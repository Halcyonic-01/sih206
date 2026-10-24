import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import OperationalError
from django.test import Client, TestCase, override_settings
from rest_framework.test import APIRequestFactory

from portal.api.exceptions import exception_handler
from portal.models import Institution, UserProfile
from portal.permissions import AUTHORITY_GROUP, INSTITUTION_GROUP, OFFICER_GROUP
from portal.services import WorkflowError

PASSWORD = 'Testing-Only-7jS!'


class ApiTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        groups = {name: Group.objects.create(name=name) for name in (INSTITUTION_GROUP, OFFICER_GROUP, AUTHORITY_GROUP)}
        cls.institution = Institution.objects.create(code='A', name='Fictional A')
        cls.inst_user = User.objects.create_user(username='institution_a', password=PASSWORD)
        cls.inst_user.groups.add(groups[INSTITUTION_GROUP])
        UserProfile.objects.create(user=cls.inst_user, institution=cls.institution)
        cls.officer = User.objects.create_user(username='officer', password=PASSWORD)
        cls.officer.groups.add(groups[OFFICER_GROUP])
        cls.norole = User.objects.create_user(username='norole', password=PASSWORD)

    def setUp(self):
        cache.clear()  # the login throttle counts requests per minute in the cache

    def csrf_client(self):
        client = Client(enforce_csrf_checks=True)
        token = client.get('/api/auth/csrf/').json()['csrfToken']
        return client, {'HTTP_X_CSRFTOKEN': token}

    def login(self, client, extra, username='officer', password=PASSWORD):
        return client.post('/api/auth/login/', {'username': username, 'password': password},
                           content_type='application/json', **extra)


class AuthApiTests(ApiTestCase):
    def test_csrf_endpoint_sets_cookie_and_returns_token(self):
        response = Client().get('/api/auth/csrf/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('csrftoken', response.cookies)
        self.assertTrue(response.json()['csrfToken'])

    def test_login_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post('/api/auth/login/', {'username': 'officer', 'password': PASSWORD},
                               content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'permission_denied')

    def test_login_me_logout_round_trip(self):
        client, extra = self.csrf_client()
        self.assertEqual(client.get('/api/auth/me/').status_code, 401)
        response = self.login(client, extra, 'institution_a')
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body['role'], 'institution')
        self.assertEqual(body['institution']['code'], 'A')
        self.assertNotIn('password', body)
        me = client.get('/api/auth/me/')
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()['username'], 'institution_a')
        # A signed-in user must send the CSRF header to sign out.
        self.assertEqual(client.post('/api/auth/logout/').status_code, 403)
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post('/api/auth/logout/', HTTP_X_CSRFTOKEN=token).status_code, 204)
        self.assertEqual(client.get('/api/auth/me/').status_code, 401)

    def test_user_without_portal_role_gets_null_role(self):
        client, extra = self.csrf_client()
        self.assertEqual(self.login(client, extra, 'norole').json()['role'], None)

    def test_unauthenticated_me_uses_error_envelope(self):
        response = Client().get('/api/auth/me/')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['code'], 'not_authenticated')
        self.assertEqual(response['WWW-Authenticate'], 'Session')

    def test_bad_credentials_and_missing_fields(self):
        client, extra = self.csrf_client()
        bad = self.login(client, extra, 'officer', 'wrong-password')
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()['code'], 'invalid_credentials')
        unknown = self.login(client, extra, 'nobody', 'x')
        # The same message for unknown users and wrong passwords: no account enumeration.
        self.assertEqual(unknown.json()['detail'], bad.json()['detail'])
        missing = client.post('/api/auth/login/', {'username': 'officer'}, content_type='application/json', **extra)
        self.assertEqual(missing.status_code, 400)
        self.assertIn('password', missing.json()['errors'])

    def test_inactive_user_cannot_sign_in(self):
        get_user_model().objects.filter(username='officer').update(is_active=False)
        client, extra = self.csrf_client()
        self.assertEqual(self.login(client, extra).status_code, 400)

    def test_lockout_after_five_failures_even_with_correct_password(self):
        client, extra = self.csrf_client()
        for _ in range(4):
            self.assertEqual(self.login(client, extra, 'officer', 'wrong').status_code, 400)
        # The fifth failure locks the account.
        self.assertEqual(self.login(client, extra, 'officer', 'wrong').status_code, 429)
        locked = self.login(client, extra, 'officer', PASSWORD)
        self.assertEqual(locked.status_code, 429)
        self.assertEqual(locked.json()['code'], 'locked_out')
        # Another account from the same client is unaffected.
        self.assertEqual(self.login(client, extra, 'institution_a').status_code, 200)

    def test_successful_login_resets_failure_count(self):
        client, extra = self.csrf_client()
        for _ in range(4):
            self.login(client, extra, 'officer', 'wrong')
        self.assertEqual(self.login(client, extra).status_code, 200)
        client.post('/api/auth/logout/', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        extra = {'HTTP_X_CSRFTOKEN': client.get('/api/auth/csrf/').json()['csrfToken']}
        for _ in range(4):
            self.assertEqual(self.login(client, extra, 'officer', 'wrong').status_code, 400)

    def test_legacy_login_is_also_locked(self):
        client = Client()
        for _ in range(5):
            client.post('/legacy/accounts/login/', {'username': 'officer', 'password': 'wrong'})
        client.post('/legacy/accounts/login/', {'username': 'officer', 'password': PASSWORD})
        self.assertEqual(client.get('/legacy/').status_code, 302)  # still signed out


class ExceptionEnvelopeTests(TestCase):
    def handle(self, exc):
        request = APIRequestFactory().get('/api/x/')
        return exception_handler(exc, {'request': request, 'view': None})

    def test_workflow_error_is_conflict(self):
        response = self.handle(WorkflowError('This record changed. Reload it before trying again.'))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data, {'detail': 'This record changed. Reload it before trying again.',
                                         'code': 'conflict'})

    def test_permission_denied_keeps_service_message(self):
        response = self.handle(PermissionDenied('You cannot review your own submission.'))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['detail'], 'You cannot review your own submission.')

    def test_missing_rows_are_404_without_details(self):
        for exc in (ObjectDoesNotExist('Instrument matching query does not exist.'),):
            response = self.handle(exc)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.data['detail'], 'Not found.')

    def test_django_validation_error_maps_fields(self):
        response = self.handle(ValidationError({'reference': ['Required.']}))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors'], {'reference': ['Required.']})
        self.assertEqual(self.handle(ValidationError('Bad file.')).data['errors'], {'non_field_errors': ['Bad file.']})

    def test_database_errors_are_503_without_internals(self):
        response = self.handle(OperationalError('no such table: secret_table'))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret_table', str(response.data))

    def test_unknown_exception_is_left_to_django(self):
        self.assertIsNone(self.handle(RuntimeError('boom')))


class PlatformTests(ApiTestCase):
    def test_health(self):
        response = Client().get('/api/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

    def test_unknown_api_path_is_json_404(self):
        response = Client().get('/api/does-not-exist/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['code'], 'not_found')

    def test_request_id_is_returned_and_inbound_ids_are_sanitised(self):
        self.assertTrue(Client().get('/api/health/')['X-Request-ID'])
        self.assertEqual(Client().get('/api/health/', HTTP_X_REQUEST_ID='trace-12345678')['X-Request-ID'],
                         'trace-12345678')
        hostile = Client().get('/api/health/', HTTP_X_REQUEST_ID='x\r\nSet-Cookie: a=b')['X-Request-ID']
        self.assertNotIn('Set-Cookie', hostile)

    def test_security_headers(self):
        response = Client().get('/api/health/')
        policy = response['Content-Security-Policy']
        self.assertIn("script-src 'self'", policy)
        self.assertNotIn("script-src 'self' 'unsafe-inline'", policy)
        self.assertIn("frame-ancestors 'self'", policy)
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
        self.assertEqual(response['Referrer-Policy'], 'same-origin')
        self.assertIn('camera=()', response['Permissions-Policy'])
        self.assertIn('no-cache', response['Cache-Control'])

    def test_docs_follow_visibility_setting(self):
        with override_settings(API_DOCS_PUBLIC=False):
            self.assertEqual(Client().get('/api/docs/').status_code, 401)
            self.assertEqual(Client().get('/api/schema/').status_code, 401)
            client = Client()
            client.force_login(self.officer)
            self.assertEqual(client.get('/api/docs/').status_code, 200)
        with override_settings(API_DOCS_PUBLIC=True):
            docs = Client().get('/api/docs/')
            self.assertEqual(docs.status_code, 200)
            self.assertIn("'unsafe-inline'", docs['Content-Security-Policy'])
            self.assertNotIn('cdn.jsdelivr', docs.content.decode())

    def test_openapi_schema_builds_and_documents_auth(self):
        with override_settings(API_DOCS_PUBLIC=True):
            response = Client().get('/api/schema/?format=json')
        self.assertEqual(response.status_code, 200)
        paths = response.json()['paths']
        for route in ('/api/auth/csrf/', '/api/auth/login/', '/api/auth/logout/', '/api/auth/me/', '/api/health/'):
            self.assertIn(route, paths)

    def test_legacy_ui_moved_under_legacy_prefix(self):
        client = Client()
        self.assertEqual(client.get('/legacy/').status_code, 302)
        self.assertTrue(client.get('/legacy/').url.startswith('/legacy/accounts/login/'))
        self.assertEqual(client.get('/legacy/accounts/login/').status_code, 200)
        client.force_login(self.inst_user)
        self.assertEqual(client.get('/legacy/instruments/new/').status_code, 200)
        # The old path now belongs to the React router (here: no build present -> explanatory 503).
        with tempfile.TemporaryDirectory() as empty, override_settings(FRONTEND_DIST=Path(empty)):
            self.assertEqual(client.get('/instruments/new/').status_code, 503)

    def test_spa_fallback_serves_index_for_client_routes(self):
        with tempfile.TemporaryDirectory() as dist:
            Path(dist, 'index.html').write_text('<!doctype html><div id="root"></div>')
            with override_settings(FRONTEND_DIST=Path(dist)):
                for route in ('/', '/login', '/records/12/documents'):
                    response = Client().get(route)
                    self.assertEqual(response.status_code, 200, route)
                    self.assertIn(b'id="root"', response.content)
                    self.assertIn('no-cache', response['Cache-Control'])
                # Missing files are real 404s, never HTML.
                self.assertEqual(Client().get('/assets/missing.js').status_code, 404)
                self.assertEqual(Client().post('/login').status_code, 405)

    def test_spa_without_build_explains_how_to_build(self):
        with tempfile.TemporaryDirectory() as dist:
            with override_settings(FRONTEND_DIST=Path(dist)):
                response = Client().get('/')
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'npm ci', response.content)


class EnvFileTests(TestCase):
    def test_parse_handles_comments_quotes_and_export(self):
        from config.envfile import parse_env_text
        values = parse_env_text('# c\nA=1\nexport B="two words"\nC=\'x\'  \nD=val # note\nbad line\n1X=no\n')
        self.assertEqual(values, {'A': '1', 'B': 'two words', 'C': 'x', 'D': 'val'})

    def test_real_environment_wins_over_file(self):
        import os
        from config.envfile import load_env_file
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, '.env')
            path.write_text('K1_TEST_A=from-file\nK1_TEST_B=from-file\n')
            os.environ['K1_TEST_A'] = 'from-env'
            try:
                load_env_file(path)
                self.assertEqual(os.environ['K1_TEST_A'], 'from-env')
                self.assertEqual(os.environ['K1_TEST_B'], 'from-file')
            finally:
                os.environ.pop('K1_TEST_A', None)
                os.environ.pop('K1_TEST_B', None)

    def test_missing_file_is_fine(self):
        from config.envfile import load_env_file
        self.assertEqual(load_env_file('/nonexistent/.env'), {})


class StaticServingTests(TestCase):
    def test_whitenoise_hooks_are_callables_and_serve_the_build(self):
        from django.conf import settings
        self.assertTrue(callable(settings.WHITENOISE_ADD_HEADERS_FUNCTION))
        self.assertTrue(callable(settings.WHITENOISE_IMMUTABLE_FILE_TEST))
        headers = {}
        settings.WHITENOISE_ADD_HEADERS_FUNCTION(headers, 'index.html', '/index.html')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertTrue(settings.WHITENOISE_IMMUTABLE_FILE_TEST('x', '/assets/index-abc.js'))
        self.assertFalse(settings.WHITENOISE_IMMUTABLE_FILE_TEST('x', '/favicon.svg'))
