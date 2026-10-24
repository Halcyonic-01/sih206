"""Evaluate literal synthetic KPI labels; no Django setup, network or writes."""
from datetime import date, datetime
import json
from pathlib import Path

from obligations.kpis import (AcceptedSuccessor, KpiEvent, KpiInputError,
    ProcessSnapshot, RenewalSnapshot, calculate_kpis)

DATASET = Path(__file__).with_name('cases.json')


def inputs(case, context):
    values = context | case.get('context', {})
    return dict(scope_institution_ids=tuple(values['scope_institution_ids']),
        window_start=datetime.fromisoformat(values['window_start']),
        window_end=datetime.fromisoformat(values['window_end']),
        as_of=datetime.fromisoformat(values['as_of']), simulation_label='SIMULATED',
        processes=tuple(ProcessSnapshot(row['instrument_id'], row['institution_id'],
            row['history_complete'], tuple(KpiEvent(**(event | {
                'at': datetime.fromisoformat(event['at'])})) for event in row['events']))
            for row in case['processes']),
        renewals=tuple(RenewalSnapshot(row['instrument_id'], row['institution_id'],
            date.fromisoformat(row['maturity_date']), row['eligible'], row['history_complete'],
            AcceptedSuccessor(**(row['successor'] | {'accepted_at': datetime.fromisoformat(
                row['successor']['accepted_at'])})) if row.get('successor') else None)
            for row in case['renewals']))


def matches(expected, actual):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and matches(v, actual[k]) for k, v in expected.items())
    return type(expected) is type(actual) and expected == actual


def evaluate():
    dataset = json.loads(DATASET.read_text(encoding='utf-8'))
    if dataset['data_classification'] != 'SYNTHETIC' or dataset['simulation_label'] != 'SIMULATED':
        raise ValueError('Explicit synthetic labels required.')
    cases = dataset['cases']
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate case IDs.')
    rows = []
    for case in cases:
        try:
            actual = calculate_kpis(**inputs(case, dataset['context']))
        except KpiInputError:
            actual = {'error': 'KpiInputError'}
        expected = {'error': case['expected_error']} if 'expected_error' in case else case['expected']
        rows.append({'id': case['id'], 'passed': matches(expected, actual),
                     'expected': expected, 'actual': actual})
    return {'dataset_id': dataset['dataset_id'], 'review_status': dataset['review_status'],
            'case_count': len(rows), 'passed': sum(row['passed'] for row in rows),
            'failed': sum(not row['passed'] for row in rows), 'cases': rows}


if __name__ == '__main__':
    result = evaluate()
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, indent=2))
    for row in result['cases']:
        if not row['passed']:
            print(json.dumps(row, indent=2))
    raise SystemExit(1 if result['failed'] else 0)
