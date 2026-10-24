"""Explicit synthetic smoke check. No claim of representative/held-out accuracy."""
import json
from decimal import Decimal
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from ai.ocr import extract_local
from ai.services import extract
from ai.synthetic import EXPECTED
from portal.models import Document


class Command(BaseCommand):
    help = 'Evaluate the seeded synthetic scan locally or, with explicit consent, using the configured AI provider.'

    def add_arguments(self, parser):
        parser.add_argument('--engine', choices=['ocr', 'ai'], default='ocr')
        parser.add_argument('--allow-external', action='store_true')

    def handle(self, **options):
        if not settings.DEBUG:
            raise CommandError('This synthetic smoke command is restricted to local DEBUG mode.')
        document = Document.objects.filter(instrument__reference=EXPECTED['reference'],
            original_name='synthetic-ocr-evaluation.pdf').select_related('instrument__created_by').first()
        if not document:
            raise CommandError('Run seed_ocr_example first.')
        if options['engine'] == 'ai' and not options['allow_external']:
            raise CommandError('AI sends the synthetic PDF externally. Pass --allow-external to authorize this run.')
        actor = document.instrument.created_by
        result = extract_local(actor, document) if options['engine'] == 'ocr' else extract(actor, document, consent=True, synthetic=True)
        if result['status'] != 'success':
            raise CommandError(result.get('detail', 'Extraction unavailable.'))
        correct = {}
        for key, expected in EXPECTED.items():
            actual = result['fields'][key]['value']
            correct[key] = Decimal(actual) == Decimal(expected) if key == 'amount' and actual else actual == expected
        self.stdout.write(json.dumps({'engine': options['engine'], 'synthetic_smoke_only': True,
            'fields_correct': sum(correct.values()), 'fields_total': len(correct), 'checks': correct}))
        if not all(correct.values()):
            raise CommandError('Synthetic smoke check has mismatches; inspect the source pages manually.')
