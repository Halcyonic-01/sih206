"""Scan stored documents that have not been scanned (or all of them) with ClamAV; quarantine the infected ones."""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from portal import scanning
from portal.models import Document


class Command(BaseCommand):
    help = ('Scan documents with status PENDING (or every document with --all) through the configured clamd. An infected '
            'file is marked REJECTED (quarantined) and can no longer be downloaded. Nothing is deleted.')

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Rescan documents that are already CLEAN as well.')

    def handle(self, *args, all=False, **options):
        if not scanning.configured():
            raise CommandError('No scanner configured. Set CLAMAV_HOST (and CLAMAV_PORT) first.')
        documents = Document.objects.exclude(scan_status='REJECTED')
        if not all:
            documents = documents.filter(scan_status='PENDING')
        counts = {'clean': 0, 'quarantined': 0, 'unreadable': 0}
        for document in documents.order_by('pk').iterator():
            try:
                with document.file.open('rb') as stored:
                    clean, signature = scanning.scan_chunks(iter(lambda: stored.read(1024 * 1024), b''))
            except FileNotFoundError:
                counts['unreadable'] += 1
                self.stderr.write(f'document {document.pk}: file is missing')
                continue
            except scanning.ScannerUnavailable as error:
                raise CommandError(f'{error} Stopped at document {document.pk}; run it again when the scanner is back.') from None
            Document.objects.filter(pk=document.pk).update(
                scan_status='CLEAN' if clean else 'REJECTED', scan_detail='' if clean else signature,
                scanned_at=timezone.now())
            counts['clean' if clean else 'quarantined'] += 1
            if not clean:
                self.stderr.write(f'document {document.pk}: QUARANTINED ({signature})')
        self.stdout.write(', '.join(f'{count} {label}' for label, count in counts.items()))
        if counts['quarantined'] or counts['unreadable']:
            raise CommandError('Some documents need attention; see the messages above.')
