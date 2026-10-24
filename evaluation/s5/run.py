"""Compare existing literal S5 labels with pure checks; no Django or writes."""
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from obligations.catalogue import draft_payload
from obligations.release_prerequisites import evaluate_prerequisites
from obligations.rules import rule_snapshot

DATASET = Path(__file__).resolve().parents[2] / 'docs/s5/scenarios.json'


def merge(base, patch):
    result = deepcopy(base)
    for key, value in patch.items():
        result[key] = merge(result[key], value) if type(value) is dict and type(result.get(key)) is dict else deepcopy(value)
    return result


def context(dataset):
    record = dataset['rule_context']
    when = date.fromisoformat(dataset['assessment_date'])
    rule = rule_snapshot(SimpleNamespace(**{key: record[key] for key in
        ['code', 'version', 'source_document', 'source_clause']},
        effective_from=date.fromisoformat(record['effective_from']),
        effective_to=date.fromisoformat(record['effective_to']), payload=draft_payload()), when)
    if rule.sha256 != record['sha256']:
        raise ValueError('Synthetic draft rule fingerprint mismatch.')
    return rule, when


def matches(expected, actual):
    if type(expected) is dict:
        return type(actual) is dict and all(key in actual and matches(value, actual[key]) for key, value in expected.items())
    return type(expected) is type(actual) and expected == actual


def evaluate():
    raw = DATASET.read_bytes()
    dataset = json.loads(raw)
    if (dataset['fixture_format'] != 's5-release-spec-v1' or dataset['data_classification'] != 'SYNTHETIC'
            or dataset['simulation_label'] != 'SIMULATED'):
        raise ValueError('Explicit synthetic S5 dataset required.')
    rule, when = context(dataset)
    cases = dataset['scenarios']
    if len({case['id'] for case in cases}) != len(cases):
        raise ValueError('Duplicate scenario IDs.')
    rows = []
    for case in cases:
        snapshot = merge(dataset['defaults'], case['input_patch'])
        actual = evaluate_prerequisites(snapshot, operation=case['operation'], rules=rule,
            as_of=when, simulation_label=dataset['simulation_label'])
        expected = {key: value for key, value in case['expected'].items() if key != 'assertion'}
        invariants = dataset['unconditional_expectations']
        passed = matches(expected, actual) and matches(invariants, actual)
        rows.append({'id': case['id'], 'passed': passed, 'expected': expected, 'actual': actual})
    labels = [{'id': case['id'], 'expected': case['expected']} for case in cases]
    return {'dataset_sha256': hashlib.sha256(raw).hexdigest(),
            'labels_sha256': hashlib.sha256(json.dumps(labels, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            'review_status': dataset['review_status'], 'case_count': len(rows),
            'passed': sum(row['passed'] for row in rows), 'failed': sum(not row['passed'] for row in rows),
            'cases': rows}


if __name__ == '__main__':
    result = evaluate()
    print(json.dumps({key: value for key, value in result.items() if key != 'cases'}, indent=2))
    for row in result['cases']:
        if not row['passed']:
            print(json.dumps(row, indent=2))
    raise SystemExit(1 if result['failed'] else 0)
