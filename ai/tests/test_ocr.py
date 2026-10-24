from io import BytesIO
from pathlib import Path
import subprocess
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from PIL import Image, ImageDraw, ImageFont

from ai.models import AiRun
from ai.ocr import extract_local, parse_fields, tool_path
from portal.tests.common import PortalTestCase


class OcrParsingTests(SimpleTestCase):
    def test_conflicts_low_confidence_invalid_values_and_missing_labels_stay_unknown(self):
        pages = [{'page': 1, 'confidence': 90, 'text': 'Amount: 1,234.50\nIssue Date: 24/10/2026\nIFSC: ABCD0123456\nReference: FIRST'},
                 {'page': 2, 'confidence': 90, 'text': 'Reference: SECOND\nMaturity Date: 31/02/2027'},
                 {'page': 3, 'confidence': 30, 'text': 'Bank: unreliable'}]
        result = parse_fields(pages)['fields']
        self.assertEqual(result['amount']['value'], '1234.50')
        self.assertEqual(result['issue_date']['value'], '2026-10-24')
        for key in ('reference', 'bank', 'maturity_date'):
            self.assertIsNone(result[key]['value'])


@override_settings(ROOT_URLCONF='config.urls', OCR_ENABLED=True)
class LocalOcrTests(PortalTestCase):
    def test_scope_role_and_disabled_never_start_worker(self):
        item = self.draft()
        path = f'/api/documents/{item.documents.get().pk}/ocr/'
        with override_settings(OCR_ENABLED=False), patch('ai.ocr.subprocess.run') as worker:
            self.assertEqual(self.client.post(path).json()['status'], 'disabled')
            worker.assert_not_called()
        self.client.force_login(self.b)
        self.assertEqual(self.client.post(path).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(path).status_code, 403)

    def test_timeout_missing_engine_and_tampering_fall_back_without_mutation(self):
        item = self.draft()
        doc = item.documents.get()
        before = (item.status, item.version, item.verification_level)
        with patch('ai.ocr.tool_path', return_value=None):
            self.assertEqual(extract_local(self.a, doc)['code'], 'OCR_NOT_CONFIGURED')
        with patch('ai.ocr.tool_path', return_value='synthetic'), patch('ai.ocr.subprocess.run', side_effect=subprocess.TimeoutExpired('test', 45)):
            self.assertEqual(extract_local(self.a, doc)['code'], 'TIMEOUT')
        doc.sha256 = '0'*64
        with patch('ai.ocr.tool_path', return_value='synthetic'), patch('ai.ocr.subprocess.run') as worker:
            self.assertEqual(extract_local(self.a, doc)['code'], 'DOCUMENT_INTEGRITY')
            worker.assert_not_called()
        item.refresh_from_db()
        self.assertEqual(before, (item.status, item.version, item.verification_level))

    def test_real_engine_reads_image_only_pdf_when_available(self):
        if not tool_path('OCR_TESSERACT', 'tesseract') or not tool_path('OCR_PDFTOPPM', 'pdftoppm'):
            self.skipTest('Native OCR tools are optional; install Tesseract and Poppler for this integration check.')
        image = Image.new('RGB', (1800, 1000), 'white')
        font_path = Path('C:/Windows/Fonts/arial.ttf')
        font = ImageFont.truetype(str(font_path), 40) if font_path.exists() else ImageFont.load_default(size=40)
        draw = ImageDraw.Draw(image)
        lines = ['SYNTHETIC OCR TEST - NOT A BANK DOCUMENT', 'Reference: SYNTHETIC-001',
                 'Bank: Fictional Bank', 'Amount: 500000.25', 'Issue Date: 2026-01-01',
                 'Maturity Date: 2027-01-01', 'IFSC: ABCD0123456']
        for index, line in enumerate(lines):
            draw.text((60, 60+index*100), line, font=font, fill='black')
        stream = BytesIO()
        image.save(stream, format='PDF', resolution=150)
        self.pdf = lambda name='scan.pdf': SimpleUploadedFile(name, stream.getvalue(), content_type='application/pdf')
        item = self.draft()
        result = extract_local(self.a, item.documents.get())
        self.assertEqual(result['status'], 'success', result)
        self.assertEqual(result['fields']['reference']['value'], 'SYNTHETIC-001')
        self.assertEqual(result['fields']['amount']['value'], '500000.25')
        self.assertEqual(result['fields']['issue_date']['page'], 1)
        self.assertEqual(AiRun.objects.get().operation, 'LOCAL_OCR')
