import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.models import Institution, Instrument, UserProfile
from portal.permissions import INSTITUTION_GROUP, OFFICER_GROUP
from .pdf_fixture import sample_pdf


class PortalTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.storage_dir = tempfile.mkdtemp(prefix='fdr-tests-')
        cls.storage_override = override_settings(MEDIA_ROOT=cls.storage_dir)
        cls.storage_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.storage_override.disable()
        try:
            shutil.rmtree(cls.storage_dir)
        finally:
            super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        institution_group = Group.objects.create(name=INSTITUTION_GROUP)
        officer_group = Group.objects.create(name=OFFICER_GROUP)
        cls.institution_a = Institution.objects.create(code='A', name='Fictional A')
        cls.institution_b = Institution.objects.create(code='B', name='Fictional B')
        cls.a = User.objects.create_user(username='institution_a', password='Testing-Only-7jS!')
        cls.b = User.objects.create_user(username='institution_b', password='Testing-Only-7jS!')
        cls.officer = User.objects.create_user(username='officer', password='Testing-Only-7jS!')
        cls.a.groups.add(institution_group)
        cls.b.groups.add(institution_group)
        cls.officer.groups.add(officer_group)
        UserProfile.objects.create(user=cls.a, institution=cls.institution_a)
        UserProfile.objects.create(user=cls.b, institution=cls.institution_b)

    def payload(self, **overrides):
        data = {'reference': 'DEMO-FDR-001', 'bank': 'Fictional Bank', 'amount': '500000.25',
                'issue_date': '2026-01-01', 'maturity_date': '2027-01-01'}
        data.update(overrides)
        return data

    def pdf(self, name='synthetic.pdf'):
        return SimpleUploadedFile(name, sample_pdf(), content_type='application/pdf')

    def draft(self, with_document=True, user=None):
        self.client.force_login(user or self.a)
        data = self.payload()
        if with_document:
            data['document'] = self.pdf()
        response = self.client.post(reverse('instrument_create'), data)
        self.assertEqual(response.status_code, 302)
        return Instrument.objects.latest('pk')

    def submitted(self):
        record = self.draft()
        response = self.client.post(reverse('instrument_submit', args=[record.pk]), {'version': record.version})
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        return record
