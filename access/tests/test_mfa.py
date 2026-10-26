import time
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from access import mfa, totp
from access.models import AccessLog, MfaDevice
from portal.permissions import AUTHORITY_GROUP
from portal.tests.common import PortalTestCase


class TotpTests(SimpleTestCase):
    def test_matches_the_rfc_6238_sha1_vectors(self):
        secret = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'  # ASCII "12345678901234567890"
        for moment, expected in ((59, '287082'), (1111111109, '081804'), (1234567890, '005924'), (2000000000, '279037')):
            self.assertEqual(totp.code_for(secret, moment // 30), expected)

    def test_window_replay_and_malformed_codes(self):
        secret = totp.new_secret()
        now = 1_700_000_000
        step = now // 30
        good = totp.code_for(secret, step)
        self.assertEqual(totp.verify(secret, good, now=now), step)
        self.assertEqual(totp.verify(secret, totp.code_for(secret, step - 1), now=now), step - 1)  # clock drift of one step
        self.assertIsNone(totp.verify(secret, totp.code_for(secret, step - 3), now=now))
        self.assertIsNone(totp.verify(secret, good, now=now, last_step=step))                       # a code is single use
        for bad in ('', '12345', '1234567', 'abcdef', None):
            self.assertIsNone(totp.verify(secret, bad, now=now))
        self.assertTrue(totp.provisioning_uri(secret, 'a b', 'Pramaan').startswith('otpauth://totp/Pramaan:a%20b?secret='))


class MfaApiTests(PortalTestCase):
    password = 'Testing-Only-7jS!'

    def setUp(self):
        super().setUp()
        self.authority = get_user_model().objects.create_user(username='authority', password=self.password)
        self.authority.groups.add(Group.objects.get_or_create(name=AUTHORITY_GROUP)[0])
        self.enrol(self.officer)

    def enrol(self, user, secret=None):
        secret = secret or totp.new_secret()
        MfaDevice.objects.create(user=user, secret=secret, confirmed_at=timezone.now())
        return secret

    def code(self, user):
        device = MfaDevice.objects.get(user=user)
        return totp.code_for(device.secret, int(time.time() // 30))

    def password_login(self, user, password=None):
        return self.client.post('/api/auth/login/', {'username': user.username, 'password': password or self.password},
                                content_type='application/json')

    def test_password_alone_does_not_sign_in_a_user_with_a_device(self):
        response = self.password_login(self.officer)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {'mfa_required': True})
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        self.assertEqual(self.client.get('/api/instruments/').status_code, 401)

    def test_a_valid_code_completes_the_sign_in_and_counts_as_a_recent_check(self):
        self.password_login(self.officer)
        response = self.client.post('/api/auth/mfa/verify/', {'code': self.code(self.officer)}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['mfa']['verified_recently'])
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)
        self.assertTrue(AccessLog.objects.filter(action='MFA_LOGIN', user=self.officer).exists())

    def test_wrong_codes_are_refused_logged_and_end_the_attempt_after_five(self):
        self.password_login(self.officer)
        for _ in range(5):
            response = self.client.post('/api/auth/mfa/verify/', {'code': '000000'}, content_type='application/json')
            self.assertEqual(response.json()['code'], 'invalid_mfa_code')
        self.assertEqual(AccessLog.objects.filter(action='MFA_FAILED').count(), 5)
        self.assertEqual(self.client.post('/api/auth/mfa/verify/', {'code': self.code(self.officer)},
                                          content_type='application/json').json()['code'], 'mfa_pending_expired')

    def test_five_wrong_codes_lock_the_device_even_for_a_correct_code(self):
        for _ in range(5):
            self.password_login(self.officer)
            self.client.post('/api/auth/mfa/verify/', {'code': '000000'}, content_type='application/json')
        self.password_login(self.officer)
        response = self.client.post('/api/auth/mfa/verify/', {'code': self.code(self.officer)}, content_type='application/json')
        self.assertEqual((response.status_code, response.json()['code']), (429, 'mfa_locked'))

    def test_a_code_cannot_be_used_twice(self):
        code = self.code(self.officer)
        self.password_login(self.officer)
        self.assertEqual(self.client.post('/api/auth/mfa/verify/', {'code': code}, content_type='application/json').status_code, 200)
        self.client.post('/api/auth/logout/')
        self.password_login(self.officer)
        self.assertEqual(self.client.post('/api/auth/mfa/verify/', {'code': code}, content_type='application/json').status_code, 400)

    def test_without_a_device_nothing_changes_unless_mfa_is_required(self):
        response = self.password_login(self.authority)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mfa'], {'in_scope': True, 'enrolled': False, 'required': False, 'verified_recently': False})
        self.assertEqual(self.client.get('/api/instruments/').status_code, 200)

    @override_settings(MFA_REQUIRED=True)
    def test_when_required_an_unenrolled_staff_user_can_only_reach_the_auth_endpoints(self):
        self.password_login(self.authority)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)
        blocked = self.client.get('/api/instruments/')
        self.assertEqual((blocked.status_code, blocked.json()['code']), (403, 'mfa_enrolment_required'))
        setup = self.client.post('/api/auth/mfa/setup/', content_type='application/json').json()
        wrong = self.client.post('/api/auth/mfa/confirm/', {'code': '123456'}, content_type='application/json')
        self.assertEqual(wrong.status_code, 400)
        good = totp.code_for(setup['secret'], int(time.time() // 30))
        self.assertEqual(self.client.post('/api/auth/mfa/confirm/', {'code': good}, content_type='application/json').status_code, 200)
        self.assertEqual(self.client.get('/api/instruments/').status_code, 200)
        self.assertEqual(self.client.post('/api/auth/mfa/disable/', {'code': good}, content_type='application/json').status_code, 403)

    def test_institution_users_cannot_enrol(self):
        self.client.force_login(self.a)
        self.assertEqual(self.client.post('/api/auth/mfa/setup/', content_type='application/json').status_code, 403)

    def test_correction_needs_a_recent_code_and_then_works(self):
        record = self.submitted()
        self.client.force_login(self.officer)             # a session with no recent code
        path = f'/api/instruments/{record.pk}/correct/'
        body = {'version': record.version, 'reference': record.reference, 'bank': 'Corrected Bank', 'amount': '500000.25',
                'issue_date': str(record.issue_date), 'maturity_date': str(record.maturity_date), 'reason': 'Typing error'}
        blocked = self.client.post(path, body, content_type='application/json')
        self.assertEqual((blocked.status_code, blocked.json()['code']), (403, 'mfa_step_up_required'))
        step = self.client.post('/api/auth/mfa/step-up/', {'code': self.code(self.officer)}, content_type='application/json')
        self.assertEqual(step.status_code, 200, step.content)
        self.assertNotEqual(self.client.post(path, body, content_type='application/json').status_code, 403)

    def test_the_step_up_window_expires(self):
        record = self.submitted()
        self.client.force_login(self.officer)
        session = self.client.session
        session[mfa.VERIFIED_AT] = int(time.time()) - 601
        session.save()
        response = self.client.post(f'/api/instruments/{record.pk}/correct/', {'version': record.version, 'reason': 'x'},
                                    content_type='application/json')
        self.assertEqual(response.json()['code'], 'mfa_step_up_required')

    def test_a_staff_member_without_a_device_is_not_asked_for_a_code(self):
        record = self.submitted()
        MfaDevice.objects.all().delete()
        self.client.force_login(self.officer)
        response = self.client.post(f'/api/instruments/{record.pk}/correct/', {'version': record.version, 'reason': 'x'},
                                    content_type='application/json')
        self.assertNotEqual(response.json().get('code'), 'mfa_step_up_required')

    def test_release_authorisation_letter_and_completion_need_a_recent_code(self):
        self.enrol(self.authority)
        self.client.force_login(self.authority)
        for action in ('approve', 'issue', 'complete'):
            response = self.client.post(f'/api/releases/999999/{action}', {'version': 1, 'reason': 'x'}, content_type='application/json')
            self.assertEqual((action, response.status_code, response.json()['code']), (action, 403, 'mfa_step_up_required'))
        self.client.post('/api/auth/mfa/step-up/', {'code': self.code(self.authority)}, content_type='application/json')
        response = self.client.post('/api/releases/999999/approve', {'version': 1, 'reason': 'x'}, content_type='application/json')
        self.assertEqual(response.status_code, 404)  # past the step-up; the case itself does not exist
        # Rejecting and reading are not step-up actions.
        self.assertNotEqual(self.client.post('/api/releases/999999/reject', {'version': 1, 'reason': 'x'},
                                             content_type='application/json').json().get('code'), 'mfa_step_up_required')

    def test_the_legacy_login_cannot_bypass_the_second_factor(self):
        response = self.client.post(reverse('login'), {'username': self.officer.username, 'password': self.password})
        self.assertContains(response, 'two-factor sign-in', status_code=200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_reset_command_removes_the_device_and_logs_it(self):
        call_command('mfa_reset', self.officer.username, '--reason', 'ticket 1', stdout=StringIO())
        self.assertFalse(MfaDevice.objects.filter(user=self.officer).exists())
        self.assertTrue(AccessLog.objects.filter(action='MFA_RESET').exists())
