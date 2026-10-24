from io import BytesIO
import subprocess
from unittest.mock import patch

import pikepdf
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from portal import services
from portal.models import Document
from portal.uploads import validate_pdf_upload
from .common import PortalTestCase
from .pdf_fixture import sample_pdf


class PdfValidationTests(PortalTestCase):
    def pdf_bytes(self, kind):
        stream = BytesIO()
        with pikepdf.Pdf.new() as pdf:
            pdf.add_blank_page()
            if kind == 'javascript':
                pdf.Root.OpenAction = pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS='app.alert(1)')
            if kind == 'embedded':
                pdf.attachments['synthetic.txt'] = b'SYNTHETIC'
            options = {'encryption': pikepdf.Encryption(owner='synthetic', user='synthetic')} if kind == 'encrypted' else {}
            pdf.save(stream, **options)
        return stream.getvalue()

    def test_safe_upload_preserves_bytes_and_records_page_count(self):
        record = self.draft()
        self.assertEqual(record.documents.get().page_count, 1)
        upload = self.pdf()
        self.assertIs(validate_pdf_upload(upload), upload)
        self.assertEqual(upload.read(), sample_pdf())

    def test_encrypted_active_embedded_and_malformed_documents_are_rejected(self):
        for kind in ['javascript', 'embedded', 'encrypted', 'malformed']:
            content = b'%PDF-1.7\nnot a real body\n%%EOF' if kind == 'malformed' else self.pdf_bytes(kind)
            with self.subTest(kind=kind), self.assertRaises(ValidationError):
                validate_pdf_upload(SimpleUploadedFile('synthetic.pdf', content, content_type='application/pdf'))
        self.assertFalse(Document.objects.exists())

    def test_timeout_and_worker_failure_are_safe_validation_errors(self):
        for failure in [subprocess.TimeoutExpired('synthetic', 10), OSError('private path')]:
            with patch('portal.uploads.subprocess.run', side_effect=failure), self.assertRaises(ValidationError) as error:
                validate_pdf_upload(self.pdf())
            self.assertNotIn('private path', str(error.exception))

    def test_page_bound_checked_by_http_and_service_without_partial_writes(self):
        item = self.submitted()
        document = item.documents.get()
        before = item.audit_events.count()
        self.client.force_login(self.officer)
        response = self.client.post(reverse('observation_add', args=[item.pk]), {
            'version': item.version, 'document': document.pk, 'page_number': 2,
            'severity': 'BLOCKING', 'comment': 'Synthetic observation'})
        self.assertEqual(response.status_code, 400)
        with self.assertRaises(services.WorkflowError):
            services.add_observation(self.officer, item.pk, item.version, document, 2, 'BLOCKING', 'Synthetic')
        item.refresh_from_db()
        self.assertEqual(item.audit_events.count(), before)
        self.assertFalse(item.observations.exists())
