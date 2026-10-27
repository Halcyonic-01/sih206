import tempfile
from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from portal.models import Instrument
from portal.tests.common import PortalTestCase
from verification import fingerprint
from verification.models import DocumentFingerprint
from verification.services import checks

FIXTURES = Path(settings.BASE_DIR) / 'fixtures'


class DistanceTests(SimpleTestCase):
    def test_hamming_distance_between_hex_hashes(self):
        self.assertEqual(fingerprint.distance('0' * 256, '0' * 256), 0)
        self.assertEqual(fingerprint.distance('0' * 256, 'f' * 256), 1024)
        self.assertEqual(fingerprint.distance('0' * 254 + 'f0', '0' * 256), 4)


@skipUnless(fingerprint.available(), 'Poppler (pdftoppm) is not installed')
class NearDuplicateTests(PortalTestCase):
    def page(self, blocks):
        """A synthetic one-page PDF with black rectangles at the given positions."""
        from io import BytesIO
        from reportlab.pdfgen import canvas
        buffer = BytesIO()
        sheet = canvas.Canvas(buffer, pagesize=(400, 520))
        for x, y, w, h in blocks:
            sheet.rect(x, y, w, h, fill=1)
        sheet.save()
        return buffer.getvalue()

    SAME = [(30, 400, 300, 60), (30, 250, 200, 90), (60, 60, 280, 40)]
    OTHER = [(200, 420, 150, 80), (20, 300, 90, 120), (150, 40, 220, 160), (30, 30, 60, 60)]

    def upload(self, user, reference, blocks=None):
        self.client.force_login(user)
        response = self.client.post('/api/instruments/', self.payload(reference=reference) | {
            'document': SimpleUploadedFile('scan.pdf', self.page(blocks or self.SAME), content_type='application/pdf')})
        self.assertEqual(response.status_code, 201, response.content)
        return Instrument.objects.get(pk=response.json()['id'])

    def submit(self, record, user):
        self.client.force_login(user)
        self.client.post(f'/api/instruments/{record.pk}/submit/', {'version': record.version}, content_type='application/json')
        record.refresh_from_db()
        return record

    def fingerprint_all(self):
        from portal.models import Document
        for document in Document.objects.all():
            fingerprint.ensure(document)

    def test_the_same_scan_on_another_institutions_record_is_flagged_for_officers_only(self):
        mine = self.submit(self.upload(self.a, 'FDR-A'), self.a)
        theirs = self.submit(self.upload(self.b, 'FDR-B'), self.b)
        self.fingerprint_all()
        self.assertEqual(DocumentFingerprint.objects.count(), 2)
        flagged = {f['code']: f for f in checks(self.officer, mine)}
        self.assertIn('NEAR_DUPLICATE_SCAN', flagged)
        match = flagged['NEAR_DUPLICATE_SCAN']['values']['matches'][0]
        self.assertEqual((match['instrument_id'], match['difference_bits']), (theirs.pk, 0))
        self.assertNotIn('NEAR_DUPLICATE_SCAN', {f['code'] for f in checks(self.a, mine)})   # the institution never sees it

    def test_a_different_document_is_not_flagged(self):
        mine = self.submit(self.upload(self.a, 'FDR-A'), self.a)
        self.submit(self.upload(self.b, 'FDR-B', blocks=self.OTHER), self.b)
        self.fingerprint_all()
        self.assertNotIn('NEAR_DUPLICATE_SCAN', {f['code'] for f in checks(self.officer, mine)})

    def test_the_same_institution_is_not_flagged_unless_the_other_record_was_released(self):
        first = self.submit(self.upload(self.a, 'FDR-A1'), self.a)
        second = self.submit(self.upload(self.a, 'FDR-A2'), self.a)
        self.fingerprint_all()
        self.assertNotIn('NEAR_DUPLICATE_SCAN', {f['code'] for f in checks(self.officer, second)})
        from django.utils import timezone
        from portal import services
        services.review(self.officer, first.pk, first.version, 'accept', 'Synthetic review')
        Instrument.objects.filter(pk=first.pk).update(released_at=timezone.now())
        self.assertIn('NEAR_DUPLICATE_SCAN', {f['code'] for f in checks(self.officer, second)})

    def test_an_unreadable_document_just_has_no_fingerprint(self):
        record = self.upload(self.a, 'FDR-A')
        document = record.documents.get()
        DocumentFingerprint.objects.all().delete()
        with open(document.file.path, 'wb') as stored:
            stored.write(b'not a pdf')
        self.assertIsNone(fingerprint.ensure(document))
        self.assertFalse(DocumentFingerprint.objects.exists())
