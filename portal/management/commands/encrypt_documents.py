"""Encrypt stored documents that were written before encryption was on, and move files to the current master key."""
import hashlib

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

from portal import storage
from portal.models import Document


class Command(BaseCommand):
    help = ('Encrypt plaintext document files and re-wrap files held under an old master key. Idempotent; a file whose '
            'content no longer matches its recorded SHA-256 is reported and left untouched.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report what would change without writing.')

    def handle(self, *args, dry_run=False, **options):
        if not isinstance(default_storage, storage.EncryptedFileSystemStorage):
            raise CommandError('Document encryption is off. Set DOCUMENT_ENCRYPTION_KEY first '
                               '(python -c "from config.documentkey import generate_key; print(generate_key())").')
        counts = {'encrypted': 0, 'rewrapped': 0, 'current': 0, 'missing': 0, 'problem': 0}
        for document in Document.objects.order_by('pk').iterator():
            name = document.file.name
            try:
                blob = default_storage.raw_bytes(name)
            except FileNotFoundError:
                counts['missing'] += 1
                self.stderr.write(f'document {document.pk}: file is missing')
                continue
            try:
                if storage.is_encrypted(blob):
                    updated = storage.rewrap(blob, name)
                    if updated is None:
                        counts['current'] += 1
                        continue
                    plaintext, kind = storage.decrypt(name, blob), 'rewrapped'
                else:
                    updated, plaintext, kind = None, blob, 'encrypted'
            except storage.DocumentDecryptionError as error:
                counts['problem'] += 1
                self.stderr.write(f'document {document.pk}: {error}')
                continue
            if hashlib.sha256(plaintext).hexdigest() != document.sha256:
                counts['problem'] += 1
                self.stderr.write(f'document {document.pk}: content does not match its recorded SHA-256; left unchanged')
                continue
            counts[kind] += 1
            if not dry_run:
                default_storage.replace_raw(name, updated if updated is not None else storage.encrypt(name, plaintext))
        suffix = ' (dry run, nothing written)' if dry_run else ''
        self.stdout.write(', '.join(f'{count} {label}' for label, count in counts.items()) + suffix)
        if counts['problem'] or counts['missing']:
            raise CommandError('Some documents need attention; see the messages above.')
