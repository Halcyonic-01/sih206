from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from notifications.models import Notification
from notifications.service import notify
from portal.permissions import AUDITOR_GROUP, OFFICER_GROUP


class InboxApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.alice = User.objects.create_user(username='alice', password='x')
        cls.bob = User.objects.create_user(username='bob', password='x')
        cls.auditor = User.objects.create_user(username='auditor', password='x')
        cls.auditor.groups.add(Group.objects.create(name=AUDITOR_GROUP))
        cls.officer = User.objects.create_user(username='officer', password='x')
        cls.officer.groups.add(Group.objects.create(name=OFFICER_GROUP))

    def setUp(self):
        notify([self.alice, self.bob], 'instrument_submitted', {'reference': 'R1', 'url': '/records/1'}, 'e1')
        notify([self.alice], 'instrument_submitted', {'reference': 'R2', 'url': '/records/2'}, 'e2')
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.alice)
        self.token = self.client.get('/api/auth/csrf/').json()['csrfToken']

    def post(self, path):
        return self.client.post(path, HTTP_X_CSRFTOKEN=self.token)

    def test_requires_sign_in(self):
        self.assertEqual(Client().get('/api/notifications/').status_code, 401)
        self.assertEqual(Client().get('/api/notifications/unread-count/').status_code, 401)

    def test_lists_only_my_inbox_newest_first_with_pagination_envelope(self):
        body = self.client.get('/api/notifications/').json()
        self.assertEqual(body['count'], 2)
        self.assertEqual([row['subject'] for row in body['results']],
                         ['New submission to review: R2', 'New submission to review: R1'])
        self.assertEqual(set(body['results'][0]), {'id', 'template_id', 'subject', 'body', 'link', 'severity',
                                                   'created_at', 'read_at', 'is_read'})
        self.assertFalse(body['results'][0]['is_read'])

    def test_unread_filter_and_count(self):
        self.assertEqual(self.client.get('/api/notifications/unread-count/').json(), {'count': 2})
        first = Notification.objects.get(recipient=self.alice, idempotency_key='e1', channel='IN_APP')
        self.assertEqual(self.post(f'/api/notifications/{first.pk}/read/').status_code, 200)
        self.assertEqual(self.client.get('/api/notifications/unread-count/').json(), {'count': 1})
        unread = self.client.get('/api/notifications/?unread=1').json()
        self.assertEqual(unread['count'], 1)
        self.assertTrue(self.client.get('/api/notifications/').json()['results'][1]['is_read'])

    def test_cannot_read_someone_elses_notification(self):
        theirs = Notification.objects.get(recipient=self.bob, channel='IN_APP')
        self.assertEqual(self.post(f'/api/notifications/{theirs.pk}/read/').status_code, 404)
        theirs.refresh_from_db()
        self.assertIsNone(theirs.read_at)

    def test_mark_all_read_only_touches_my_rows(self):
        self.assertEqual(self.post('/api/notifications/read-all/').json(), {'marked': 2})
        self.assertEqual(Notification.objects.filter(recipient=self.bob, read_at__isnull=True).count(), 1)

    def test_writes_need_csrf(self):
        first = Notification.objects.filter(recipient=self.alice).first()
        self.assertEqual(self.client.post(f'/api/notifications/{first.pk}/read/').status_code, 403)

    def test_email_rows_never_appear_in_the_inbox(self):
        notify([self.alice], 'instrument_submitted', {'reference': 'R3'}, 'e3')  # alice has no address: inbox only
        get_user_model().objects.filter(pk=self.alice.pk).update(email='alice@example.org')
        self.alice.refresh_from_db()
        notify([self.alice], 'instrument_submitted', {'reference': 'R4'}, 'e4')
        self.assertEqual(self.client.get('/api/notifications/').json()['count'], 4)

    def test_delivery_status_is_auditor_only_and_has_no_message_content(self):
        self.assertEqual(self.client.get('/api/notifications/delivery-status/').status_code, 403)
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get('/api/notifications/delivery-status/').status_code, 403)
        self.client.force_login(self.auditor)
        response = self.client.get('/api/notifications/delivery-status/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['counts'], {'PENDING': 0, 'SENT': 0, 'FAILED': 0})

    def test_delivery_status_surfaces_failures_without_message_bodies(self):
        get_user_model().objects.filter(pk=self.alice.pk).update(email='alice@example.org')
        self.alice.refresh_from_db()
        notify([self.alice], 'instrument_submitted', {'reference': 'SECRET-REF'}, 'e9')
        Notification.objects.filter(channel='EMAIL').update(status='FAILED', attempts=5, last_error='OSError: down')
        self.client.force_login(self.auditor)
        body = self.client.get('/api/notifications/delivery-status/').json()
        self.assertEqual(body['counts']['FAILED'], 1)
        self.assertEqual(body['failures'][0]['last_error'], 'OSError: down')
        self.assertNotIn('SECRET-REF', str(body))
