"""Evaluate the existing rule contract in isolated in-memory SQLite, never the demo DB."""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from statistics import median
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def evaluate(dataset_path):
    dataset_bytes = dataset_path.read_bytes()
    dataset = json.loads(dataset_bytes)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    from django.conf import settings
    settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.exceptions import ValidationError
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.core.management import call_command
    from django.test import override_settings
    from portal.models import Document, Institution, Instrument
    from portal.uploads import validate_pdf_upload
    from portal.validation import CHECKS_VERSION, run_checks
    call_command('migrate', verbosity=0)
    user = get_user_model().objects.create_user(username='synthetic-evaluation', password=None)
    metrics = {rule: dict(tp=0, fp=0, fn=0, tn=0) for rule in dataset['rules']}
    rows, durations = [], []
    for index, case in enumerate(dataset['cases']):
        institution = Institution.objects.create(code=f'EVAL-{index}', name='Synthetic evaluation institution')
        fields = dict(bank=case.get('bank', 'Fictional Bank'), reference=case.get('reference', 'FDR-001'),
                      amount_paise=50000000, issue_date=date(2026, 1, 1), maturity_date=date(2027, 1, 1),
                      created_by=user, institution=institution)
        item = Instrument.objects.create(**fields)
        if 'other' in case:
            other = dict(fields)
            other.update({key: value for key, value in case['other'].items() if key != 'institution'})
            if case['other'].get('institution') == 'other':
                other['institution'] = Institution.objects.create(code=f'OTHER-{index}', name='Other synthetic institution')
            Instrument.objects.create(**other)
        if case['document'] != 'none':
            # Presence is the rule's input. No PDF content extraction is performed.
            Document.objects.create(instrument=item, kind=case['document'], file='synthetic-not-read.pdf',
                                    original_name='synthetic.pdf', size_bytes=0, sha256='0' * 64, uploaded_by=user)
        start = perf_counter()
        findings = run_checks(item)
        elapsed = (perf_counter() - start) * 1000
        durations.append(elapsed)
        actual, expected = {finding.code for finding in findings}, set(case['expected'])
        for rule, counts in metrics.items():
            counts['tp' if rule in actual and rule in expected else 'fp' if rule in actual
                   else 'fn' if rule in expected else 'tn'] += 1
        rows.append({'id': case['id'], 'expected': sorted(expected), 'actual': sorted(actual),
                     'pass': actual == expected, 'milliseconds': round(elapsed, 4)})
    for counts in metrics.values():
        counts['precision'] = counts['tp'] / (counts['tp'] + counts['fp']) if counts['tp'] + counts['fp'] else None
        counts['recall'] = counts['tp'] / (counts['tp'] + counts['fn']) if counts['tp'] + counts['fn'] else None
    uploads = []
    with TemporaryDirectory(prefix='release-evaluation-') as directory, override_settings(MEDIA_ROOT=directory):
        for case in dataset['uploads']:
            content = ((ROOT / 'fixtures' / case['source']).read_bytes() if 'source' in case
                       else case['text'].encode('ascii'))
            upload = SimpleUploadedFile(case['name'], content, content_type=case['mime'])
            accepted = True
            with override_settings(MAX_UPLOAD_BYTES=case.get('limit', 10 * 1024 * 1024)):
                try:
                    validate_pdf_upload(upload)
                except ValidationError:
                    accepted = False
            uploads.append({'id': case['id'], 'accepted': accepted,
                            'expected_envelope_accept': case['expected_envelope_accept'],
                            'readable_by_construction': case['readable_by_construction'],
                            'pass': accepted == case['expected_envelope_accept']})
    return {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'dataset_sha256': hashlib.sha256(dataset_bytes).hexdigest(), 'checks_version': CHECKS_VERSION,
            'scope': 'Synthetic boundary evaluation of two metadata rules and upload envelope policy; not real-world document validation.',
            'ground_truth': dataset['ground_truth'], 'extraction': {'implemented': False, 'precision': None, 'recall': None},
            'rules': metrics, 'cases': rows, 'uploads': uploads,
            'timing_ms': {'n': len(durations), 'median': round(median(durations), 4),
                          'min': round(min(durations), 4), 'max': round(max(durations), 4)},
            'all_contract_cases_pass': all(row['pass'] for row in rows + uploads)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, default=ROOT / 'evaluation' / 'cases.json')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = evaluate(args.cases)
    encoded = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf-8')
    print(encoded)
    raise SystemExit(0 if result['all_contract_cases_pass'] else 1)
