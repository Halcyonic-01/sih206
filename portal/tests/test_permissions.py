from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from portal.permissions import OFFICER_GROUP
from .common import PortalTestCase


class PermissionTests(PortalTestCase):
    def test_anonymous_cannot_access_records_or_documents(self):
        record = self.submitted()
        doc = record.documents.get()
        self.client.logout()
        for name, args in [('instrument_list', []), ('instrument_detail', [record.pk]),
                           ('document_download', [doc.pk]), ('instrument_create', [])]:
            with self.subTest(name=name):
                response = self.client.get(reverse(name, args=args))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse('login')))

    def test_cross_institution_read_edit_submit_and_download_fail(self):
        record = self.submitted()
        self.client.force_login(self.b)
        self.assertNotContains(self.client.get(reverse('instrument_list')), record.reference)
        for name in ['instrument_detail', 'instrument_edit']:
            self.assertEqual(self.client.get(reverse(name, args=[record.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('instrument_edit', args=[record.pk]),
                                         self.payload(version=record.version)).status_code, 404)
        self.assertEqual(self.client.post(reverse('instrument_submit', args=[record.pk]),
                                         {'version': record.version}).status_code, 404)
        self.assertEqual(self.client.get(reverse('document_download',
                                                 args=[record.documents.get().pk])).status_code, 404)

    def test_institution_cannot_review(self):
        record = self.submitted()
        response = self.client.post(reverse('instrument_review', args=[record.pk]), {
            'version': record.version, 'decision': 'accept', 'reason': 'Unauthorized.',
        })
        self.assertEqual(response.status_code, 403)

    def test_officer_cannot_create_edit_submit_or_read_unsubmitted_drafts(self):
        record = self.draft()
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(reverse('instrument_create')).status_code, 403)
        self.assertEqual(self.client.get(reverse('instrument_edit', args=[record.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('instrument_submit', args=[record.pk]),
                                         {'version': record.version}).status_code, 403)
        self.assertEqual(self.client.get(reverse('instrument_detail', args=[record.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('document_download',
                                                 args=[record.documents.get().pk])).status_code, 404)

    def test_institution_id_and_status_cannot_be_forged(self):
        self.client.force_login(self.a)
        self.client.post(reverse('instrument_create'), self.payload(
            institution=self.institution_b.pk, status='ACCEPTED', amount_paise='1', created_by=self.officer.pk))
        from portal.models import Instrument
        record = Instrument.objects.get()
        self.assertEqual(record.institution, self.institution_a)
        self.assertEqual(record.status, Instrument.Status.DRAFT)
        self.assertEqual(record.created_by, self.a)
        self.assertEqual(record.amount_paise, 50000025)

    def test_unassigned_or_ambiguous_roles_fail_closed(self):
        outsider = get_user_model().objects.create_user(username='outsider')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse('instrument_list')).status_code, 403)
        self.a.groups.add(Group.objects.get(name=OFFICER_GROUP))
        self.client.force_login(self.a)
        self.assertEqual(self.client.get(reverse('instrument_list')).status_code, 403)

    def test_self_review_after_role_change_is_forbidden(self):
        record = self.submitted()
        self.a.groups.clear()
        self.a.groups.add(Group.objects.get(name=OFFICER_GROUP))
        self.client.force_login(self.a)
        response = self.client.post(reverse('instrument_review', args=[record.pk]), {
            'version': record.version, 'decision': 'accept', 'reason': 'Own submission.',
        })
        self.assertEqual(response.status_code, 403)
