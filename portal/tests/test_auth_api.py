from django.core.cache import cache
from django.test import Client, override_settings
from portal.tests.common import PortalTestCase


@override_settings(ROOT_URLCONF='config.urls')
class SessionApiTests(PortalTestCase):
    def setUp(self):
        cache.clear()

    def test_csrf_login_session_role_and_logout(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get('/api/auth/me/').status_code, 401)
        body = {'username': self.a.username, 'password': 'Testing-Only-7jS!'}
        self.assertEqual(client.post('/api/auth/login/', body, content_type='application/json').status_code, 403)
        token = client.get('/api/auth/csrf/').json()['csrfToken']
        response = client.post('/api/auth/login/', body, content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['institution_id'], self.institution_a.pk)
        self.assertEqual(client.get('/api/auth/me/').json()['role'], 'institution')
        self.assertEqual(client.post('/api/auth/logout/').status_code, 403)
        token = client.get('/api/auth/csrf/').json()['csrfToken']
        self.assertEqual(client.post('/api/auth/logout/', HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertEqual(client.get('/api/auth/me/').status_code, 401)

    def test_bad_credentials_bad_input_and_throttle(self):
        self.assertEqual(self.client.post('/api/auth/login/', [], content_type='application/json').status_code, 400)
        for _ in range(4):
            self.assertEqual(self.client.post('/api/auth/login/', {'username': 'unknown', 'password': 'wrong'}, content_type='application/json').status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login/', {'username': 'unknown', 'password': 'wrong'}, content_type='application/json').status_code, 429)
