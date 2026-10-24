"""Problem-statement scenarios owned by Kushagra (4, 8 and 10), driven through the real views, API and commands."""
from datetime import date, timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from access.models import AccessLog
from access.tests.base import PASSWORD, StaffTestCase
from audit.models import AuditSeal
from notifications.models import Notification
from portal import releases
from portal.models import AuditEvent, Instrument, ReleaseRequest


class ScenarioCase(StaffTestCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        for user, address in ((self.a, 'inst-a@demo.example'), (self.officer, 'officer@demo.example')):
            User.objects.filter(pk=user.pk).update(email=address)

    def accepted(self, maturity, reference='SCN-1'):
        """Institution A submits a record with a PDF; the officer accepts it (all through the legacy views)."""
        self.client.force_login(self.a)
        created = self.client.post(reverse('instrument_create'), {
            **self.payload(reference=reference, maturity_date=maturity.isoformat()), 'document': self.pdf()})
        self.assertEqual(created.status_code, 302)
        record = Instrument.objects.get(reference=reference)
        self.client.post(reverse('instrument_submit', args=[record.pk]), {'version': record.version})
        record.refresh_from_db()
        self.client.force_login(self.officer)
        response = self.client.post(reverse('instrument_review', args=[record.pk]), {
            'version': record.version, 'decision': 'accept', 'reason': 'Reviewed (synthetic).'})
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.status, Instrument.Status.ACCEPTED)
        return record


class Scenario4ApproachingMaturityAndAlerts(ScenarioCase):
    """run_due_rules --as-of produces a T-30 reminder in the bell and by email; an unrenewed matured record escalates."""

    def test_t_minus_30_reminder_reaches_the_bell_and_the_inbox_of_email(self):
        as_of = date(2026, 10, 23)
        record = self.accepted(as_of + timedelta(days=30))
        call_command('run_due_rules', '--as-of', as_of.isoformat(), stdout=StringIO())

        institution_client = Client()
        institution_client.force_login(self.a)
        self.assertEqual(institution_client.get('/api/notifications/unread-count/').json(), {'count': 1})
        item = institution_client.get('/api/notifications/').json()['results'][0]
        self.assertEqual(item['subject'], 'FDR SCN-1 matures in 30 days')
        self.assertEqual(item['link'], f'/records/{record.pk}')
        # The dealing officer is told from T-30 as well.
        officer_client = Client()
        officer_client.force_login(self.officer)
        self.assertEqual(officer_client.get('/api/notifications/unread-count/').json(), {'count': 1})

        call_command('send_notifications', stdout=StringIO())
        recipients = sorted(message.to[0] for message in mail.outbox)
        self.assertEqual(recipients, ['inst-a@demo.example', 'officer@demo.example'])
        self.assertIn(f'/records/{record.pk}', mail.outbox[0].body)
        self.assertNotIn('500000', mail.outbox[0].body)   # no amounts in email
        self.assertEqual(Notification.objects.filter(channel='EMAIL', status='SENT').count(), 2)

        before = Notification.objects.count()
        call_command('run_due_rules', '--as-of', as_of.isoformat(), stdout=StringIO())
        self.assertEqual(Notification.objects.count(), before)   # running twice adds nothing

    def test_a_matured_record_without_a_successor_escalates_as_overdue(self):
        matured = self.accepted(date(2026, 10, 22), reference='SCN-OVERDUE')
        call_command('run_due_rules', '--as-of', '2026-10-23', stdout=StringIO())
        overdue = Notification.objects.filter(template_id='renewal_overdue', channel='IN_APP')
        self.assertEqual({row.recipient.username for row in overdue}, {'institution_a', 'officer', 'authority'})
        self.assertEqual(overdue.first().severity, 'critical')
        self.assertEqual(overdue.first().link, f'/records/{matured.pk}')

    def test_boundaries_minus_one_zero_plus_one(self):
        self.accepted(date(2026, 11, 22), reference='SCN-EDGE')
        t30 = Notification.objects.filter(channel='IN_APP', recipient=self.a, idempotency_key__contains=':maturity:T-30:')
        call_command('run_due_rules', '--as-of', '2026-10-22', stdout=StringIO())    # 31 days left: T-60 only
        self.assertEqual(t30.count(), 0)
        call_command('run_due_rules', '--as-of', '2026-10-23', stdout=StringIO())    # 30 days left: T-30 fires
        self.assertEqual(t30.count(), 1)
        call_command('run_due_rules', '--as-of', '2026-11-22', stdout=StringIO())    # matures today: no overdue yet
        self.assertFalse(Notification.objects.filter(template_id='renewal_overdue').exists())
        call_command('run_due_rules', '--as-of', '2026-11-23', stdout=StringIO())    # one day past: overdue
        self.assertTrue(Notification.objects.filter(template_id='renewal_overdue').exists())


class Scenario8AccessControl(ScenarioCase):
    def test_institution_b_cannot_open_a_record_or_document_of_a(self):
        record = self.submitted()
        document = record.documents.get()
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(reverse('instrument_detail', args=[record.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('document_download', args=[document.pk])).status_code, 404)
        self.assertEqual(AccessLog.objects.filter(action=AccessLog.DOCUMENT_DOWNLOAD).count(), 0)

    def test_requester_cannot_decide_their_own_release_and_clearance_cannot_decide_at_all(self):
        record = self.accepted(date(2027, 6, 1))
        release = releases.request_release(self.a, record.pk, record.version, 'Release please.')
        record.refresh_from_db()
        for user in (self.a, self.pgrc, self.vigilance, self.auditor, self.officer):
            with self.subTest(user=user.username), self.assertRaises(PermissionDenied):
                releases.decide_release(user, record.pk, release.pk, record.version, 'approve', 'Nope.')
        # Only an authority other than the requester may decide.
        releases.decide_release(self.authority, record.pk, release.pk, record.version, 'approve', 'Independent decision.')
        self.assertEqual(ReleaseRequest.objects.get(pk=release.pk).status, 'APPROVED')

    def test_login_locks_after_five_failures(self):
        client = Client(enforce_csrf_checks=True)
        extra = {'HTTP_X_CSRFTOKEN': client.get('/api/auth/csrf/').json()['csrfToken']}
        statuses = [client.post('/api/auth/login/', {'username': 'officer', 'password': 'wrong'},
                                content_type='application/json', **extra).status_code for _ in range(5)]
        self.assertEqual(statuses, [400, 400, 400, 400, 429])
        locked = client.post('/api/auth/login/', {'username': 'officer', 'password': PASSWORD},
                             content_type='application/json', **extra)
        self.assertEqual((locked.status_code, locked.json()['code']), (429, 'locked_out'))


class Scenario10AuditTrail(ScenarioCase):
    def test_auditor_sees_full_history_access_log_chain_and_a_tampered_row_shows_broken(self):
        record = self.accepted(date(2027, 6, 1))
        document = record.documents.get()
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(reverse('document_download', args=[document.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('instrument_export') + '?category=all').status_code, 200)

        auditor = Client()
        auditor.force_login(self.auditor)
        events = auditor.get(f'/api/audit/events/?instrument={record.pk}').json()
        self.assertEqual({row['action'] for row in events['results']},
                         {'DRAFT_CREATED', 'SUBMITTED', 'ACCEPTED'})
        logged = {row['action'] for row in auditor.get('/api/audit/access-log/').json()['results']}
        self.assertTrue({'DOCUMENT_DOWNLOAD', 'EXPORT', 'LOGIN'} <= logged)

        chain = auditor.get('/api/audit/chain/verify/').json()
        self.assertEqual((chain['status'], chain['broken']), ('ok', []))
        self.assertEqual(chain['checked'], AuditEvent.objects.count())
        self.assertEqual(AuditSeal.objects.count(), AuditEvent.objects.count())

        accepted_event = AuditEvent.objects.get(instrument=record, action='ACCEPTED')
        AuditEvent.objects.filter(pk=accepted_event.pk).update(reason='Edited directly in the database.')
        chain = auditor.get('/api/audit/chain/verify/').json()
        self.assertEqual(chain['status'], 'broken')
        self.assertEqual([item['event_id'] for item in chain['broken']], [accepted_event.pk])

    def test_nobody_but_the_auditor_can_read_the_access_log_or_chain(self):
        for user in (self.a, self.officer, self.authority, self.pgrc):
            client = Client()
            client.force_login(user)
            for path in ('/api/audit/access-log/', '/api/audit/events/', '/api/audit/chain/verify/'):
                self.assertEqual(client.get(path).status_code, 403, (user.username, path))
