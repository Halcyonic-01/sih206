import socketserver
import struct
import threading
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from portal import scanning
from portal.models import Document
from .common import PortalTestCase
from .pdf_fixture import sample_pdf

EICAR = b'EICAR-TEST-MARKER'


class FakeClamd(socketserver.ThreadingTCPServer):
    """Speaks just enough of clamd's zINSTREAM protocol: reports FOUND when the stream contains the marker."""
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, reply=None):
        self.reply, self.seen = reply, []
        super().__init__(('127.0.0.1', 0), self.Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()

    class Handler(socketserver.BaseRequestHandler):
        def read(self, count):
            data = b''
            while len(data) < count:
                piece = self.request.recv(count - len(data))
                if not piece:
                    raise ConnectionError
                data += piece
            return data

        def handle(self):
            command = b''
            while not command.endswith(b'\0'):
                command += self.request.recv(1)
            payload = b''
            while (size := struct.unpack('>I', self.read(4))[0]):
                payload += self.read(size)
            self.server.seen.append((command, len(payload)))
            reply = self.server.reply or (b'stream: Eicar-Test-Signature FOUND\0' if EICAR in payload else b'stream: OK\0')
            self.request.sendall(reply)

    @property
    def port(self):
        return self.server_address[1]


class ScannerClientTests(SimpleTestCase):
    def setUp(self):
        self.server = FakeClamd()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def use(self, **extra):
        return override_settings(CLAMAV_HOST='127.0.0.1', CLAMAV_PORT=self.server.port, CLAMAV_TIMEOUT=3,
                                 SCAN_REQUIRED=False, **extra)

    def test_clean_and_infected_streams(self):
        with self.use():
            self.assertEqual(scanning.scan_chunks([b'%PDF-1.4 ', b'hello']), (True, ''))
            clean, signature = scanning.scan_chunks([b'abc', EICAR])
        self.assertFalse(clean)
        self.assertEqual(signature, 'Eicar-Test-Signature')
        self.assertEqual(self.server.seen[0][0], b'zINSTREAM\0')

    def test_a_large_file_is_sent_in_pieces(self):
        with self.use():
            self.assertEqual(scanning.scan_chunks([b'x' * 300_000]), (True, ''))
        self.assertEqual(self.server.seen[0][1], 300_000)

    def test_an_error_reply_or_a_dead_scanner_is_unavailable_not_clean(self):
        self.server.reply = b'INSTREAM size limit exceeded. ERROR\0'
        with self.use(), self.assertRaises(scanning.ScannerUnavailable):
            scanning.scan_chunks([b'abc'])
        with override_settings(CLAMAV_HOST='127.0.0.1', CLAMAV_PORT=1, CLAMAV_TIMEOUT=1), self.assertRaises(scanning.ScannerUnavailable):
            scanning.scan_chunks([b'abc'])

    def test_upload_outcomes_depend_on_the_switch(self):
        upload = lambda body=b'%PDF-': SimpleUploadedFile('a.pdf', body, content_type='application/pdf')
        with self.use():
            self.assertEqual(scanning.scan_upload(upload()).scan_status, 'CLEAN')
            with self.assertRaisesMessage(ValidationError, 'rejected by the malware scan'):
                scanning.scan_upload(upload(EICAR))
        with override_settings(CLAMAV_HOST='', SCAN_REQUIRED=False):
            self.assertEqual(scanning.scan_upload(upload()).scan_status, 'PENDING')   # no scanner, not required: stored unscanned
        with override_settings(CLAMAV_HOST='', SCAN_REQUIRED=True), self.assertRaisesMessage(ValidationError, 'no scanner is configured'):
            scanning.scan_upload(upload())
        with override_settings(CLAMAV_HOST='127.0.0.1', CLAMAV_PORT=1, CLAMAV_TIMEOUT=1, SCAN_REQUIRED=True):
            with self.assertRaisesMessage(ValidationError, 'not available'):
                scanning.scan_upload(upload())                                           # required: fail closed
        with override_settings(CLAMAV_HOST='127.0.0.1', CLAMAV_PORT=1, CLAMAV_TIMEOUT=1, SCAN_REQUIRED=False):
            self.assertEqual(scanning.scan_upload(upload()).scan_status, 'PENDING')


class ScanOnUploadTests(PortalTestCase):
    def setUp(self):
        super().setUp()
        self.server = FakeClamd()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.scanner = override_settings(CLAMAV_HOST='127.0.0.1', CLAMAV_PORT=self.server.port, CLAMAV_TIMEOUT=3)
        self.scanner.enable()
        self.addCleanup(self.scanner.disable)

    def test_a_clean_upload_is_marked_clean_and_downloads(self):
        record = self.draft()
        document = record.documents.get()
        self.assertEqual(document.scan_status, 'CLEAN')
        self.assertIsNotNone(document.scanned_at)
        self.client.force_login(self.a)
        response = self.client.get(f'/api/documents/{document.pk}/download/')
        self.assertEqual(response.status_code, 200)
        response.close()
        body = self.client.get(f'/api/instruments/{record.pk}/').json()
        self.assertEqual(body['documents'][0]['scan_status'], 'CLEAN')

    def test_an_infected_upload_is_refused_and_nothing_is_stored(self):
        before = Document.objects.count()
        self.client.force_login(self.a)
        data = self.payload()
        data['document'] = SimpleUploadedFile('bad.pdf', sample_pdf() + EICAR, content_type='application/pdf')
        with override_settings(SCAN_REQUIRED=False):
            response = self.client.post('/api/instruments/', data)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(Document.objects.count(), before)

    def test_unscanned_and_quarantined_documents_are_not_served_when_scanning_is_required(self):
        record = self.draft()
        document = record.documents.get()
        self.client.force_login(self.a)
        Document.objects.filter(pk=document.pk).update(scan_status='PENDING')
        with override_settings(SCAN_REQUIRED=True):
            response = self.client.get(f'/api/documents/{document.pk}/download/')
            self.assertEqual((response.status_code, response.json()['code']), (409, 'document_not_scanned'))
            self.assertEqual(self.client.get(reverse('document_download', args=[document.pk])).status_code, 409)
        with override_settings(SCAN_REQUIRED=False):
            self.assertEqual(self.client.get(f'/api/documents/{document.pk}/download/').status_code, 200)
        Document.objects.filter(pk=document.pk).update(scan_status='REJECTED')
        with override_settings(SCAN_REQUIRED=False):
            response = self.client.get(f'/api/documents/{document.pk}/download/')
            self.assertEqual((response.status_code, response.json()['code']), (409, 'document_quarantined'))

    def test_scan_documents_command_marks_clean_and_quarantines(self):
        record = self.draft()
        good = record.documents.get()
        Document.objects.filter(pk=good.pk).update(scan_status='PENDING', scanned_at=None)
        out = StringIO()
        call_command('scan_documents', stdout=out, stderr=StringIO())
        good.refresh_from_db()
        self.assertEqual(good.scan_status, 'CLEAN')
        self.assertIn('1 clean', out.getvalue())
        with good.file.storage.open(good.file.name) as stored:
            pass  # the file is still there; nothing is deleted
        with override_settings(CLAMAV_HOST=''), self.assertRaisesMessage(CommandError, 'No scanner configured'):
            call_command('scan_documents', stdout=StringIO(), stderr=StringIO())
