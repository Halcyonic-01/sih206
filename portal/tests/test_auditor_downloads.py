from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import override_settings
from django.urls import reverse

from access.models import AccessLog
from notifications.models import Notification
from portal.permissions import AUDITOR_GROUP
from portal.tests.common import PortalTestCase


class AuditorDownloadTests(PortalTestCase):
    def setUp(self):
        self.auditor = get_user_model().objects.create_user(username='auditor', password='x')
        self.auditor.groups.add(Group.objects.get_or_create(name=AUDITOR_GROUP)[0])
        self.record = self.submitted()
        self.document = self.record.documents.get()
        self.url = f'/api/documents/{self.document.pk}/download/'

    def get(self, user, url=None, **extra):
        self.client.force_login(user)
        return self.client.get(url or self.url, **extra)

    def test_an_auditor_sees_metadata_and_hashes_without_a_reason(self):
        self.client.force_login(self.auditor)
        body = self.client.get(f'/api/instruments/{self.record.pk}/').json()
        self.assertEqual(body['documents'][0]['sha256'], self.document.sha256)

    def test_the_file_needs_a_reason_and_the_reason_is_logged(self):
        refused = self.get(self.auditor)
        self.assertEqual((refused.status_code, refused.json()['code']), (403, 'download_reason_required'))
        self.assertFalse(AccessLog.objects.filter(action='DOCUMENT_DOWNLOAD', user=self.auditor).exists())
        for short in ('', 'too short', 'x' * 301):
            self.assertEqual(self.get(self.auditor, self.url, QUERY_STRING=f'reason={short}').status_code, 403)
        ok = self.get(self.auditor, self.url, QUERY_STRING='reason=Annual audit sample 12')
        self.assertEqual(ok.status_code, 200)
        ok.close()
        row = AccessLog.objects.get(action='DOCUMENT_DOWNLOAD', user=self.auditor)
        self.assertIn('auditor reason: Annual audit sample 12', row.detail)

    def test_the_reason_may_come_in_a_header(self):
        ok = self.get(self.auditor, HTTP_X_DOWNLOAD_REASON='Complaint 2026/44 review')
        self.assertEqual(ok.status_code, 200)
        ok.close()

    def test_other_roles_are_not_asked_and_are_not_logged_with_a_reason(self):
        for user in (self.a, self.officer):
            response = self.get(user)
            self.assertEqual(response.status_code, 200)
            response.close()
        self.assertFalse(AccessLog.objects.filter(detail__contains='auditor reason').exists())

    def test_the_legacy_download_asks_too(self):
        legacy = reverse('document_download', args=[self.document.pk])
        self.assertEqual(self.get(self.auditor, legacy).status_code, 403)
        ok = self.get(self.auditor, legacy, QUERY_STRING='reason=Annual audit sample 12')
        self.assertEqual(ok.status_code, 200)
        ok.close()

    @override_settings(AUDITOR_DOWNLOAD_NOTIFY=True)
    def test_officers_can_be_told_and_only_once_per_reason(self):
        for _ in range(2):
            self.get(self.auditor, self.url, QUERY_STRING='reason=Annual audit sample 12').close()
        rows = Notification.objects.filter(template_id='auditor_document_download', recipient=self.officer)
        self.assertEqual(rows.count(), 1)
        self.assertIn('Annual audit sample 12', rows.get().body)

    def test_officers_are_not_told_unless_switched_on(self):
        self.get(self.auditor, self.url, QUERY_STRING='reason=Annual audit sample 12').close()
        self.assertFalse(Notification.objects.filter(template_id='auditor_document_download').exists())
