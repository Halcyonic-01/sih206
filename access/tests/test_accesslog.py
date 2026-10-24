import tempfile
from pathlib import Path
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from access.logging import log_access
from access.middleware import AccessLogMiddleware
from access.models import AccessLog, AppendOnlyError, UnitAssignment
from .base import PASSWORD, StaffTestCase


class DownloadAndExportLoggingTests(StaffTestCase):
    def test_document_download_is_logged_with_context(self):
        record = self.submitted()
        document = record.documents.get()
        self.client.force_login(self.officer)
        response = self.client.get(reverse('document_download', args=[document.pk]),
                                   HTTP_USER_AGENT='UnitTest/1.0', HTTP_X_REQUEST_ID='trace-abcdef12')
        self.assertEqual(response.status_code, 200)
        row = AccessLog.objects.get(action=AccessLog.DOCUMENT_DOWNLOAD)
        self.assertEqual((row.user, row.username), (self.officer, 'officer'))
        self.assertEqual((row.object_type, row.object_id), ('document', document.pk))
        self.assertEqual(row.user_agent, 'UnitTest/1.0')
        self.assertEqual(row.request_id, 'trace-abcdef12')
        self.assertEqual(row.ip_address, '127.0.0.1')
        self.assertEqual(AccessLog.objects.filter(action=AccessLog.DOWNLOAD).count(), 0)  # not logged twice

    def test_denied_or_missing_download_is_not_logged_as_access(self):
        record = self.submitted()
        document = record.documents.get()
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(reverse('document_download', args=[document.pk])).status_code, 404)
        self.assertEqual(AccessLog.objects.filter(action=AccessLog.DOCUMENT_DOWNLOAD).count(), 0)

    def test_export_is_logged_but_invalid_export_is_not(self):
        self.submitted()
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(reverse('instrument_export') + '?category=all').status_code, 200)
        row = AccessLog.objects.get(action=AccessLog.EXPORT)
        self.assertEqual(row.object_type, 'instrument_register')
        self.assertIn('rows=1', row.detail)
        self.assertEqual(self.client.get(reverse('instrument_export') + '?category=bogus').status_code, 400)
        self.assertEqual(AccessLog.objects.filter(action=AccessLog.EXPORT).count(), 1)


class MiddlewareFallbackTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='u1', password=PASSWORD)
        self.factory = RequestFactory()

    def run_middleware(self, path, *, user=None, status=200, method='GET', logged=False):
        request = getattr(self.factory, method.lower())(path)
        request.user = user if user is not None else self.user
        if logged:
            request.access_logged = True
        return AccessLogMiddleware(lambda r: HttpResponse('x', status=status))(request)

    def test_download_like_paths_are_logged(self):
        for path in ('/api/documents/5/download/', '/api/reports/pending.xlsx', '/api/instruments/export.csv',
                     '/api/releases/3/noc.pdf', '/api/reports/'):
            with self.subTest(path=path):
                before = AccessLog.objects.count()
                self.run_middleware(path)
                self.assertEqual(AccessLog.objects.count(), before + 1)
        self.assertEqual(AccessLog.objects.latest('pk').action, AccessLog.DOWNLOAD)

    def test_other_requests_are_not_logged(self):
        from django.contrib.auth.models import AnonymousUser
        self.run_middleware('/api/instruments/')
        self.run_middleware('/api/documents/5/download/', status=404)
        self.run_middleware('/api/documents/5/download/', method='POST')
        self.run_middleware('/api/documents/5/download/', user=AnonymousUser())
        self.run_middleware('/api/docs/', logged=False)
        self.run_middleware('/api/documents/5/download/', logged=True)
        self.assertEqual(AccessLog.objects.count(), 0)

    def test_log_access_unwraps_drf_requests_and_supports_anonymous(self):
        from django.contrib.auth.models import AnonymousUser
        http = self.factory.get('/api/public/verify/abc')
        http.user = AnonymousUser()

        class Wrapper:  # stands in for rest_framework.request.Request
            _request = http
        row = log_access(Wrapper(), AccessLog.NOC_VIEW, object_type='issuedletter', object_id=9)
        self.assertIsNone(row.user)
        self.assertEqual(row.username, '')
        self.assertTrue(http.access_logged)


class AuthEventLoggingTests(StaffTestCase):
    def csrf(self, client):
        return {'HTTP_X_CSRFTOKEN': client.get('/api/auth/csrf/').json()['csrfToken']}

    def test_login_logout_and_failed_login_are_logged(self):
        client = Client(enforce_csrf_checks=True)
        extra = self.csrf(client)
        client.post('/api/auth/login/', {'username': 'officer', 'password': 'wrong-password'},
                    content_type='application/json', **extra)
        failed = AccessLog.objects.get(action=AccessLog.LOGIN_FAILED)
        self.assertEqual(failed.username, 'officer')
        self.assertIsNone(failed.user)
        self.assertNotIn('wrong-password', str(failed.__dict__))
        client.post('/api/auth/login/', {'username': 'officer', 'password': PASSWORD},
                    content_type='application/json', **extra)
        login = AccessLog.objects.get(action=AccessLog.LOGIN)
        self.assertEqual(login.user, self.officer)
        client.post('/api/auth/logout/', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(AccessLog.objects.get(action=AccessLog.LOGOUT).user, self.officer)

    def test_unknown_username_failure_is_logged_without_user(self):
        client = Client(enforce_csrf_checks=True)
        client.post('/api/auth/login/', {'username': 'nobody', 'password': 'x'},
                    content_type='application/json', **self.csrf(client))
        self.assertEqual(AccessLog.objects.get(action=AccessLog.LOGIN_FAILED).username, 'nobody')


class AppendOnlyTests(StaffTestCase):
    def test_rows_cannot_be_changed_or_deleted(self):
        row = AccessLog.objects.create(user=self.officer, username='officer', action='X')
        row.detail = 'edited'
        with self.assertRaises(AppendOnlyError):
            row.save()
        with self.assertRaises(AppendOnlyError):
            row.delete()
        with self.assertRaises(AppendOnlyError):
            AccessLog.objects.filter(pk=row.pk).update(detail='edited')
        with self.assertRaises(AppendOnlyError):
            AccessLog.objects.all().delete()
        row.refresh_from_db()
        self.assertEqual(row.detail, '')


class SeedStaffTests(TestCase):
    def run_seed(self, base_dir, debug=True):
        (Path(base_dir) / 'data').mkdir(exist_ok=True)
        with override_settings(BASE_DIR=Path(base_dir), DEBUG=debug):
            out = StringIO()
            call_command('seed_staff', '--generate-password', stdout=out)
            return out.getvalue()

    def test_creates_accounts_units_and_private_credentials_once(self):
        with tempfile.TemporaryDirectory() as base:
            self.run_seed(base)
            User = get_user_model()
            self.assertEqual(User.objects.count(), 4)
            self.assertEqual(User.objects.get(username='clearance_grants').unit_assignment.unit, 'GRANTS')
            self.assertEqual(set(User.objects.get(username='auditor').groups.values_list('name', flat=True)), {'Auditor'})
            credentials = Path(base, 'data', 'staff-credentials.txt')
            self.assertTrue(credentials.exists())
            self.assertEqual(credentials.stat().st_mode & 0o077, 0)  # owner-only
            self.assertIn('nothing changed', self.run_seed(base))
            self.assertEqual(UnitAssignment.objects.count(), 3)

    def test_generated_passwords_refused_outside_debug(self):
        with tempfile.TemporaryDirectory() as base:
            with self.assertRaises(CommandError):
                self.run_seed(base, debug=False)
            self.assertEqual(get_user_model().objects.count(), 0)
