"""Compute first-page fingerprints for documents that have none (near-duplicate scan detection)."""
from django.core.management.base import BaseCommand, CommandError

from portal.models import Document
from verification import fingerprint


class Command(BaseCommand):
    help = 'Fingerprint documents that do not have one yet. Needs Poppler (pdftoppm); safe to repeat.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=500)

    def handle(self, *args, limit, **options):
        if not fingerprint.available():
            raise CommandError('Near-duplicate detection is off or pdftoppm (Poppler) is not installed.')
        done = failed = 0
        for document in Document.objects.filter(fingerprint__isnull=True).exclude(scan_status='REJECTED').order_by('pk')[:limit]:
            if fingerprint.ensure(document):
                done += 1
            else:
                failed += 1
        self.stdout.write(f'{done} fingerprinted, {failed} could not be read.')
