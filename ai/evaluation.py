"""Dataset validation and exact, reproducible scoring. No provider calls here."""
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from pypdf import PdfReader
from .services import FIELD_NAMES


def normalize(name, value):
    if value is None:
        return None
    return str(Decimal(value).normalize()) if name == 'amount' else value.strip().casefold()


def load_manifest(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('synthetic_only') is not True or data.get('schema') != 1 or not data.get('cases'):
        raise ValueError('A version-1 synthetic-only manifest is required.')
    seen = set()
    for item in data['cases']:
        if item['id'] in seen:
            raise ValueError('Duplicate dataset identity.')
        seen.add(item['id'])
        pdf = (path.parent / item['file']).resolve()
        if pdf.parent != path.parent or pdf.suffix != '.pdf':
            raise ValueError('Dataset PDF must be beside its manifest.')
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Dataset hash mismatch.')
        count = len(PdfReader(pdf).pages)
        if count != item['page_count'] or set(item['expected']) != set(FIELD_NAMES) or set(item['declared']) != set(FIELD_NAMES):
            raise ValueError('Invalid dataset pages or field set.')
        for name, field in item['expected'].items():
            value, page = field['value'], field['page']
            if (value is None) != (page is None) or page is not None and (type(page) is not int or not 1 <= page <= count):
                raise ValueError('Ground truth must identify a valid supporting page or abstain.')
            normalize(name, value)
        expected_flags = {k for k, f in item['expected'].items() if f['value'] is not None and
                          normalize(k, f['value']) != normalize(k, item['declared'][k])}
        if expected_flags != set(item['expected_mismatches']):
            raise ValueError('Mismatch labels disagree with verified values.')
    return data


def score_case(item, result):
    counts = Counter(fields=len(FIELD_NAMES))
    errors = []
    checks = {}
    predicted = {f['field'] for f in result.get('findings', []) if f.get('code') == 'AI_MISMATCH'}
    truth = set(item['expected_mismatches'])
    counts.update(tp=len(predicted & truth), fp=len(predicted - truth), fn=len(truth - predicted))
    for name, expected in item['expected'].items():
        actual = result.get('fields', {}).get(name, {'value': None, 'page': None})
        value, target = normalize(name, actual['value']), normalize(name, expected['value'])
        counts['known'] += target is not None
        counts['predicted'] += value is not None
        # A service failure earns no exact-match credit, even for a null label.
        correct = result.get('status') == 'success' and value == target
        counts['exact'] += correct
        counts['correct_predictions'] += correct and value is not None
        counts['correct_pages'] += correct and value is not None and actual['page'] == expected['page']
        counts['missing_values'] += target is not None and value is None
        counts['invented_values'] += target is None and value is not None
        counts['wrong_values'] += target is not None and value is not None and not correct
        checks[name] = {'known': target is not None, 'predicted': value is not None,
                        'exact': correct, 'correct_prediction': correct and value is not None,
                        'supported': correct and value is not None and actual['page'] == expected['page']}
        if not correct or value is not None and actual['page'] != expected['page']:
            errors.append({'field': name, 'expected': expected, 'actual': actual})
    return {'id': item['id'], 'status': result.get('status'), 'counts': dict(counts), 'errors': errors,
            'field_checks': checks, 'extracted_fields': result.get('fields', {}),
            'duration_ms': result.get('evaluation_duration_ms', 0), 'run_id': result.get('run_id')}


def summarize(rows):
    totals = Counter()
    for row in rows:
        totals.update(row['counts'])
    ratio = lambda a, b: a / b if b else None
    durations = sorted(row['duration_ms'] for row in rows)
    per_field = {}
    for name in FIELD_NAMES:
        checks = [row['field_checks'][name] for row in rows]
        known = sum(c['known'] for c in checks)
        predicted = sum(c['predicted'] for c in checks)
        correct = sum(c['correct_prediction'] for c in checks)
        per_field[name] = {'known': known, 'predicted': predicted, 'correct': correct,
            'exact_accuracy': ratio(sum(c['exact'] for c in checks), len(checks)),
            'precision': ratio(correct, predicted), 'recall': ratio(correct, known)}
    return {'documents': len(rows), 'counts': dict(totals), 'statuses': dict(Counter(r['status'] for r in rows)),
        'per_field': per_field,
        'documents_exact_and_successful': sum(r['status'] == 'success' and not r['errors'] for r in rows),
        'field_exact_accuracy': ratio(totals['exact'], totals['fields']),
        'field_precision': ratio(totals['correct_predictions'], totals['predicted']),
        'field_recall': ratio(totals['correct_predictions'], totals['known']),
        'page_accuracy_among_predictions': ratio(totals['correct_pages'], totals['predicted']),
        'mismatch_precision': ratio(totals['tp'], totals['tp'] + totals['fp']),
        'mismatch_recall': ratio(totals['tp'], totals['tp'] + totals['fn']),
        'timing_ms': {'min': min(durations) if durations else None,
                      'max': max(durations) if durations else None,
                      'median': (durations[(len(durations)-1)//2] + durations[len(durations)//2]) / 2 if durations else None}}
