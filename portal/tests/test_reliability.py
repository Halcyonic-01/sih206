"""Operational failures must not expose data or partially commit workflow actions."""
from pathlib import Path
from unittest.mock import patch

from django.db import OperationalError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from portal.models import AuditEvent, Document, Instrument
from portal import releases, services
from portal.permissions import AUTHORITY_GROUP
from decimal import Decimal
from datetime import date
from .common import PortalTestCase


class ReliabilityTests(PortalTestCase):
    def test_database_failure_returns_safe_response_and_rolls_back_upload(self):
        self.client.force_login(self.a)
        files = set(Path(self.storage_dir).rglob('*.pdf'))
        with patch('portal.services.event', side_effect=OperationalError('SECRET SQL and applicant data')):
            response = self.client.post(reverse('instrument_create'), self.payload(document=self.pdf()))
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, 'SECRET SQL', status_code=503)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertFalse(Instrument.objects.exists())
        self.assertFalse(Document.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())
        self.assertEqual(set(Path(self.storage_dir).rglob('*.pdf')), files)

    def test_storage_failure_rolls_back_draft(self):
        self.client.force_login(self.a)
        with patch('django.core.files.storage.FileSystemStorage._save', side_effect=OSError('private disk path')):
            response = self.client.post(reverse('instrument_create'), self.payload(document=self.pdf()))
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, 'private disk path', status_code=503)
        self.assertFalse(Instrument.objects.exists())
        self.assertFalse(Document.objects.exists())

    def test_missing_and_unreadable_stored_documents(self):
        record = self.draft()
        doc = record.documents.get()
        path = reverse('document_download', args=[doc.pk])
        with patch('django.core.files.storage.FileSystemStorage._open', side_effect=PermissionError('private path')):
            response = self.client.get(path)
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, 'private path', status_code=503)
        doc.file.delete(save=False)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())

    def test_read_database_failure_does_not_expose_exception(self):
        self.client.force_login(self.a)
        with patch('portal.views.filter_instruments', side_effect=OperationalError('private SELECT')):
            response = self.client.get(reverse('instrument_list'))
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, 'private SELECT', status_code=503)

    def test_login_and_edit_forms_are_not_cached(self):
        response = self.client.get(reverse('login'))
        self.assertIn('no-store', response['Cache-Control'])
        record = self.draft()
        response = self.client.get(reverse('instrument_edit', args=[record.pk]))
        self.assertIn('no-store', response['Cache-Control'])

    def test_missing_required_fields_and_bad_document_have_no_side_effects(self):
        self.client.force_login(self.a)
        for missing in ('reference', 'bank', 'amount', 'issue_date', 'maturity_date'):
            payload = self.payload(document=self.pdf())
            payload.pop(missing)
            response = self.client.post(reverse('instrument_create'), payload)
            self.assertIn(missing, response.context['form'].errors)
        self.assertFalse(Instrument.objects.exists())
        self.assertFalse(Document.objects.exists())

    def test_signature_only_unreadable_file_is_not_automatically_accepted(self):
        # Y2 closes the old envelope-only limitation without recording a draft.
        self.client.force_login(self.a)
        upload = SimpleUploadedFile('unreadable.pdf', b'%PDF-1.7\nnot a PDF body\n%%EOF', content_type='application/pdf')
        response = self.client.post(reverse('instrument_create'), self.payload(document=upload))
        self.assertEqual(response.status_code, 200)
        self.assertIn('document', response.context['form'].errors)
        self.assertFalse(Instrument.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(action='ACCEPTED').exists())

    def test_database_failure_during_observation_keeps_version_and_findings(self):
        record = self.submitted()
        version, events = record.version, record.audit_events.count()
        self.client.force_login(self.officer)
        with patch('portal.services.event', side_effect=OperationalError('private SQL')):
            response = self.client.post(reverse('observation_add', args=[record.pk]), {
                'version': version, 'document': record.documents.get().pk, 'page_number': 1,
                'severity': 'BLOCKING', 'comment': 'Manual conflicting amount observation.',
            })
        self.assertEqual(response.status_code, 503)
        record.refresh_from_db()
        self.assertEqual(record.version, version)
        self.assertFalse(record.observations.exists())
        self.assertEqual(record.audit_events.count(), events)

    def test_completion_database_failure_preserves_authorization_and_removes_evidence(self):
        record = self.submitted()
        record = services.review(self.officer, record.pk, record.version, 'accept', 'Human review.')
        authority = get_user_model().objects.create_user(username='reliability_authority')
        authority.groups.add(Group.objects.get_or_create(name=AUTHORITY_GROUP)[0])
        request = releases.request_release(self.a, record.pk, record.version, 'Synthetic release.')
        record.refresh_from_db()
        releases.decide_release(authority, record.pk, request.pk, record.version, 'approve', 'Human assessment.')
        record.refresh_from_db()
        version, events = record.version, record.audit_events.count()
        files = set(Path(self.storage_dir).rglob('*.pdf'))
        self.client.force_login(authority)
        with patch('portal.releases.event', side_effect=OperationalError('private SQL')):
            response = self.client.post(reverse('release_completion', args=[record.pk, request.pk]), {
                'version': version, 'notes': 'Inspected synthetic evidence.', 'document': self.pdf(),
            })
        self.assertEqual(response.status_code, 503)
        record.refresh_from_db()
        request.refresh_from_db()
        self.assertEqual((record.version, request.status), (version, 'APPROVED'))
        self.assertIsNone(record.released_at)
        self.assertIsNone(request.completion_evidence_id)
        self.assertEqual(record.audit_events.count(), events)
        self.assertEqual(set(Path(self.storage_dir).rglob('*.pdf')), files)

    def test_renewal_database_failure_rolls_back_both_lifecycle_records(self):
        parent = self.submitted()
        parent = services.review(self.officer, parent.pk, parent.version, 'accept', 'Human review.')
        child = services.save_draft(self.a, {
            'reference': 'RELIABILITY-RENEWAL', 'bank': 'Fictional Bank', 'amount': Decimal('500000.25'),
            'issue_date': date(2026, 1, 1), 'maturity_date': date(2027, 1, 1),
            'predecessor_version': parent.version, 'document': self.pdf(),
        }, predecessor_id=parent.pk)
        child = services.submit(self.a, child.pk, child.version)
        self.client.force_login(self.officer)
        with patch('portal.services.event', side_effect=OperationalError('private SQL')):
            response = self.client.post(reverse('instrument_review', args=[child.pk]), {
                'version': child.version, 'decision': 'accept', 'reason': 'Human successor review.',
            })
        self.assertEqual(response.status_code, 503)
        parent.refresh_from_db()
        child.refresh_from_db()
        self.assertTrue(parent.is_current)
        self.assertEqual(child.status, 'SUBMITTED')
        self.assertFalse(parent.audit_events.filter(action='SUPERSEDED').exists())

    def test_failure_log_does_not_include_exception_message(self):
        self.client.force_login(self.a)
        with self.assertLogs('portal.middleware', level='WARNING') as logged:
            with patch('portal.views.filter_instruments', side_effect=OperationalError('SECRET applicant SQL')):
                self.assertEqual(self.client.get(reverse('instrument_list')).status_code, 503)
        self.assertNotIn('SECRET', ''.join(logged.output))
