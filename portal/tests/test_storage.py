import hashlib
import shutil
import tempfile
from io import StringIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from config.documentkey import generate_key, key_id, parse_key
from portal import storage
from portal.models import Document
from .common import PortalTestCase
from .pdf_fixture import sample_pdf

KEY, OTHER = generate_key(), generate_key()


class EncryptionPrimitivesTests(SimpleTestCase):
    @override_settings(DOCUMENT_ENCRYPTION_KEY=KEY, DOCUMENT_ENCRYPTION_OLD_KEYS=[])
    def test_round_trip_is_authenticated_and_bound_to_the_storage_name(self):
        blob = storage.encrypt('1/a.pdf', b'%PDF-synthetic')
        self.assertTrue(storage.is_encrypted(blob))
        self.assertNotIn(b'synthetic', blob)
        self.assertEqual(storage.decrypt('1/a.pdf', blob), b'%PDF-synthetic')
        with self.assertRaises(storage.DocumentDecryptionError):
            storage.decrypt('2/other.pdf', blob)            # copied over another record's file
        with self.assertRaises(storage.DocumentDecryptionError):
            storage.decrypt('1/a.pdf', blob[:-1] + bytes([blob[-1] ^ 1]))  # one flipped bit
        with self.assertRaises(storage.DocumentDecryptionError):
            storage.decrypt('1/a.pdf', blob[:30])           # truncated

    @override_settings(DOCUMENT_ENCRYPTION_KEY=KEY, DOCUMENT_ENCRYPTION_OLD_KEYS=[])
    def test_every_file_gets_its_own_key_and_nonce(self):
        self.assertNotEqual(storage.encrypt('a', b'same'), storage.encrypt('a', b'same'))

    def test_a_wrong_or_malformed_key_is_refused(self):
        with override_settings(DOCUMENT_ENCRYPTION_KEY=KEY, DOCUMENT_ENCRYPTION_OLD_KEYS=[]):
            blob = storage.encrypt('a', b'data')
        with override_settings(DOCUMENT_ENCRYPTION_KEY=OTHER, DOCUMENT_ENCRYPTION_OLD_KEYS=[]):
            with self.assertRaises(storage.DocumentDecryptionError):
                storage.decrypt('a', blob)
        with override_settings(DOCUMENT_ENCRYPTION_KEY=OTHER, DOCUMENT_ENCRYPTION_OLD_KEYS=[KEY]):
            self.assertEqual(storage.decrypt('a', blob), b'data')   # an old key still opens it
        with self.assertRaises(Exception):
            parse_key('too-short')

    def test_rewrap_moves_a_file_to_the_current_key_without_touching_the_body(self):
        with override_settings(DOCUMENT_ENCRYPTION_KEY=KEY, DOCUMENT_ENCRYPTION_OLD_KEYS=[]):
            blob = storage.encrypt('a', b'data')
            self.assertIsNone(storage.rewrap(blob, 'a'))
        with override_settings(DOCUMENT_ENCRYPTION_KEY=OTHER, DOCUMENT_ENCRYPTION_OLD_KEYS=[KEY]):
            moved = storage.rewrap(blob, 'a')
            self.assertEqual(moved[8:12], key_id(parse_key(OTHER)))
            self.assertEqual(moved[74:], blob[74:])  # header is 8 + 4 + 2 + 60 bytes; the nonce and ciphertext are unchanged
        with override_settings(DOCUMENT_ENCRYPTION_KEY=OTHER, DOCUMENT_ENCRYPTION_OLD_KEYS=[]):
            self.assertEqual(storage.decrypt('a', moved), b'data')  # the old key is no longer needed


class EncryptedStorageTests(SimpleTestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.settings = override_settings(DOCUMENT_ENCRYPTION_KEY=KEY, DOCUMENT_ENCRYPTION_OLD_KEYS=[],
                                          DOCUMENT_ALLOW_PLAINTEXT=True)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.store = storage.EncryptedFileSystemStorage(location=self.root)

    def test_what_is_on_disk_is_not_the_pdf_and_reads_return_it(self):
        name = self.store.save('1/doc.pdf', ContentFile(sample_pdf()))
        on_disk = Path(self.root, name).read_bytes()
        self.assertNotIn(b'%PDF-', on_disk)
        with self.store.open(name) as stored:
            self.assertEqual(stored.read(), sample_pdf())

    def test_plaintext_files_still_open_until_plaintext_is_disallowed(self):
        Path(self.root, 'legacy.pdf').write_bytes(sample_pdf())
        with self.store.open('legacy.pdf') as stored:
            self.assertEqual(stored.read(), sample_pdf())
        with override_settings(DOCUMENT_ALLOW_PLAINTEXT=False):
            with self.assertRaises(storage.DocumentDecryptionError):
                self.store.open('legacy.pdf')

    def test_a_tampered_file_fails_to_open(self):
        name = self.store.save('1/doc.pdf', ContentFile(sample_pdf()))
        path = Path(self.root, name)
        blob = bytearray(path.read_bytes())
        blob[-5] ^= 0xFF
        path.write_bytes(bytes(blob))
        with self.assertRaises(storage.DocumentDecryptionError):
            self.store.open(name)


class EncryptDocumentsCommandTests(PortalTestCase):
    def setUp(self):
        super().setUp()
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def run_command(self, store, *args):
        out = StringIO()
        with self.settings(DOCUMENT_ENCRYPTION_KEY=KEY, DOCUMENT_ENCRYPTION_OLD_KEYS=[]), \
                __import__('unittest.mock', fromlist=['patch']).patch('portal.management.commands.encrypt_documents.default_storage', store):
            call_command('encrypt_documents', *args, stdout=out, stderr=StringIO())
        return out.getvalue()

    def test_encrypts_existing_plaintext_files_once_and_is_idempotent(self):
        store = storage.EncryptedFileSystemStorage(location=self.root)
        with self.settings(MEDIA_ROOT=self.root, DOCUMENT_ENCRYPTION_KEY=KEY, DOCUMENT_ENCRYPTION_OLD_KEYS=[]):
            document = Document.objects.create(
                instrument=self.draft(with_document=False), kind='FDR', original_name='x.pdf', size_bytes=len(sample_pdf()),
                sha256=hashlib.sha256(sample_pdf()).hexdigest(), uploaded_by=self.a, file='9/plain.pdf')
        Path(self.root, '9').mkdir()
        Path(self.root, '9/plain.pdf').write_bytes(sample_pdf())
        self.assertIn('1 encrypted', self.run_command(store, '--dry-run'))
        self.assertEqual(Path(self.root, '9/plain.pdf').read_bytes(), sample_pdf())
        self.assertIn('1 encrypted', self.run_command(store))
        self.assertTrue(storage.is_encrypted(Path(self.root, '9/plain.pdf').read_bytes()))
        self.assertIn('1 current', self.run_command(store))
        with self.settings(DOCUMENT_ENCRYPTION_KEY=KEY, DOCUMENT_ENCRYPTION_OLD_KEYS=[]):
            self.assertEqual(storage.decrypt(document.file.name, Path(self.root, '9/plain.pdf').read_bytes()), sample_pdf())

    def test_a_file_that_no_longer_matches_its_hash_is_reported_and_left_alone(self):
        store = storage.EncryptedFileSystemStorage(location=self.root)
        Document.objects.create(instrument=self.draft(with_document=False), kind='FDR', original_name='x.pdf', size_bytes=3,
                                sha256='0' * 64, uploaded_by=self.a, file='9/bad.pdf')
        Path(self.root, '9').mkdir()
        Path(self.root, '9/bad.pdf').write_bytes(b'tampered')
        with self.assertRaises(CommandError):
            self.run_command(store)
        self.assertEqual(Path(self.root, '9/bad.pdf').read_bytes(), b'tampered')

    def test_refuses_to_run_when_encryption_is_off(self):
        with self.assertRaisesMessage(CommandError, 'encryption is off'):
            call_command('encrypt_documents', stdout=StringIO(), stderr=StringIO())


class EndToEndEncryptionTests(PortalTestCase):
    """Upload through the application, check the disk, download through the application."""

    def test_uploaded_pdf_is_encrypted_on_disk_and_downloads_unchanged(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        storages = {'default': {'BACKEND': 'portal.storage.EncryptedFileSystemStorage'},
                    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
        with self.settings(MEDIA_ROOT=root, STORAGES=storages, DOCUMENT_ENCRYPTION_KEY=KEY, DOCUMENT_ENCRYPTION_OLD_KEYS=[],
                           DOCUMENT_ALLOW_PLAINTEXT=False):
            record = self.draft()
            document = record.documents.get()
            self.assertEqual(document.sha256, hashlib.sha256(sample_pdf()).hexdigest())  # the hash is over the plaintext
            on_disk = Path(root, document.file.name).read_bytes()
            self.assertNotIn(b'%PDF-', on_disk)
            self.assertTrue(storage.is_encrypted(on_disk))
            self.client.force_login(self.a)
            response = self.client.get(f'/api/documents/{document.pk}/download/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), sample_pdf())
            response.close()
            with document.file.open('rb') as stored:  # what OCR and AI extraction use
                self.assertEqual(stored.read(), sample_pdf())
