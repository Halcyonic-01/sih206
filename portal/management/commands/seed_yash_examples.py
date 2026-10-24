"""Additional Y6/Y7 synthetic demo inputs; never alters an existing record."""
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from portal import services
from portal.models import Instrument


class Command(BaseCommand):
    help = 'Add two synthetic RTGS examples for statement preview/mismatch review.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Synthetic examples are restricted to local DEBUG mode.')
        try:
            owner = get_user_model().objects.get(username='institution_a')
        except get_user_model().DoesNotExist:
            raise CommandError('Run seed_demo first.') from None
        pdf = (settings.BASE_DIR / 'fixtures/sample-fdr.pdf').read_bytes()
        for suffix in ['MATCH', 'MISMATCH']:
            reference = f'YASH-RTGS-{suffix}'
            if Instrument.objects.filter(reference=reference).exists():
                self.stdout.write(f'{reference}: already exists; unchanged.')
                continue
            files = []
            try:
                with transaction.atomic():
                    item = services.save_draft(owner, {
                        'reference': reference, 'bank': 'Synthetic Bank - NOT A REAL INSTRUMENT',
                        'mode': 'RTGS', 'utr': f'YASH-SYNTHETIC-{suffix}', 'amount': Decimal('500000.25'),
                        'issue_date': date(2026, 10, 24), 'maturity_date': date(2027, 10, 24),
                        'document': SimpleUploadedFile('synthetic-payment.pdf', pdf, content_type='application/pdf')})
                    files = [doc.file for doc in item.documents.all()]
                    services.submit(owner, item.pk, item.version)
            except Exception:
                for file in files:
                    file.delete(save=False)
                raise
            self.stdout.write(f'{reference}: synthetic submitted example created.')
        self.stdout.write('Preview fixtures/synthetic-statement.csv as an officer. All results must remain labelled SIMULATED.')
