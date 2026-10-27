from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.test import override_settings

from access.models import AppendOnlyError
from access.tests.base import StaffTestCase
from audit.chain import compute_hash, seal_pending, verify_chain
from audit.models import AuditSeal
from portal.models import AuditEvent


class ChainTestCase(StaffTestCase):
    def setUp(self):
        self.record = self.instrument(self.institution_a, self.a)

    def event(self, action='X', **extra):
        return AuditEvent.objects.create(instrument=self.record, actor=self.officer, action=action, **extra)

    def raw(self, sql, *params):
        with connection.cursor() as cursor:
            cursor.execute(sql, params)


class SealingTests(ChainTestCase):
    def test_every_event_is_sealed_and_linked_to_the_previous_seal(self):
        first, second, third = self.event('A'), self.event('B'), self.event('C')
        seals = [first.seal, second.seal, third.seal]
        self.assertEqual(seals[0].prev_hash, '')
        self.assertEqual(seals[1].prev_hash, seals[0].hash)
        self.assertEqual(seals[2].prev_hash, seals[1].hash)
        self.assertEqual(seals[0].hash, compute_hash('', first))
        self.assertFalse(any(seal.backfilled for seal in seals))
        self.assertTrue(verify_chain().ok)

    def test_a_real_workflow_produces_a_valid_chain(self):
        self.submitted()
        result = verify_chain()
        self.assertEqual(result.status, 'ok')
        self.assertGreaterEqual(result.checked, 2)
        self.assertEqual(result.head, AuditSeal.objects.order_by('-pk').first().hash)

    def test_empty_chain_is_ok(self):
        result = verify_chain()
        self.assertEqual((result.status, result.checked, result.head), ('ok', 0, ''))

    def test_rolled_back_events_leave_no_seal(self):
        self.event('A')
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.event('B')
                raise RuntimeError('boom')
        self.assertEqual(AuditSeal.objects.count(), 1)
        self.assertTrue(verify_chain().ok)
        self.event('C')
        self.assertTrue(verify_chain().ok)

    def test_the_chain_cannot_fork(self):
        first = self.event('A')
        with self.assertRaises(IntegrityError), transaction.atomic():
            AuditSeal.objects.create(event=self.event('B'), prev_hash='', hash='f' * 64)  # claims the genesis slot
        self.assertEqual(first.seal.prev_hash, '')

    def test_seals_are_append_only(self):
        seal = self.event('A').seal
        seal.hash = 'x' * 64
        with self.assertRaises(AppendOnlyError):
            seal.save()
        with self.assertRaises(AppendOnlyError):
            seal.delete()
        with self.assertRaises(AppendOnlyError):
            AuditSeal.objects.update(hash='x')

    def test_long_chains_verify_across_chunk_boundaries(self):
        for number in range(520):
            self.event(f'E{number}')
        self.assertEqual(verify_chain().checked, 520)
        self.assertTrue(verify_chain().ok)


class TamperDetectionTests(ChainTestCase):
    def setUp(self):
        super().setUp()
        self.events = [self.event(f'E{number}', reason=f'reason {number}') for number in range(4)]

    def broken(self):
        result = verify_chain()
        return result.status, [(item['event_id'], item['reason']) for item in result.broken]

    def test_editing_an_event_is_detected_at_that_event_only(self):
        AuditEvent.objects.filter(pk=self.events[1].pk).update(reason='quietly rewritten')  # bypasses the app
        self.assertEqual(self.broken(), ('broken', [(self.events[1].pk, 'event_modified')]))

    def test_editing_a_snapshot_is_detected(self):
        AuditEvent.objects.filter(pk=self.events[2].pk).update(after={'status': 'ACCEPTED'})
        self.assertEqual(self.broken(), ('broken', [(self.events[2].pk, 'event_modified')]))

    def test_changing_the_actor_or_time_is_detected(self):
        AuditEvent.objects.filter(pk=self.events[0].pk).update(actor=self.authority)
        self.assertEqual(self.broken()[1], [(self.events[0].pk, 'event_modified')])
        AuditEvent.objects.filter(pk=self.events[0].pk).update(actor=self.officer)
        self.assertTrue(verify_chain().ok)
        # Events created within one clock tick can have identical timestamps.
        changed_at = self.events[3].created_at + timedelta(seconds=1)
        AuditEvent.objects.filter(pk=self.events[3].pk).update(created_at=changed_at)
        self.assertEqual(self.broken()[1], [(self.events[3].pk, 'event_modified')])

    def test_deleting_a_seal_breaks_the_chain(self):
        self.raw('DELETE FROM audit_auditseal WHERE event_id = %s', self.events[1].pk)
        status, items = self.broken()
        self.assertEqual(status, 'broken')
        self.assertIn((self.events[2].pk, 'chain_break'), items)

    def test_rewriting_a_seal_hash_breaks_the_chain(self):
        self.raw("UPDATE audit_auditseal SET hash = %s WHERE event_id = %s", 'a' * 64, self.events[1].pk)
        _, items = self.broken()
        self.assertIn((self.events[1].pk, 'event_modified'), items)
        self.assertIn((self.events[2].pk, 'chain_break'), items)

    def test_deleting_an_event_is_detected(self):
        savepoint = transaction.savepoint()
        try:
            with connection.constraint_checks_disabled():  # what someone with direct database access could do
                self.raw('DELETE FROM portal_auditevent WHERE id = %s', self.events[2].pk)
            self.assertEqual(self.broken(), ('broken', [(self.events[2].pk, 'event_missing')]))
        finally:
            transaction.savepoint_rollback(savepoint)

    def test_an_event_inserted_behind_the_applications_back_is_reported_unsealed(self):
        AuditEvent.objects.bulk_create([AuditEvent(instrument=self.record, actor=self.officer, action='SNEAKY')])
        result = verify_chain()
        self.assertEqual((result.status, result.unsealed), ('incomplete', 1))
        self.assertEqual(seal_pending(), 1)
        result = verify_chain()
        self.assertEqual((result.status, result.backfilled), ('ok', 1))  # honest: sealed late

    def test_the_chain_is_keyed(self):
        self.assertTrue(verify_chain().ok)
        with override_settings(AUDIT_CHAIN_KEY='someone-without-the-real-key'):
            self.assertEqual(verify_chain().status, 'broken')


class CommandAndApiTests(ChainTestCase):
    def setUp(self):
        super().setUp()
        self.events = [self.event(f'E{number}') for number in range(3)]

    def test_verify_command_passes_and_fails(self):
        out = StringIO()
        call_command('verify_audit_chain', stdout=out)
        self.assertIn('OK', out.getvalue())
        AuditEvent.objects.filter(pk=self.events[1].pk).update(reason='tampered')
        err = StringIO()
        with self.assertRaises(CommandError):
            call_command('verify_audit_chain', stdout=StringIO(), stderr=err)
        self.assertIn(f'BROKEN at event {self.events[1].pk}', err.getvalue())

    def test_seal_command_backfills_old_events(self):
        AuditEvent.objects.bulk_create([AuditEvent(instrument=self.record, actor=self.officer, action='OLD')])
        out = StringIO()
        call_command('seal_audit_chain', stdout=out)
        self.assertIn('Sealed 1', out.getvalue())
        self.assertTrue(AuditSeal.objects.filter(backfilled=True).exists())
        call_command('verify_audit_chain', stdout=StringIO())

    def test_api_is_auditor_only(self):
        for user in (self.a, self.officer, self.authority, self.pgrc):
            self.client.force_login(user)
            self.assertEqual(self.client.get('/api/audit/chain/verify/').status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get('/api/audit/chain/verify/').status_code, 401)

    def test_api_reports_ok_then_broken(self):
        self.client.force_login(self.auditor)
        body = self.client.get('/api/audit/chain/verify/').json()
        self.assertEqual((body['status'], body['checked'], body['broken']), ('ok', 3, []))
        self.assertEqual(len(body['head']), 64)
        AuditEvent.objects.filter(pk=self.events[0].pk).update(action='CHANGED')
        body = self.client.get('/api/audit/chain/verify/').json()
        self.assertEqual(body['status'], 'broken')
        self.assertEqual(body['broken'][0]['event_id'], self.events[0].pk)

    def test_event_detail_includes_its_seal(self):
        self.client.force_login(self.auditor)
        body = self.client.get(f'/api/audit/events/{self.events[1].pk}/').json()
        self.assertEqual(body['seal']['hash'], self.events[1].seal.hash)
        self.assertEqual(body['seal']['prev_hash'], self.events[0].seal.hash)
        self.assertFalse(body['seal']['backfilled'])
