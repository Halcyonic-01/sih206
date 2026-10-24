from django.test import Client, override_settings

from portal import services
from portal.models import Document, Instrument
from .common import PortalTestCase


@override_settings(ROOT_URLCONF='config.urls')
class RecordsApiTests(PortalTestCase):
    def post(self, path, data):
        return self.client.post(path, data, content_type='application/json')

    def path(self, item, action=''):
        return f'/api/instruments/{item.pk}/' + (action + '/' if action else '')

    def test_create_and_edit_derive_owner_and_preserve_locking(self):
        self.client.force_login(self.a)
        response = self.post('/api/instruments/', self.payload())
        self.assertEqual(response.status_code, 201, response.content)
        item = Instrument.objects.get()
        self.assertEqual(item.institution, self.institution_a)
        self.assertTrue(response.json()['actions']['can_edit'])
        response = self.client.patch(self.path(item), {'version': item.version, 'branch': 'Synthetic branch'}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['branch'], 'Synthetic branch')
        stale = self.client.patch(self.path(item), {'version': item.version, 'branch': 'stale'}, content_type='application/json')
        self.assertEqual(stale.status_code, 409)
        self.client.force_login(self.officer)
        self.assertEqual(self.post('/api/instruments/', self.payload()).status_code, 403)

    def test_server_controlled_fields_and_bad_amount_rejected(self):
        self.client.force_login(self.a)
        for extra in [{'amount': '-1'}, {'verification_level': 'CONFIRMED'},
                      {'institution_id': self.institution_b.pk}, {'mode': 'OTHER'},
                      {'mode': 'RTGS', 'utr': ''}]:
            with self.subTest(extra=extra):
                self.assertEqual(self.post('/api/instruments/', self.payload(**extra)).status_code, 400)
        self.assertFalse(Instrument.objects.exists())

    def test_list_search_pagination_export_and_dashboard_are_scoped(self):
        own = self.draft()
        other = self.draft(user=self.b)
        other.reference = 'PRIVATE-OTHER'
        other.save()
        self.client.force_login(self.a)
        result = self.client.get('/api/instruments/?q=DEMO&page_size=1').json()
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['results'][0]['id'], own.pk)
        for path in ['/api/instruments/', '/api/instruments/export.csv', '/api/dashboard/']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('PRIVATE-OTHER', response.content.decode())
        for query in ['page=0', 'page=abc', 'page_size=101', 'category=bad', 'maturity_from=no']:
            self.assertEqual(self.client.get('/api/instruments/?' + query).status_code, 400)

    def test_other_institution_cannot_read_write_or_download(self):
        item = self.draft()
        document = item.documents.get()
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(self.path(item)).status_code, 404)
        self.assertEqual(self.client.patch(self.path(item), {'version': 1}, content_type='application/json').status_code, 404)
        self.assertEqual(self.client.get(f'/api/documents/{document.pk}/download/').status_code, 404)
        for action in ['submit', 'review', 'observations', 'renew', 'documents', 'correct']:
            with self.subTest(action=action):
                self.assertEqual(self.post(self.path(item, action), {'version': 1}).status_code, 404)

    def test_submission_and_review_actions_require_versions_and_roles(self):
        item = self.draft()
        self.assertEqual(self.post(self.path(item, 'submit'), {}).status_code, 400)
        self.assertEqual(self.post(self.path(item, 'submit'), {'version': 999}).status_code, 409)
        response = self.post(self.path(item, 'submit'), {'version': item.version})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['notification_queued'])
        item.refresh_from_db()
        data = {'version': item.version, 'decision': 'accept', 'reason': 'Synthetic review'}
        self.assertEqual(self.post(self.path(item, 'review'), data).status_code, 403)
        self.client.force_login(self.officer)
        self.assertEqual(self.post(self.path(item, 'review'), {'version': item.version}).status_code, 400)
        self.assertEqual(self.post(self.path(item, 'review'), data | {'version': 999}).status_code, 409)
        response = self.post(self.path(item, 'review'), data)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], 'ACCEPTED')

    def test_observation_resolution_and_correction_are_audited(self):
        item = self.submitted()
        self.client.force_login(self.officer)
        payload = {'version': item.version, 'document': item.documents.get().pk,
                   'page_number': 1, 'severity': 'BLOCKING', 'comment': 'Synthetic discrepancy'}
        self.assertEqual(self.post(self.path(item, 'observations'), payload | {'page_number': 2}).status_code, 409)
        self.assertEqual(self.post(self.path(item, 'observations'), payload).status_code, 200)
        item.refresh_from_db()
        self.assertEqual(self.post(self.path(item, 'observations'), payload).status_code, 409)
        observation = item.observations.get()
        path = self.path(item, f'observations/{observation.pk}/resolve')
        self.assertEqual(self.post(path, {'version': 999, 'resolution': 'Synthetic check'}).status_code, 409)
        self.assertEqual(self.post(path, {'version': item.version, 'resolution': 'Synthetic check'}).status_code, 200)
        item.refresh_from_db()
        path = self.path(item, 'correct')
        self.assertEqual(self.post(path, {'version': item.version, 'bank': 'Changed'}).status_code, 400)
        self.assertEqual(self.post(path, {'version': 999, 'bank': 'Changed', 'reason': 'Correction'}).status_code, 409)
        self.assertEqual(self.post(path, {'version': item.version, 'bank': 'Changed', 'reason': 'Correction'}).status_code, 200)
        self.assertTrue(item.audit_events.filter(action='OFFICER_CORRECTION').exists())

    def test_typed_upload_and_download_preserve_original_evidence(self):
        item = self.draft()
        path = self.path(item, 'documents')
        self.assertEqual(self.client.post(path, {'version': 999, 'kind': 'PAYMENT_PROOF', 'document': self.pdf()}).status_code, 409)
        self.assertEqual(self.client.post(path, {'version': item.version, 'kind': 'NOC', 'document': self.pdf()}).status_code, 400)
        response = self.client.post(path, {'version': item.version, 'kind': 'PAYMENT_PROOF', 'document': self.pdf()})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(item.documents.count(), 2)
        document = item.documents.get(kind='PAYMENT_PROOF')
        self.assertEqual(document.page_count, 1)
        response = self.client.get(f'/api/documents/{document.pk}/download/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF-'))
        response.close()

    def test_renewal_creates_linked_draft_with_stale_and_denied_guards(self):
        item = self.submitted()
        item = services.review(self.officer, item.pk, item.version, 'accept', 'Synthetic review')
        payload = self.payload(reference='SYNTHETIC-RENEWAL', version=item.version)
        self.client.force_login(self.a)
        self.assertEqual(self.post(self.path(item, 'renew'), payload | {'version': 999}).status_code, 409)
        response = self.post(self.path(item, 'renew'), payload)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Instrument.objects.get(pk=response.json()['id']).predecessor_id, item.pk)
        self.client.force_login(self.officer)
        self.assertEqual(self.post(self.path(item, 'renew'), payload).status_code, 403)

    def test_session_csrf_enforced_and_anonymous_denied(self):
        self.client.logout()
        self.assertIn(self.client.get('/api/instruments/').status_code, [401, 403])
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.a)
        self.assertEqual(browser.post('/api/instruments/', self.payload(), content_type='application/json').status_code, 403)
