from datetime import date
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from ai.synthetic import EXPECTED, scanned_pdf
from portal.models import Instrument
from portal.services import save_draft


class Command(BaseCommand):
    help = 'Add one clearly labelled synthetic image-only PDF for OCR rehearsal; never replace existing data.'

    def handle(self, **options):
        if not settings.DEBUG:
            raise CommandError('Synthetic seeding requires local DEBUG mode.')
        owner = get_user_model().objects.filter(username='institution_a').first()
        if not owner:
            raise CommandError('Run seed_demo first.')
        item = Instrument.objects.filter(reference=EXPECTED['reference']).first()
        if not item:
            values = EXPECTED | {'amount': Decimal(EXPECTED['amount']), 'issue_date': date(2026, 1, 1),
                'maturity_date': date(2027, 1, 1), 'document': SimpleUploadedFile(
                    'synthetic-ocr-evaluation.pdf', scanned_pdf(), content_type='application/pdf')}
            item = save_draft(owner, values)
        self.stdout.write(f'Synthetic OCR record {item.pk}; document {item.documents.first().pk}. Existing records are unchanged.')
