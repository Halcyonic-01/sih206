"""Explicit synthetic smoke check. No claim of representative/held-out accuracy."""
import json
from pathlib import Path
from time import monotonic
from decimal import Decimal
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from ai.ocr import extract_local
from ai.services import extract
from ai.synthetic import EXPECTED
from portal.models import Document
from ai.evaluation import load_manifest, score_case, summarize, normalize


class Command(BaseCommand):
    help = 'Evaluate the seeded synthetic scan locally or, with explicit consent, using the configured AI provider.'

    def add_arguments(self, parser):
        parser.add_argument('--engine', choices=['ocr', 'ai', 'text'], default='ocr')
        parser.add_argument('--allow-external', action='store_true')
        parser.add_argument('--manifest')
        parser.add_argument('--output')
        parser.add_argument('--subset', choices=['all', 'tuning', 'heldout'], default='all')
        parser.add_argument('--validate-only', action='store_true')

    def handle(self, **options):
        if not settings.DEBUG:
            raise CommandError('This synthetic smoke command is restricted to local DEBUG mode.')
        if options['manifest']:
            return self.dataset(options)
        if options['engine'] == 'text':
            raise CommandError('The offline text baseline requires --manifest.')
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

    def dataset(self, options):
        from pypdf import PdfReader
        from ai.ocr import parse_fields
        from ai.services import ai_model
        path = Path(options['manifest'])
        data = load_manifest(path)
        if options['validate_only']:
            self.stdout.write(f"Validated {len(data['cases'])} synthetic PDFs, hashes and label contracts.")
            return
        if options['engine'] == 'ai' and not options['allow_external']:
            raise CommandError('External synthetic PDF transfer requires --allow-external.')
        rows = []
        for entry in data['cases']:
            if options['subset'] != 'all' and options['subset'] != entry['subset']:
                continue
            start = monotonic()
            if options['engine'] == 'text':
                # Baseline only, not a new product extraction engine or an OCR claim.
                pages = [{'page': n, 'confidence': 100, 'text': p.extract_text() or ''}
                         for n, p in enumerate(PdfReader(path.parent / entry['file']).pages, 1)]
                result = {'status': 'success', **parse_fields(pages), 'findings': []}
                result['findings'] = [{'code': 'AI_MISMATCH', 'field': k} for k, f in result['fields'].items()
                    if f['value'] is not None and normalize(k, f['value']) != normalize(k, entry['declared'][k])]
            else:
                doc = Document.objects.filter(sha256=entry['sha256'], instrument__reference=entry['declared']['reference']).select_related('instrument__created_by').first()
                if doc is None:
                    raise CommandError('Seed this corpus first using seed_extraction_evaluation.')
                actor = doc.instrument.created_by
                result = extract(actor, doc, consent=True, synthetic=True) if options['engine'] == 'ai' else extract_local(actor, doc)
                from ai.models import AiRun
                run = AiRun.objects.filter(document=doc, operation='DOCUMENT_EXTRACTION' if options['engine'] == 'ai' else 'LOCAL_OCR').latest('pk')
                result['run_id'] = run.pk
                result['evaluation_error_code'] = run.error_code
                # OCR intentionally has no product mismatch findings; do not invent any for its score.
            result['evaluation_duration_ms'] = round((monotonic() - start) * 1000)
            row = score_case(entry, result)
            row['error_code'] = result.get('evaluation_error_code', '')
            rows.append(row)
            self.stdout.write(f"{entry['id']}: {row['status']}; {len(row['errors'])} field/page errors")
        report = {'synthetic_only': True, 'independent_label_review': False,
            'engine': options['engine'], 'model': ai_model() if options['engine'] == 'ai' else None,
            'subset': options['subset'], 'cached': False, 'manifest_sha256': __import__('hashlib').sha256(path.read_bytes()).hexdigest(),
            'limitations': ['Small author-labelled synthetic set; no general accuracy claim.',
                'Existing provider/OCR rate limits apply; failures remain in denominators.',
                'Text baseline cannot read scanned images; OCR does not generate product mismatch findings.'],
            'summary': summarize(rows), 'results': rows}
        output = json.dumps(report, indent=2)
        if options['output']:
            target = Path(options['output']); target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(output + '\n', encoding='utf-8')
        self.stdout.write(json.dumps(report['summary']))
