import hashlib
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from portal.models import Document, Instrument
from .common import PortalTestCase
from .pdf_fixture import sample_pdf


class DocumentTests(PortalTestCase):
    def test_protected_download_returns_original_bytes_and_safe_headers(self):
        record = self.draft()
        doc = record.documents.get()
        self.assertEqual(doc.sha256, hashlib.sha256(sample_pdf()).hexdigest())
        response = self.client.get(reverse('document_download', args=[doc.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), sample_pdf())
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertNotIn('synthetic.pdf', doc.file.name)
        self.assertEqual(self.client.get('/media/' + doc.file.name).status_code, 404)

    def test_invalid_uploads_are_rejected(self):
        self.client.force_login(self.a)
        cases = [
            SimpleUploadedFile('fake.pdf', b'not a pdf', content_type='application/pdf'),
            SimpleUploadedFile('wrong.txt', sample_pdf(), content_type='application/pdf'),
            SimpleUploadedFile('wrong.pdf', sample_pdf(), content_type='text/html'),
            SimpleUploadedFile('truncated.pdf', b'%PDF-1.4\ntruncated', content_type='application/pdf'),
        ]
        for upload in cases:
            with self.subTest(name=upload.name):
                response = self.client.post(reverse('instrument_create'), self.payload(document=upload))
                self.assertEqual(response.status_code, 200)
                self.assertIn('document', response.context['form'].errors)
        self.assertFalse(Document.objects.exists())
        self.assertFalse(Instrument.objects.exists())

    @override_settings(MAX_UPLOAD_BYTES=20)
    def test_oversized_upload_rejected(self):
        self.client.force_login(self.a)
        response = self.client.post(reverse('instrument_create'), self.payload(document=self.pdf()))
        self.assertIn('document', response.context['form'].errors)
        self.assertFalse(Document.objects.exists())

    def test_stale_upload_does_not_store_orphan_file(self):
        record = self.draft()
        before = set(Path(self.storage_dir).rglob('*.pdf'))
        response = self.client.post(reverse('instrument_edit', args=[record.pk]), self.payload(
            version=record.version + 10, document=self.pdf('stale.pdf')))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(set(Path(self.storage_dir).rglob('*.pdf')), before)
        self.assertEqual(record.documents.count(), 1)

    def test_failed_audit_rolls_back_document_and_removes_stored_file(self):
        self.client.force_login(self.a)
        before = set(Path(self.storage_dir).rglob('*.pdf'))
        with patch('portal.services.event', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('instrument_create'), self.payload(document=self.pdf()))
        self.assertFalse(Instrument.objects.exists())
        self.assertFalse(Document.objects.exists())
        self.assertEqual(set(Path(self.storage_dir).rglob('*.pdf')), before)
