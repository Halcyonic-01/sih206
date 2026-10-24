"""Offline evaluation of literal-labelled synthetic S2 cases; no DB access."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace

DATASET = Path(__file__).with_name('cases.json')
ROOT = Path(__file__).resolve().parents[2]
CODES = ('AMOUNT_SHORTFALL', 'TERM_GAP', 'PROOF_OVERDUE')


def merge(base, patch):
    result = deepcopy(base)
    for key, value in patch.items():
        result[key] = merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else deepcopy(value)
    return result


def dates(values):
    return {key: date.fromisoformat(value) if value is not None and (
        key.endswith('_date') or key in {'term_start', 'term_end'}) else value
        for key, value in values.items()}


def execute(case, defaults):
    from obligations.calculations import (ApprovalInput, HoldingInput, ObligationInput,
        coverage, penalty_proposal, required_amount, term_end)
    from obligations.catalogue import SOURCE, draft_payload
    from obligations.checks import obligation_findings
    from obligations.rules import rule_snapshot
    values = case['input']
    when = date.fromisoformat(values.get('as_of', defaults['as_of']))
    record = SimpleNamespace(code='synthetic-s2-review', version=1,
        effective_from=date.fromisoformat(defaults['rule_effective_from']),
        effective_to=date.fromisoformat(defaults['rule_effective_to']) if defaults['rule_effective_to'] else None,
        payload=merge(draft_payload(), values.get('payload_patch', {})),
        source_document=SOURCE, source_clause='Synthetic regression contract; not approved policy')
    rule = rule_snapshot(record, when)
    kind = case['kind']
    if kind == 'policy':
        return {'valid': True}
    if kind == 'amount':
        approvals = [ApprovalInput(**(defaults['approval'] | item)) for item in values['approvals']]
        return required_amount(approvals, rule, as_of=when)
    if kind == 'term':
        return {'term_end': term_end(date.fromisoformat(values['start']), rule, as_of=when).isoformat()}
    if kind == 'penalty':
        args = {k: v for k, v in values.items() if k not in {'as_of', 'payload_patch'}}
        for key in ['intimation_date', 'proof_completed_on']:
            if key in args:
                args[key] = date.fromisoformat(args[key])
        return penalty_proposal(ruleset=rule, as_of=when, **args)
    obligation = ObligationInput(**dates(defaults['obligation'] | values.get('obligation', {})))
    raw = values['holdings']
    holdings = None if raw is None else [HoldingInput(**dates(defaults['holding'] | h)) for h in raw]
    if kind == 'coverage':
        return coverage(obligation, when, holdings=holdings)
    if kind == 'findings':
        args = {key: date.fromisoformat(values[key]) for key in
                ['intimation_date', 'payment_proof_on', 'affidavit_on'] if key in values}
        findings = obligation_findings(obligation, rule, as_of=when, holdings=holdings, **args)
        return {'codes': sorted(f.code for f in findings), 'findings': [f.as_dict() for f in findings]}
    raise ValueError('Unknown scenario kind.')


def matches(expected, actual):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and matches(value, actual[key])
                                              for key, value in expected.items())
    return type(expected) is type(actual) and expected == actual


def evaluate(path=DATASET):
    from obligations.rules import RuleInputError
    raw = Path(path).read_bytes()
    dataset = json.loads(raw)
    cases = dataset['cases']
    assert dataset['data_classification'] == 'SYNTHETIC'
    assert len({c['id'] for c in cases}) == len(cases)
    rows = []
    confusion = {code: Counter(tp=0, fp=0, fn=0, tn=0) for code in CODES}
    evaluated_findings = 0
    for case in cases:
        assert case['rationale'].strip() and case['expected']
        started = time.perf_counter()
        try:
            actual = execute(case, dataset['defaults'])
        except RuleInputError as exc:
            actual = {'error': 'RuleInputError', 'message': str(exc)}
        except Exception as exc:
            actual = {'unexpected_error': type(exc).__name__, 'message': str(exc)}
        elapsed = time.perf_counter() - started
        rows.append({'id': case['id'], 'kind': case['kind'], 'passed': matches(case['expected'], actual),
                     'expected': case['expected'], 'actual': actual, 'elapsed_seconds': elapsed})
        if case['kind'] == 'findings' and 'codes' in case['expected']:
            evaluated_findings += 1
            expected, predicted = set(case['expected']['codes']), set(actual.get('codes', []))
            for code in CODES:
                confusion[code]['tp' if code in expected and code in predicted else
                                'fn' if code in expected else 'fp' if code in predicted else 'tn'] += 1
    for counts in confusion.values():
        counts['precision'] = counts['tp'] / (counts['tp'] + counts['fp']) if counts['tp'] + counts['fp'] else None
        counts['recall'] = counts['tp'] / (counts['tp'] + counts['fn']) if counts['tp'] + counts['fn'] else None
    return {'dataset_id': dataset['dataset_id'], 'dataset_sha256': hashlib.sha256(raw).hexdigest(),
        'label_review_status': dataset['review_status'], 'scope': dataset['scope'],
        'engine_sha256': {name: hashlib.sha256((ROOT / 'obligations' / name).read_bytes()).hexdigest()
                          for name in ['catalogue.py', 'rules.py', 'calculations.py', 'checks.py']},
        'case_count': len(rows), 'passed': sum(row['passed'] for row in rows),
        'failed': sum(not row['passed'] for row in rows), 'finding_cases': evaluated_findings,
        'finding_metrics': confusion, 'total_case_seconds': sum(row['elapsed_seconds'] for row in rows),
        'timing_scope': 'Local case calls including validation; excludes Django startup, DB, PDFs and human review.',
        'cases': rows}


def main():
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = evaluate()
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in
        ['case_count', 'passed', 'failed', 'finding_cases', 'finding_metrics', 'total_case_seconds']}))
    return 1 if result['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
