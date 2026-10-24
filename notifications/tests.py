from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from django.core import mail
from django.core.management import call_command
from django.db import transaction
from django.test import override_settings
from django.utils import timezone
from notifications.models import DeliveryAttempt, Notification
from notifications.services import deliver_pending, notify
from portal.tests.common import PortalTestCase


@override_settings(ROOT_URLCONF='config.urls', NOTIFICATION_EMAIL_ENABLED=False)
class NotificationTests(PortalTestCase):
    def enqueue(self, key='synthetic-event'):
        return notify(recipients=[self.a.pk], template='record_submitted', context={'reference': 'SYNTHETIC', 'secret': 'excluded'}, key=key)

    def test_outbox_idempotency_and_rollback(self):
        self.enqueue()
        self.enqueue()
        self.assertEqual(Notification.objects.count(), 1)
        self.assertNotIn('secret', Notification.objects.get().context)
        try:
            with transaction.atomic():
                self.enqueue('rolled-back')
                raise ValueError('rollback')
        except ValueError:
            pass
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(deliver_pending(), 1)
        self.assertEqual(deliver_pending(), 0)
        self.assertEqual(DeliveryAttempt.objects.count(), 1)

    def test_inbox_is_recipient_scoped_and_read_is_idempotent(self):
        row = self.enqueue()[0]
        self.client.force_login(self.b)
        self.assertEqual(self.client.get('/api/notifications/').json(), [])
        self.assertEqual(self.client.post(f'/api/notifications/{row.pk}/read/').status_code, 404)
        self.client.force_login(self.a)
        self.assertEqual(len(self.client.get('/api/notifications/').json()), 1)
        for _ in range(2):
            self.assertEqual(self.client.post(f'/api/notifications/{row.pk}/read/').status_code, 200)
        self.assertEqual(self.client.post('/api/notifications/999999/read/').status_code, 404)
        row.refresh_from_db()
        self.assertIsNotNone(row.read_at)

    @override_settings(NOTIFICATION_EMAIL_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_email_delivery_retry_history_and_exhaustion(self):
        self.a.email = 'synthetic@example.invalid'
        self.a.save()
        self.enqueue()
        with patch('notifications.services.send_mail', side_effect=OSError('private relay detail')):
            for attempt in range(5):
                Notification.objects.filter(channel='EMAIL').update(next_attempt_at=timezone.now()-timedelta(seconds=1))
                deliver_pending()
        email = Notification.objects.get(channel='EMAIL')
        self.assertEqual((email.status, email.attempts, email.last_error), ('FAILED', 5, 'DELIVERY_FAILED'))
        self.assertEqual(email.delivery_attempts.count(), 5)
        self.enqueue('success')
        deliver_pending()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('SYNTHETIC', mail.outbox[0].body)
        self.assertEqual(Notification.objects.get(key='success', channel='EMAIL').status, 'CAPTURED')

    def test_operations_delivery_history_is_officer_only(self):
        self.enqueue()
        self.client.force_login(self.a)
        self.assertEqual(self.client.get('/api/notifications/deliveries/').status_code, 403)
        self.client.force_login(self.officer)
        response = self.client.get('/api/notifications/deliveries/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['attempts'], 0)

    def test_scheduler_exact_boundaries_and_repeat_run(self):
        item = self.draft()
        today = timezone.localdate()
        item.status, item.maturity_date = 'ACCEPTED', today+timedelta(days=30)
        item.save()
        with patch('notifications.management.commands.run_due_rules.business_today', return_value=today):
            call_command('run_due_rules', stdout=StringIO())
            call_command('run_due_rules', stdout=StringIO())
        self.assertEqual(Notification.objects.count(), 1)
        Notification.objects.all().delete()
        for days in (29, 31):
            item.maturity_date = today+timedelta(days=days)
            item.save()
            with patch('notifications.management.commands.run_due_rules.business_today', return_value=today):
                call_command('run_due_rules', stdout=StringIO())
        self.assertEqual(Notification.objects.count(), 0)
