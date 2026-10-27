from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone

from access.models import IdempotentRequest
from portal.models import Instrument
from portal.tests.common import PortalTestCase

KEY = 'a1b2c3d4-key-0001'


class IdempotencyTests(PortalTestCase):
    def create(self, key=KEY, user=None, **overrides):
        self.client.force_login(user or self.a)
        extra = {'HTTP_IDEMPOTENCY_KEY': key} if key else {}
        return self.client.post('/api/instruments/', self.payload(**overrides), content_type='application/json', **extra)

    def test_a_repeated_create_returns_the_first_answer_and_creates_nothing_new(self):
        first = self.create()
        again = self.create()
        self.assertEqual((first.status_code, again.status_code), (201, 201))
        self.assertEqual(again.json(), first.json())
        self.assertEqual(again['Idempotent-Replay'], 'true')
        self.assertNotIn('Idempotent-Replay', first)
        self.assertEqual(Instrument.objects.count(), 1)

    def test_without_the_header_nothing_changes(self):
        self.assertEqual(self.create(key=None).status_code, 201)
        self.assertEqual(self.create(key=None, reference='DEMO-FDR-002').status_code, 201)
        self.assertEqual(Instrument.objects.count(), 2)
        self.assertFalse(IdempotentRequest.objects.exists())

    def test_the_same_key_with_a_different_body_is_a_conflict(self):
        self.create()
        response = self.create(reference='DEMO-FDR-OTHER')
        self.assertEqual((response.status_code, response.json()['code']), (409, 'idempotency_key_reused'))
        self.assertEqual(Instrument.objects.count(), 1)

    def test_keys_belong_to_a_user(self):
        self.create()
        other = self.create(user=self.b)
        self.assertEqual(other.status_code, 201)
        self.assertEqual(Instrument.objects.count(), 2)

    def test_failures_are_not_stored_so_a_retry_runs_again(self):
        bad = self.create(bank='')
        self.assertEqual(bad.status_code, 400)
        self.assertFalse(IdempotentRequest.objects.exists())
        self.assertEqual(self.create(bank='Fictional Bank').status_code, 201)

    def test_a_request_still_running_is_a_conflict_not_a_second_run(self):
        IdempotentRequest.objects.create(user=self.a, key=KEY, fingerprint='0' * 64)
        self.client.force_login(self.a)
        response = self.client.post('/api/instruments/', self.payload(), content_type='application/json', HTTP_IDEMPOTENCY_KEY=KEY)
        self.assertEqual(response.status_code, 409)
        self.assertIn(response.json()['code'], {'request_in_progress', 'idempotency_key_reused'})

    def test_a_malformed_key_is_refused_and_unauthenticated_requests_still_get_401(self):
        self.assertEqual(self.create(key='short').status_code, 400)
        self.client.logout()
        response = self.client.post('/api/instruments/', self.payload(), content_type='application/json', HTTP_IDEMPOTENCY_KEY=KEY)
        self.assertEqual(response.status_code, 401)

    def test_uploads_are_covered_without_reading_the_body(self):
        self.client.force_login(self.a)
        data = self.payload() | {'document': self.pdf()}
        first = self.client.post('/api/instruments/', data, HTTP_IDEMPOTENCY_KEY='upload-key-0001')
        data = self.payload() | {'document': self.pdf()}
        again = self.client.post('/api/instruments/', data, HTTP_IDEMPOTENCY_KEY='upload-key-0001')
        self.assertEqual((first.status_code, again.status_code), (201, 201))
        self.assertEqual(Instrument.objects.count(), 1)

    def test_old_records_are_cleaned_up(self):
        self.create()
        IdempotentRequest.objects.update(created_at=timezone.now() - timedelta(hours=25))
        call_command('cleanup_idempotency', stdout=StringIO())
        self.assertFalse(IdempotentRequest.objects.exists())

    def test_an_expired_key_can_be_used_again(self):
        self.create()
        IdempotentRequest.objects.update(created_at=timezone.now() - timedelta(hours=25))
        self.assertEqual(self.create(reference='DEMO-FDR-NEW').status_code, 201)
