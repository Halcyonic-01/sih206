from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import override_settings
from django.utils import timezone

from audit.chain import verify_chain
from audit.models import RecordRetention
from portal import retention, services
from portal.models import AuditEvent, Instrument
from portal.permissions import AUTHORITY_GROUP
from portal.tests.common import PortalTestCase


class RetentionTests(PortalTestCase):
    def setUp(self):
        self.authority = get_user_model().objects.create_user(username='authority', password='x')
        self.authority.groups.add(Group.objects.get_or_create(name=AUTHORITY_GROUP)[0])
        record = self.submitted()
        self.record = services.review(self.officer, record.pk, record.version, 'accept', 'Synthetic review')

    def settle(self, years_ago):
        Instrument.objects.filter(pk=self.record.pk).update(released_at=timezone.now() - timedelta(days=365 * years_ago + years_ago // 4 + 2))
        self.record.refresh_from_db()

    def post(self, user, action, reason='Retention period has passed.', method='post'):
        self.client.force_login(user)
        return getattr(self.client, method)(f'/api/instruments/{self.record.pk}/{action}/', {'reason': reason}, content_type='application/json')

    def test_an_unsettled_record_has_no_due_date_and_cannot_be_archived(self):
        state = retention.state(self.record)
        self.assertEqual((state['settled_on'], state['archival_due_on'], state['archival_due']), (None, None, False))
        self.assertEqual(self.post(self.authority, 'archive').status_code, 409)

    def test_a_settled_record_becomes_due_after_the_configured_years(self):
        self.settle(3)
        self.assertFalse(retention.state(self.record)['archival_due'])
        with override_settings(RETENTION_YEARS=2):
            self.assertTrue(retention.state(self.record)['archival_due'])
        self.assertEqual(self.post(self.authority, 'archive').status_code, 409)
        self.settle(11)
        state = retention.state(self.record)
        self.assertTrue(state['archival_due'])
        self.assertEqual(state['retention_years'], 10)

    def test_archiving_freezes_the_record_and_is_audited(self):
        self.settle(11)
        response = self.post(self.authority, 'archive')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['archived'])
        self.assertTrue(AuditEvent.objects.filter(instrument=self.record, action='ARCHIVED').exists())
        self.record.refresh_from_db()
        with self.assertRaisesMessage(services.WorkflowError, 'archived and frozen'):
            services._compare_and_update(self.record, self.record.version, bank='Changed')
        self.assertEqual(self.post(self.authority, 'archive').status_code, 409)
        self.assertTrue(verify_chain().ok)

    def test_a_legal_hold_blocks_archiving_until_lifted(self):
        self.settle(11)
        self.assertEqual(self.post(self.authority, 'legal-hold', 'Court order 12/2026').status_code, 200)
        self.assertTrue(retention.state(self.record)['legal_hold'])
        self.assertEqual(self.post(self.authority, 'legal-hold', 'again').status_code, 409)
        blocked = self.post(self.authority, 'archive')
        self.assertEqual(blocked.status_code, 409)
        self.assertIn('legal hold', blocked.json()['detail'])
        lifted = self.post(self.authority, 'legal-hold', 'Order withdrawn', method='delete')
        self.assertEqual(lifted.status_code, 200)
        self.assertEqual(self.post(self.authority, 'archive').status_code, 200)
        self.assertEqual({e.action for e in AuditEvent.objects.filter(instrument=self.record)} & {'LEGAL_HOLD_SET', 'LEGAL_HOLD_LIFTED'},
                         {'LEGAL_HOLD_SET', 'LEGAL_HOLD_LIFTED'})

    def test_only_the_authority_may_act_and_a_reason_is_required(self):
        self.settle(11)
        for user in (self.officer, self.a):
            self.assertEqual(self.post(user, 'archive').status_code, 403)
            self.assertEqual(self.post(user, 'legal-hold').status_code, 403)
        self.assertEqual(self.post(self.authority, 'archive', reason='no').status_code, 409)
        self.assertFalse(RecordRetention.objects.filter(archived_at__isnull=False).exists())

    def test_the_due_list_and_the_record_detail_show_it(self):
        self.settle(11)
        self.client.force_login(self.officer)
        rows = self.client.get('/api/retention/due/').json()['results']
        self.assertEqual([r['id'] for r in rows], [self.record.pk])
        self.assertTrue(self.client.get(f'/api/instruments/{self.record.pk}/').json()['retention']['archival_due'])
        self.post(self.authority, 'archive')
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get('/api/retention/due/').json()['results'], [])
        self.client.force_login(self.a)
        self.assertEqual(self.client.get('/api/retention/due/').json()['results'], [])

    def test_the_command_lists_due_records_and_archives_only_when_asked(self):
        from io import StringIO
        from django.core.management import call_command
        self.settle(11)
        out = StringIO()
        call_command('archive_due_records', stdout=out)
        self.assertIn(self.record.reference, out.getvalue())
        self.assertFalse(RecordRetention.objects.exists())
        call_command('archive_due_records', '--archive', '--as-user', 'authority', '--reason', 'Scheduled archival', stdout=StringIO())
        self.assertTrue(retention.is_archived(self.record))
