from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from django.test import TestCase, override_settings
from io import StringIO
from types import SimpleNamespace
from rest_framework.test import APIClient

from notifications.digest_dispatch import dispatch
from notifications.digest_sources import prepare_digest
from notifications.models import DigestPreference, Notification
from notifications.service import deliver_pending
from portal.models import Institution, Instrument, UserProfile, ReviewObservation, AuditEvent

MONDAY = datetime(2026, 10, 26, 9, tzinfo=ZoneInfo('Asia/Kolkata'))


@override_settings(WEEKLY_DIGEST_ENABLED=True, NOTIFY_SEND_ON_COMMIT=False,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PORTAL_BASE_URL='http://127.0.0.1:8010')
class DigestIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.institution = Institution.objects.create(code='DG-A', name='Synthetic A')
        cls.other = Institution.objects.create(code='DG-B', name='Synthetic B')
        cls.user = User.objects.create_user('dg-inst', email='institution@example.invalid')
        cls.user.groups.add(Group.objects.get_or_create(name='Institution')[0])
        UserProfile.objects.create(user=cls.user, institution=cls.institution)
        cls.officer = User.objects.create_user('dg-officer', email='officer@example.invalid')
        cls.officer.groups.add(Group.objects.get_or_create(name='Officer')[0])
        cls.record = Instrument.objects.create(institution=cls.institution, reference='SYNTHETIC-DG-1', bank='Demo Bank',
            amount_paise=10000, issue_date=date(2020,1,1), maturity_date=date(2026,10,30),
            status='ACCEPTED', created_by=cls.user)
        cls.foreign = Instrument.objects.create(institution=cls.other, reference='SYNTHETIC-DG-2', bank='Demo Bank',
            amount_paise=10000, issue_date=date(2020,1,1), maturity_date=date(2026,10,30),
            status='ACCEPTED', created_by=cls.user)

    def prepare(self, user=None):
        return prepare_digest(user or self.user, as_of=MONDAY, portal_base_url='http://127.0.0.1:8010')

    def queue(self):
        return dispatch(now=MONDAY, dry_run=False, user_id=self.user.pk)

    def test_institution_scope_excludes_foreign_and_released_and_superseded(self):
        result = self.prepare()
        self.assertEqual(result['metrics'][0]['value'], 1)
        self.record.released_at = MONDAY
        self.record.save(update_fields=['released_at'])
        self.assertEqual(self.prepare()['metrics'][0]['value'], 0)

    def test_dry_run_and_disabled_flag_do_not_queue(self):
        self.assertEqual(dispatch(now=MONDAY, user_id=self.user.pk)['prepared'], 1)
        self.assertFalse(Notification.objects.exists())
        with override_settings(WEEKLY_DIGEST_ENABLED=False):
            self.assertTrue(self.queue()['disabled'])
        self.assertFalse(Notification.objects.exists())

    def test_pre_monday_9_waits_and_tuesday_catches_up_once(self):
        self.assertTrue(dispatch(now=MONDAY-timedelta(minutes=1), dry_run=False)['not_due'])
        self.assertEqual(dispatch(now=MONDAY+timedelta(days=1), dry_run=False, user_id=self.user.pk)['queued'], 1)
        self.assertEqual(self.queue()['existing'], 1)

    def test_frozen_snapshot_and_weekly_idempotency(self):
        self.assertEqual(self.queue()['queued'], 1)
        row = Notification.objects.get()
        body = row.body
        self.record.released_at = MONDAY; self.record.save(update_fields=['released_at'])
        self.assertEqual(self.queue()['existing'], 1)
        row.refresh_from_db(); self.assertEqual(row.body, body)
        self.assertEqual(dispatch(now=MONDAY+timedelta(days=7), dry_run=False, user_id=self.user.pk)['queued'], 1)

    def test_repeat_scheduler_tick_does_not_rebuild_frozen_case_sources(self):
        self.queue()
        with patch('notifications.digest_dispatch.prepare_digest',side_effect=AssertionError('Must not rebuild')):
            self.assertEqual(self.queue()['existing'],1)

    def test_delivery_memory_backend_contains_only_aggregates_and_accurate_footer(self):
        self.queue()
        self.assertEqual(deliver_pending(now=MONDAY), (1, 0))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('expiring in the rest of this month: 1', mail.outbox[0].body)
        self.assertNotIn(self.record.reference, mail.outbox[0].body)
        self.assertNotIn('contains no account or deposit details', mail.outbox[0].body)
        self.assertIn('aggregate activity counts', mail.outbox[0].body)

    def test_email_change_suppresses_frozen_message(self):
        self.queue(); self.user.email='new@example.invalid'; self.user.save(update_fields=['email'])
        self.assertEqual(deliver_pending(now=MONDAY), (0,1))
        self.assertFalse(mail.outbox)
        row=Notification.objects.get(); self.assertEqual(row.status,'FAILED'); self.assertIn('SUPPRESSED',row.last_error)

    def test_role_scope_inactive_and_optout_changes_suppress(self):
        for change in ['role','scope','inactive','optout','disabled']:
            with self.subTest(change=change):
                Notification.objects.all().delete()
                self.user.is_active=True; self.user.save(update_fields=['is_active'])
                self.user.groups.set([Group.objects.get(name='Institution')])
                UserProfile.objects.filter(user=self.user).update(institution=self.institution)
                DigestPreference.objects.filter(user=self.user).delete()
                self.queue()
                if change=='role': self.user.groups.add(Group.objects.get(name='Officer'))
                elif change=='scope': UserProfile.objects.filter(user=self.user).update(institution=self.other)
                elif change=='inactive': self.user.is_active=False; self.user.save(update_fields=['is_active'])
                elif change=='optout': DigestPreference.objects.create(user=self.user,enabled=False)
                with override_settings(WEEKLY_DIGEST_ENABLED=change!='disabled'):
                    self.assertEqual(deliver_pending(now=MONDAY),(0,1))

    def test_smtp_failure_uses_existing_retry_and_frozen_body(self):
        self.queue()
        with patch('notifications.service.send_mail',side_effect=OSError('synthetic SMTP outage')):
            self.assertEqual(deliver_pending(now=MONDAY),(0,1))
        row=Notification.objects.get(); self.assertEqual(row.attempts,1); self.assertEqual(row.status,'PENDING')
        self.assertEqual(deliver_pending(now=MONDAY+timedelta(minutes=5)),(1,0))

    def test_source_failure_does_not_queue_a_false_zero(self):
        with patch('notifications.digest_dispatch.prepare_digest',side_effect=DatabaseError('private message')):
            result=self.queue()
        self.assertEqual(result['failed'],1); self.assertFalse(Notification.objects.exists())

    def test_officer_private_draft_excluded_discrepancy_and_review_history(self):
        from verification.models import VerificationEvidence
        self.foreign.status='DRAFT'; self.foreign.save(update_fields=['status'])
        self.record.status='SUBMITTED'; self.record.verification_level='DISCREPANCY'
        self.record.save(update_fields=['status','verification_level'])
        VerificationEvidence.objects.create(instrument=self.record, actor=self.officer, instrument_version=self.record.version,
            method='SIMULATED_STATEMENT', result='DISCREPANCY', source='SIMULATED digest test')
        result=self.prepare(self.officer)
        values={m['code']:m['value'] for m in result['metrics']}
        self.assertEqual(values['pending_submissions'],1)
        self.assertEqual(values['unresolved_discrepancies'],1)
        self.assertIsNone(values['average_review_days'])

    def test_preference_allowed_invalid_stale_and_anonymous(self):
        client=APIClient(); self.assertEqual(client.get('/api/notifications/digest-preference/').status_code,401)
        client.force_authenticate(self.user)
        self.assertEqual(client.get('/api/notifications/digest-preference/').json()['version'],0)
        result=client.patch('/api/notifications/digest-preference/',{'enabled':False,'version':0},format='json')
        self.assertEqual(result.status_code,200); self.assertFalse(result.json()['enabled'])
        self.assertEqual(client.patch('/api/notifications/digest-preference/',{'enabled':True,'version':0},format='json').status_code,409)
        self.assertEqual(client.patch('/api/notifications/digest-preference/',{'enabled':'yes','version':1},format='json').status_code,400)
        self.assertEqual(client.patch('/api/notifications/digest-preference/',{'enabled':True,'version':1,'user_id':self.officer.pk},format='json').status_code,400)

    def test_preview_is_own_scope_and_never_queues(self):
        client=APIClient(); client.force_authenticate(self.user)
        response=client.get('/api/notifications/digest-preview/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['recipient_id'],self.user.pk)
        self.assertEqual(response.json()['delivery_state'],'PREVIEW_ONLY')
        self.assertFalse(Notification.objects.exists())

    def test_ambiguous_role_denied_and_database_failure_safe(self):
        client=APIClient(); client.force_authenticate(self.user)
        with patch('notifications.digest_views.prepare_digest',side_effect=DatabaseError('secret')):
            response=client.get('/api/notifications/digest-preview/')
        self.assertEqual(response.status_code,503); self.assertNotIn('secret',response.content.decode())
        self.user.groups.add(Group.objects.get(name='Officer'))
        self.assertEqual(client.get('/api/notifications/digest-preview/').status_code,403)

    def test_no_role_or_ambiguous_recipient_is_skipped(self):
        self.user.groups.clear()
        result=self.queue(); self.assertEqual(result['skipped'],1); self.assertEqual(result['failed'],0)
        self.user.groups.add(Group.objects.get(name='Institution'),Group.objects.get(name='Officer'))
        self.assertEqual(self.queue()['skipped'],1)
        self.assertFalse(Notification.objects.exists())

    def test_scheduler_hook_never_dispatches_during_replay_or_filtered_runs(self):
        rules_result=SimpleNamespace(lines=[],created=0,skipped=0,errors=[])
        with patch('notifications.management.commands.run_due_rules.run_rules',return_value=rules_result), patch('notifications.digest_dispatch.dispatch',return_value={}) as dispatcher:
            call_command('run_due_rules',stdout=StringIO())
            dispatcher.assert_called_once_with(dry_run=False)
            dispatcher.reset_mock()
            call_command('run_due_rules',as_of='2026-10-26',stdout=StringIO())
            call_command('run_due_rules',institution=self.institution.code,stdout=StringIO())
            dispatcher.assert_not_called()

    def test_invalid_list_body_and_preview_override_are_rejected(self):
        client=APIClient(); client.force_authenticate(self.user)
        self.assertEqual(client.patch('/api/notifications/digest-preference/',[],format='json').status_code,400)
        self.assertEqual(client.get('/api/notifications/digest-preview/?user_id=999').status_code,400)

    def test_new_staff_visible_institution_does_not_cancel_frozen_digest(self):
        dispatch(now=MONDAY,dry_run=False,user_id=self.officer.pk)
        institution=Institution.objects.create(code='DG-C',name='Synthetic C')
        Instrument.objects.create(institution=institution,reference='DG-C-NEW',bank='Demo Bank',amount_paise=10000,
            issue_date=date(2020,1,1),maturity_date=date(2026,10,30),status='SUBMITTED',created_by=self.user)
        self.assertEqual(deliver_pending(now=MONDAY),(1,0))

    def test_dispatch_command_failures_exit_unsuccessfully(self):
        with patch('notifications.management.commands.send_weekly_digests.dispatch',return_value={'failed':1}):
            with self.assertRaises(CommandError):
                call_command('send_weekly_digests',stdout=StringIO())

    def test_real_audit_cycles_average_1_8_and_exclude_current_week(self):
        start=MONDAY.replace(hour=0)-timedelta(days=7)
        def event(item,action,at):
            row=AuditEvent.objects.create(instrument=item,actor=self.officer,action=action)
            AuditEvent.objects.filter(pk=row.pk).update(created_at=at)
        event(self.record,'SUBMITTED',start)
        event(self.record,'ACCEPTED',start+timedelta(days=1))
        event(self.foreign,'SUBMITTED',start)
        event(self.foreign,'ACCEPTED',start+timedelta(days=2,hours=14,minutes=24))
        event(self.record,'SUBMITTED',MONDAY.replace(hour=0)-timedelta(hours=1))
        event(self.record,'ACCEPTED',MONDAY.replace(hour=0))
        result=self.prepare(self.officer)
        average=next(m for m in result['metrics'] if m['code']=='average_review_days')
        self.assertEqual(average['value'],'1.8'); self.assertEqual(average['sample_count'],2)

    def case(self):
        from obligations.models import RuleSet, DepositObligation, ReleaseCase
        from portal.models import ReleaseRequest
        rule=RuleSet.objects.create(code='digest-only-synthetic',version=1,effective_from=date(2020,1,1),
            source_clause='SYNTHETIC',source_document='Synthetic digest test')
        obligation=DepositObligation.objects.create(institution=self.institution)
        release=ReleaseRequest.objects.create(instrument=self.record,requested_by=self.user,reason='Synthetic digest case')
        return ReleaseCase.objects.create(release=release,institution=self.institution,obligation=obligation,
            rule_version=rule,rule_sha256='0'*64,path='TERM_COMPLETE',mode='FDR')

    def test_clearance_real_unit_assignment_excludes_other_unit_tasks(self):
        from access.models import UnitAssignment
        from obligations.models import ClearanceTask
        case=self.case()
        ClearanceTask.objects.create(case=case,unit='PGRC')
        ClearanceTask.objects.create(case=case,unit='VIGILANCE')
        clearance=get_user_model().objects.create_user('digest-pgrc',email='pgrc@example.invalid')
        clearance.groups.add(Group.objects.get_or_create(name='Clearance')[0])
        UnitAssignment.objects.create(user=clearance,unit='PGRC')
        self.assertEqual(self.prepare(clearance)['metrics'][0]['value'],1)

    def test_authority_uses_existing_action_gate_and_unknown_escalations(self):
        self.case()
        authority=get_user_model().objects.create_user('digest-authority',email='authority@example.invalid')
        authority.groups.add(Group.objects.get_or_create(name='Authority')[0])
        for allowed in [False,True]:
            with patch('casework.api.case_json',return_value={'actions':{'can_approve':allowed}}) as gate:
                values={m['code']:m['value'] for m in self.prepare(authority)['metrics']}
                self.assertEqual(values['awaiting_authority'],int(allowed))
                self.assertIsNone(values['pgrc_escalations']); gate.assert_called_once()
