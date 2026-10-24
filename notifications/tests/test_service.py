from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from access.models import UnitAssignment
from notifications import recipients as who
from notifications.models import DeliveryAttempt, Notification
from notifications.service import MAX_ATTEMPTS, deliver_pending, notify
from portal.models import Institution, UserProfile
from portal.permissions import AUDITOR_GROUP, CLEARANCE_GROUP, INSTITUTION_GROUP, OFFICER_GROUP


class NotifyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.with_email = User.objects.create_user(username='a', password='x', email='a@example.org')
        cls.without_email = User.objects.create_user(username='b', password='x')

    def test_user_gets_inbox_row_and_email_row_when_they_have_an_address(self):
        rows = notify([self.with_email], 'maturity_reminder',
                      {'reference': 'FDR-1', 'days': 30, 'maturity_date': '2026-11-23', 'url': '/records/4'},
                      'instrument:4:maturity:T-30:2026-11-23')
        self.assertEqual(sorted(row.channel for row in rows), ['EMAIL', 'IN_APP'])
        inbox = Notification.objects.get(channel='IN_APP')
        self.assertEqual(inbox.status, 'SENT')
        self.assertEqual(inbox.subject, 'FDR FDR-1 matures in 30 days')
        self.assertEqual(inbox.link, '/records/4')
        self.assertEqual(inbox.severity, 'warning')
        self.assertEqual(Notification.objects.get(channel='EMAIL').status, 'PENDING')

    def test_user_without_address_gets_inbox_only(self):
        rows = notify([self.without_email], 'instrument_submitted', {'reference': 'R'}, 'k1')
        self.assertEqual([row.channel for row in rows], ['IN_APP'])

    def test_plain_email_addresses_get_email_only(self):
        rows = notify(['Contact@Example.org '], 'instrument_submitted', {'reference': 'R'}, 'k1')
        self.assertEqual([(row.channel, row.recipient_email, row.recipient) for row in rows],
                         [('EMAIL', 'contact@example.org', None)])

    def test_user_ids_are_accepted(self):
        notify([self.without_email.pk], 'instrument_submitted', {'reference': 'R'}, 'k1')
        self.assertEqual(Notification.objects.get().recipient, self.without_email)

    def test_same_key_and_recipient_never_duplicates(self):
        args = ([self.with_email, self.with_email], 'instrument_submitted', {'reference': 'R'}, 'event:1')
        self.assertEqual(len(notify(*args)), 2)
        self.assertEqual(notify(*args), [])
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(len(notify([self.with_email], 'instrument_submitted', {'reference': 'R'}, 'event:2')), 2)
        self.assertEqual(Notification.objects.count(), 4)

    def test_a_new_recipient_on_the_same_event_is_added_once(self):
        notify([self.with_email], 'instrument_submitted', {'reference': 'R'}, 'event:1')
        rows = notify([self.with_email, self.without_email], 'instrument_submitted', {'reference': 'R'}, 'event:1')
        self.assertEqual([(row.recipient, row.channel) for row in rows], [(self.without_email, 'IN_APP')])

    def test_key_is_required(self):
        with self.assertRaises(ValueError):
            notify([self.with_email], 'instrument_submitted', {'reference': 'R'}, '')

    def test_unknown_template_uses_generic_text_and_missing_values_do_not_raise(self):
        notify([self.without_email], 'something_new', {'subject': 'Heads up', 'message': 'Details here.'}, 'k1')
        row = Notification.objects.get()
        self.assertEqual((row.subject, row.body), ('Heads up', 'Details here.'))
        notify([self.without_email], 'maturity_reminder', {'reference': 'R'}, 'k2')
        self.assertIn('{days}', Notification.objects.get(idempotency_key='k2').subject)

    def test_severity_can_be_overridden_in_context(self):
        notify([self.without_email], 'instrument_submitted', {'reference': 'R', 'severity': 'critical'}, 'k1')
        self.assertEqual(Notification.objects.get().severity, 'critical')

    def test_outbox_rolls_back_with_the_event(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                notify([self.with_email], 'instrument_submitted', {'reference': 'R'}, 'k1')
                raise RuntimeError('event failed')
        self.assertEqual(Notification.objects.count(), 0)


class DeliveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='a', password='x', email='a@example.org')

    def queue(self, key='k1'):
        notify([self.user], 'instrument_submitted', {'reference': 'FDR-9', 'url': '/records/9'}, key)
        return Notification.objects.get(channel='EMAIL', idempotency_key=key)

    @override_settings(PORTAL_BASE_URL='https://fdr.example.gov.in/')
    def test_email_is_sent_with_a_link_and_no_details(self):
        row = self.queue()
        self.assertEqual(deliver_pending(), (1, 0))
        message = mail.outbox[0]
        self.assertEqual(message.to, ['a@example.org'])
        self.assertIn('https://fdr.example.gov.in/records/9', message.body)
        self.assertIn('FDR-9', message.subject)
        row.refresh_from_db()
        self.assertEqual((row.status, row.attempts), ('SENT', 1))
        self.assertIsNotNone(row.sent_at)
        self.assertEqual(DeliveryAttempt.objects.get().ok, True)
        self.assertEqual(deliver_pending(), (0, 0))  # nothing left to send

    def test_failed_send_retries_with_backoff_then_fails_permanently(self):
        row = self.queue()
        start = timezone.now()
        waits = []
        with mock.patch('notifications.service.send_mail', side_effect=ConnectionRefusedError('smtp down')):
            now = start
            for attempt in range(1, MAX_ATTEMPTS + 1):
                self.assertEqual(deliver_pending(now=now), (0, 1))
                row.refresh_from_db()
                self.assertEqual(row.attempts, attempt)
                if row.status == 'PENDING':
                    waits.append(row.next_attempt_at - now)
                    # Not due again before the backoff has passed.
                    self.assertEqual(deliver_pending(now=now + waits[-1] - timedelta(seconds=1)), (0, 0))
                    now = row.next_attempt_at
        self.assertEqual(waits, [timedelta(minutes=m) for m in (5, 15, 60, 240)])
        self.assertEqual(row.status, 'FAILED')
        self.assertIsNone(row.next_attempt_at)
        self.assertIn('ConnectionRefusedError', row.last_error)
        self.assertEqual(DeliveryAttempt.objects.filter(ok=False).count(), MAX_ATTEMPTS)
        self.assertEqual(deliver_pending(now=now + timedelta(days=9)), (0, 0))  # FAILED is final

    def test_recovery_after_a_failure(self):
        row = self.queue()
        with mock.patch('notifications.service.send_mail', side_effect=OSError('boom')):
            deliver_pending()
        row.refresh_from_db()
        self.assertEqual(deliver_pending(now=row.next_attempt_at), (1, 0))
        row.refresh_from_db()
        self.assertEqual((row.status, row.attempts, row.last_error), ('SENT', 2, ''))

    def test_a_leased_row_is_not_sent_twice(self):
        row = self.queue()
        Notification.objects.filter(pk=row.pk).update(next_attempt_at=timezone.now() + timedelta(minutes=5))
        self.assertEqual(deliver_pending(), (0, 0))
        self.assertEqual(len(mail.outbox), 0)

    def test_sends_right_after_commit_when_enabled(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.queue()
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(NOTIFY_SEND_ON_COMMIT=False)
    def test_on_commit_sending_can_be_disabled(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.queue()
        self.assertEqual(len(mail.outbox), 0)

    def test_management_command(self):
        self.queue()
        call_command('send_notifications')
        self.assertEqual(len(mail.outbox), 1)


class RecipientHelperTests(TestCase):
    def test_role_and_institution_helpers(self):
        User = get_user_model()
        officer = User.objects.create_user(username='o', password='x')
        officer.groups.add(Group.objects.create(name=OFFICER_GROUP))
        auditor = User.objects.create_user(username='au', password='x')
        auditor.groups.add(Group.objects.create(name=AUDITOR_GROUP))
        clearance = Group.objects.create(name=CLEARANCE_GROUP)
        pgrc = User.objects.create_user(username='p', password='x')
        pgrc.groups.add(clearance)
        UnitAssignment.objects.create(user=pgrc, unit='PGRC')
        vig = User.objects.create_user(username='v', password='x')
        vig.groups.add(clearance)
        UnitAssignment.objects.create(user=vig, unit='VIGILANCE')
        institution = Institution.objects.create(code='A', name='A')
        member = User.objects.create_user(username='m', password='x')
        member.groups.add(Group.objects.create(name=INSTITUTION_GROUP))
        UserProfile.objects.create(user=member, institution=institution)
        gone = User.objects.create_user(username='gone', password='x', is_active=False)
        gone.groups.add(Group.objects.get(name=OFFICER_GROUP))

        self.assertEqual(who.officers(), [officer])
        self.assertEqual(who.auditors(), [auditor])
        self.assertEqual(who.clearance_users('PGRC'), [pgrc])
        self.assertEqual(set(who.clearance_users()), {pgrc, vig})
        self.assertEqual(who.institution_users(institution), [member])
        self.assertEqual(who.institution_contacts(institution), [member])
        self.assertEqual(who.authorities(), [])
