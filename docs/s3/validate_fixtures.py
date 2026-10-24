"""Offline presentation-fixture gate; no HTTP, database queries or fixture writes."""
import argparse
from collections import Counter
from datetime import date
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).with_name('fixtures.json')


class FixtureError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise FixtureError(message)


def equal(actual, expected, label):
    # JSON booleans must not compare equal to integer money or counts.
    require(type(actual) is type(expected) and actual == expected, f'{label}: mismatch')


def dated(values):
    return {k: date.fromisoformat(v) if v is not None and
            (k.endswith('_date') or k in {'term_start', 'term_end'}) else v
            for k, v in values.items()}


def inr(paise):
    if paise is None:
        return 'Unknown'
    require(type(paise) is int and 0 <= paise <= 2**53 - 1, 'Unsafe money')
    digits = str(paise // 100)
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while head:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return 'INR ' + ','.join(groups + [tail]) + f'.{paise % 100:02d}'


def validate(dataset):
    """Validate the fixed v1 scenario suite. Django must already be configured.

    Actor checks validate fixture consistency, never real authorization. Queries
    are forbidden even if this function is called outside Django's test runner.
    """
    from django.db import connections
    from contextlib import ExitStack

    def reject_query(*args, **kwargs):
        raise FixtureError('Database access forbidden in S3 fixture validation')

    with ExitStack() as stack:
        for connection in connections.all():
            stack.enter_context(connection.execute_wrapper(reject_query))
        return _validate(dataset)


def _validate(d):
    from obligations.calculations import (ApprovalInput, HoldingInput,
        ObligationInput, coverage, required_amount)
    from obligations.catalogue import draft_payload
    from obligations.checks import obligation_findings
    from obligations.rules import RuleInputError, rule_snapshot

    equal(d['fixture_format'], 's3-presentation-v1', 'format')
    equal(d['status'], 'SPECIFICATION_ONLY_NOT_AN_API_CONTRACT', 'status')
    equal(d['data_classification'], 'SYNTHETIC', 'classification')
    equal(d['simulation_label'], 'SIMULATED', 'label')
    when = date.fromisoformat(d['assessment_date'])
    rows = d['scenarios']
    expected_ids = {
        'list-staff', 'list-own', 'list-loading', 'list-empty', 'list-unavailable',
        'detail-covered', 'detail-shortfall', 'detail-term-gap', 'detail-unknown',
        'detail-adapter-unavailable', 'detail-proof-overdue', 'detail-not-found',
        'detail-forbidden', 'calculator-idle', 'calculator-preview',
        'calculator-invalid', 'calculator-conflict', 'calculator-unavailable',
        'calculator-loading'}
    require(len(rows) == 19 and {s['id'] for s in rows} == expected_ids,
            'Missing or duplicate v1 scenarios')
    require(Counter(s['screen'] for s in rows) == {
        'institution_list': 5, 'institution_detail': 8, 'calculator': 6}, 'Screen counts')
    lineage = {s['id'] for s in json.loads(
        (ROOT / 'evaluation/s2/cases.json').read_text(encoding='utf-8'))['cases']}
    r = d['rule']
    equal(r['policy_label'], 'DRAFT_DEMO_NOT_APPROVED', 'rule label')
    equal(r['publication_status'], 'UNAPPROVED', 'publication')
    record = SimpleNamespace(**{k: r[k] for k in
        ['code', 'version', 'source_document', 'source_clause']},
        effective_from=date.fromisoformat(r['effective_from']),
        effective_to=date.fromisoformat(r['effective_to']) if r['effective_to'] else None,
        payload=draft_payload())
    rule = rule_snapshot(record, when)
    equal(rule.sha256, r['sha256'], 'rule fingerprint')
    for entity in d['entities'].values():
        require(entity['institution']['code'].startswith('SYNTH-'), 'Synthetic identity')
        if entity['profile']:
            require(entity['profile']['contact_email'].endswith('@example.invalid'), 'Synthetic email')
    calculations = rejections = 0
    for s in rows:
        sid = s['id']
        equal(s['simulation_label'], 'SIMULATED', sid)
        require(set(s.get('s2_lineage', [])) <= lineage, f'{sid}: missing lineage')
        data, display, actor = s['screen_data'], s['expected_display'], s['actor']
        if s['state'] in {'not_found', 'forbidden'}:
            require(data is None and display['show_protected_details'] is False,
                    f'{sid}: protected detail leak')
            equal(s['http_status_hint'], 404 if s['state'] == 'not_found' else 403, sid)
            continue
        scope = [actor['institution_id']] if actor['role'] == 'institution' else actor['scope_institution_ids']
        if s['screen'] == 'institution_list':
            if data is None:
                require(display['result_count'] is None, f'{sid}: false zero count')
            else:
                ids = [d['entities'][ref]['institution']['id'] for ref in data['institution_refs']]
                require(set(ids) <= set(scope), f'{sid}: scope leak')
                equal(data['count'], len(ids), sid)
                equal(display['result_count'], len(ids), sid)
                if 'visible_institution_ids' in display:
                    equal(display['visible_institution_ids'], ids, sid)
            continue
        entity = d['entities'][data['institution_ref']]
        institution_id = entity['institution']['id']
        require(institution_id in scope, f'{sid}: scope leak')
        equal(data['rule_ref'], r['id'], sid)
        equal(data['assessment_date'], d['assessment_date'], sid)
        if 'next_action' in data:
            equal(data['next_action']['delivery_status'], 'NOT_SENT_SIMULATED', sid)
        if s['screen'] == 'calculator':
            equal(display['preview_visible'], data['preview'] is not None, sid)
            if s['state'] != 'ready':
                require(data['preview'] is None, f'{sid}: stale preview')
        else:
            equal(data['selected_obligation']['institution_id'], institution_id, sid)
            if data['assessment_status'] == 'UNAVAILABLE':
                require(data['holdings'] is None and data['finding_codes'] is None,
                        f'{sid}: unavailable ledger became empty')
                for field in ['held_paise', 'shortfall_paise', 'coverage_end', 'term_gap_days']:
                    require(data['coverage'][field] is None, f'{sid}: invented {field}')
                equal(data['coverage']['required_paise'], data['selected_obligation']['required_paise'], sid)
                for field in ['held', 'shortfall']:
                    equal(display[field + '_display'], 'Unavailable', sid)
                equal(display['required_display'], inr(data['coverage']['required_paise']), sid)
                continue
        inputs = s.get('calculation_inputs')
        if inputs is None:
            require(s['screen'] == 'calculator' and s['state'] != 'ready', f'{sid}: missing calculation')
            continue
        calculations += 1
        equal(inputs['as_of'], d['assessment_date'], sid)
        if s['screen'] == 'calculator':
            equal(inputs['approvals'], data['draft_approvals'], sid)
            equal(inputs['institution_type'], entity['profile']['institution_type'], sid)
            try:
                actual = required_amount([ApprovalInput(**a) for a in inputs['approvals']],
                    rule, as_of=when, institution_type=inputs['institution_type'])
            except RuleInputError:
                require(inputs.get('expected_error') == 'RuleInputError' and
                        s['state'] == 'validation_error' and s['http_status_hint'] == 400,
                        f'{sid}: unexpected rejection')
                require(display['retain_inputs'] and display['field_errors'], f'{sid}: missing error guidance')
                rejections += 1
                continue
            require('expected_error' not in inputs, f'{sid}: expected rejection did not occur')
            for key in ['required_paise', 'multiplier', 'exemption_assessed']:
                equal(data['preview'][key], actual[key], sid)
            equal(data['preview']['base_paise'], [a['base_paise'] for a in actual['breakdown']], sid)
            equal(display['total_display'], inr(actual['required_paise']), sid)
            require(display['show_save_action'] is False, f'{sid}: mutation action')
        else:
            equal(inputs['obligation'], data['selected_obligation'], sid)
            equal(inputs['holdings'], data['holdings'], sid)
            ob = ObligationInput(**dated(inputs['obligation']))
            holdings = [HoldingInput(**dated(h)) for h in inputs['holdings']]
            actual = coverage(ob, when, holdings=holdings)
            for key, value in data['coverage'].items():
                equal(value, actual[key], f'{sid}: coverage {key}')
            proof = inputs['proof_context']
            equal(proof, data.get('proof_context', {}), sid)
            args = {k: date.fromisoformat(v) if v else None for k, v in proof.items()
                    if k in {'intimation_date', 'payment_proof_on', 'affidavit_on'}}
            findings = obligation_findings(ob, rule, as_of=when, holdings=holdings, **args)
            codes = [f.code for f in findings]
            equal(data['finding_codes'], codes, sid)
            equal(display['finding_codes'], codes, sid)
            for f in findings:
                if f.code == 'PROOF_OVERDUE':
                    for key in ['due_date', 'days_overdue']:
                        equal(proof[key], f.as_dict()['values'][key], sid)
                    equal(data['next_action']['due_date'], proof['due_date'], sid)
            for key in ['required', 'held', 'shortfall']:
                equal(display[key + '_display'], inr(actual[key + '_paise']), sid)
            require(display['show_bank_verified_badge'] is False, f'{sid}: verification claim')
        require(display['show_draft_label'] is True, f'{sid}: missing draft label')
    equal(calculations, 7, 'calculation count')
    equal(rejections, 1, 'expected rejections')
    return {'scenarios': 19, 'calculation_cases': calculations,
            'expected_rejections': rejections, 'database_queries': 0, 'result': 'passed'}


def main():
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, default=FIXTURES)
    args = parser.parse_args()
    try:
        result = validate(json.loads(args.fixtures.read_text(encoding='utf-8')))
    except (FixtureError, ValueError, KeyError, TypeError, OSError) as exc:
        print(f'S3 fixture validation failed: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
