"""Offline S6 preparation gate; no HTTP, fixture writes or database queries."""
import argparse
from contextlib import ExitStack
from datetime import date
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).with_name('fixtures.json')
MAX_BYTES = 1024 * 1024

# Fixed v1 coverage, not a second set of calculated S5 outcomes.
# id, existing S5 input, required prohibited controls; screen follows id prefix.
LINKED = '''
case-ready S5-01 automatic_approval
case-term-unknown S5-02 approve
wizard-term-not-elapsed S5-03 submit_as_term_complete
wizard-progressive-certificate S5-04 advance_to_review
case-progressive-reviewed S5-05 automatic_approval
case-exception-unknown S5-07 approve
wizard-merger-child S5-08 advance_to_review
case-conversion-proceedings S5-10 approve
case-conversion-unknown S5-11 approve
case-penalty-proposed S5-13 approve,automatic_deduction
case-penalty-confirmed S5-14 automatic_deduction
case-rtgs-letter-kind S5-15 automatic_refund
case-rpgf-letter-kind S5-16 automatic_issuance
case-clearance-open S5-17 approve
case-clearance-objection S5-18 approve
case-external-hold S5-19 approve
wizard-affidavit-conflict S5-21 advance_to_review
case-evidence-denied S5-22 view_foreign_pdf,approve
wizard-unusable-document S5-23 advance_to_review
case-penalty-unavailable S5-25 approve
case-requester-authority S5-26 approve,reject,complete
case-clearer-authority S5-27 approve
case-stale S5-28 replay_without_refresh
wizard-existing-request S5-29 submit
wizard-renewal-conflict S5-30 submit
case-approve-projection S5-31 optimistic_approval,automatic_completion
case-completion-missing-pdf S5-32 complete
case-rtgs-completion-reference S5-33 complete
case-complete-projection S5-34 optimistic_completion
case-letter-failed S5-35 download_unissued_letter,complete
wizard-cross-scope S5-37 submit,view_pdf
case-reject-projection S5-38 optimistic_rejection
case-units-unknown S5-40 approve
'''
LINKED = {sid: (ref, controls.split(',')) for sid, ref, controls in
          (line.split() for line in LINKED.strip().splitlines())}
PATHS = ['TERM_COMPLETE', 'PROGRESSIVE_CLOSURE', 'MERGER',
         'CONVERSION_TO_UNIVERSITY', 'CLOSURE_BY_AICTE']

# Presentation-only states have no executable backend outcome. Keep their
# unknown/error/legacy payloads explicit instead of inferring successful facts.
PRESENTATION = {
    'wizard-path': ('path_selection', {'path_options': PATHS, 'mode': 'FDR'}, ['submit']),
    'wizard-template-unavailable': ('template_unavailable', {'template_available': False}, ['advance_to_documents']),
    'wizard-review-request': ('review', {'request_gate': 'EVIDENCE_AND_BASIS_REVIEWED_SYNTHETIC',
        'clearance_status': 'NOT_YET_REQUESTED', 'penalty_review': None}, ['automatic_submit', 'approve']),
    'wizard-path-changed': ('preview_invalidated', {'old_path': 'TERM_COMPLETE',
        'new_path': 'MERGER', 'preview_valid': False}, ['submit_with_old_preview']),
    'wizard-upload-invalid': ('invalid_input', {'upload_error': 'PDF_PARSE_REJECTED',
        'upload_accepted': False}, ['advance_to_review']),
    'case-viewer-failed': ('viewer_unavailable', {'document_ref': 'SYNTH-DOC-FDR',
        'page_count': None, 'viewer_loaded': False}, ['unscoped_download']),
    'case-loading': ('loading', {}, ['approve', 'complete']),
    'case-service-unavailable': ('service_unavailable', {}, ['approve', 'complete']),
    'case-session-expired': ('session_expired', {}, ['approve', 'complete']),
    'case-response-race': ('late_response', {}, ['apply_old_response']),
    'case-legacy': ('legacy', {'legacy_request_status': 'APPROVED',
        'persisted_monitoring_active': True}, ['invent_clearance_history']),
    'queue-open': ('assigned_tasks', {'unit': 'GRANTS', 'tasks': [{
        'ref': 'SYNTH-TASK-GRANTS', 'institution_name': 'Synthetic Demo Institute A',
        'status': 'OPEN', 'due_date': '2026-10-25',
        'responsible_party': 'Assigned Grants group'}]}, ['bulk_clear', 'approve_release']),
    'queue-empty': ('empty', {'tasks': []}, ['bulk_clear']),
    'queue-denied': ('access_denied', {}, ['decide_task']),
    'queue-stale': ('conflict', {}, ['replay_without_refresh']),
}
PUBLIC = {
    'public-issued': ('ISSUED', 'Issued demo record found'),
    'public-revoked': ('REVOKED', 'Revoked — do not rely on this letter'),
    'public-not-found': ('NOT_FOUND', 'Verification record unavailable'),
    'public-service-failed': ('UNAVAILABLE', 'Verification service temporarily unavailable'),
    'public-loading': ('LOADING', 'Checking verification record'),
}
PUBLIC_FIELDS = {'serial', 'issue_date', 'institution_name', 'kind', 'status'}
INVARIANTS = ['No effects applied', 'No automatic approval', 'No bank verification',
    'Human consequential decisions', 'No software movement of money',
    'Never use fixtures as runtime failure fallback']


class FixtureError(ValueError):
    """Controlled fixture/contract failure; not an application exception."""


def require(condition, message):
    if not condition:
        raise FixtureError(message)


def plain(value, depth=0):
    require(depth <= 24, 'Fixture nesting exceeds limit')
    if type(value) is dict:
        for key, child in value.items():
            require(type(key) is str, 'Object keys must be text')
            plain(key, depth + 1)
            plain(child, depth + 1)
    elif type(value) is list:
        for child in value:
            plain(child, depth + 1)
    elif type(value) is str:
        require(len(value) <= 4096 and not any(ord(c) < 32 for c in value), 'Invalid fixture text')
    else:
        require(value is None or type(value) in {bool, int}, 'Only plain JSON without floats is supported')
        if type(value) is int:
            require(abs(value) <= 2**53 - 1, 'Unsafe JSON integer')


def equal(actual, expected, label):
    # Recursive JSON equality distinguishes true/1 and null/0, including lists.
    require(json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True), label)


def keys(value, fields, label):
    require(type(value) is dict and set(value) == set(fields), label)


def texts(value, label):
    require(type(value) is list and bool(value) and all(type(s) is str and s.strip() for s in value), label)
    require(len(value) == len(set(value)), label)


def load(path):
    """Bounded local read; reject ambiguous duplicate JSON keys and constants."""
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result

    def constant(_):
        raise FixtureError('Non-finite JSON constant')

    with path.open('rb') as handle:
        raw = handle.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, 'Fixture file exceeds size limit')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise FixtureError('Invalid fixture JSON') from exc


def validate(dataset):
    """Check v1 preparation with all configured Django queries forbidden.

    Uses only local S5 source data and its existing pure evaluator. Django must
    be configured by the caller. Never validates actual users, PDFs or endpoints.
    """
    from django.db import connections

    def reject_query(*args, **kwargs):
        raise FixtureError('Database access forbidden in S6 fixture validation')

    with ExitStack() as stack:
        for connection in connections.all():
            stack.enter_context(connection.execute_wrapper(reject_query))
        try:
            return _validate(dataset)
        except FixtureError:
            raise
        except (ValueError, KeyError, TypeError, RecursionError) as exc:
            raise FixtureError('Malformed S6 fixture or source context') from exc


def _validate(d):
    from evaluation.s5.run import DATASET, context, merge
    from obligations.release_prerequisites import evaluate_prerequisites

    plain(d)
    keys(d, ['fixture_format', 'artifact_status', 'data_classification', 'simulation_label',
        'rule_status', 'source_checkpoint', 'assessment_date', 'usage', 'all_examples_require',
        'private_scenarios', 'public_record_allowlist', 'public_scenarios'], 'Top-level contract')
    for field, value in {'fixture_format': 's6-release-ui-spec-v1',
            'artifact_status': 'SPECIFICATION_ONLY_NO_FRONTEND', 'data_classification': 'SYNTHETIC',
            'simulation_label': 'SIMULATED', 'rule_status': 'DRAFT_DEMO_NOT_APPROVED',
            'source_checkpoint': '227a59c', 'assessment_date': '2026-10-24'}.items():
        equal(d[field], value, 'Invalid fixture context: ' + field)
    require(type(d['usage']) is str and bool(d['usage'].strip()), 'Missing usage boundary')
    equal(d['all_examples_require'], INVARIANTS, 'Missing safety boundaries')
    texts(d['public_record_allowlist'], 'Public allowlist')
    require(set(d['public_record_allowlist']) == PUBLIC_FIELDS, 'Public allowlist widened')
    private, public = d['private_scenarios'], d['public_scenarios']
    for rows, expected in [(private, set(LINKED) | set(PRESENTATION)), (public, set(PUBLIC))]:
        require(type(rows) is list, 'Scenario collection must be a list')
        require(all(type(s) is dict and type(s.get('id')) is str for s in rows), 'Invalid scenario ID')
        require(len(rows) == len(expected) and {s['id'] for s in rows} == expected,
                'Missing, duplicate or unknown v1 scenarios')

    s5 = load(DATASET)
    rule, when = context(s5)
    equal(when.isoformat(), d['assessment_date'], 'Assessment date mismatch')
    sources = {s['id']: s for s in s5['scenarios']}
    for s in private + public:
        expected_keys = ['heading', 'checks', 'prohibited_controls']
        if s['id'] in LINKED:
            expected_keys += ['s5_outcome', 's5_reason_codes']
        keys(s['expected'], expected_keys, s['id'] + ': expectation shape')
        require(type(s['expected']['heading']) is str and bool(s['expected']['heading'].strip()), 'Missing heading')
        texts(s['expected']['checks'], 'Missing presentation checks')
        texts(s['expected']['prohibited_controls'], 'Missing prohibited controls')

    for s in private:
        sid = s['id']
        keys(s, ['id', 'screen', 'state', 'actor', 'condition', 'view_data', 'expected'], sid + ': private shape')
        screen = 'clearance_queue' if sid.startswith('queue-') else sid.split('-')[0]
        equal(s['screen'], screen, sid + ': screen mismatch')
        if sid in LINKED:
            ref, controls = LINKED[sid]
            require(ref in sources, sid + ': missing S5 source')
            source = sources[ref]
            equal(s['state'], 'synthetic_assessment', sid + ': state mismatch')
            keys(s['condition'], ['s5_ref', 'operation', 'snapshot_recipe'], sid + ': lineage shape')
            equal(s['condition']['s5_ref'], ref, sid + ': incorrect lineage')
            equal(s['condition']['operation'], source['operation'], sid + ': incorrect operation')
            equal(s['condition']['snapshot_recipe'], 'Fresh S5 defaults recursively merged with this S5 input_patch; arrays/scalars/null replace.', sid + ': merge recipe')
            snapshot = merge(s5['defaults'], source['input_patch'])
            equal(s['actor'], snapshot['actor'], sid + ': synthetic actor/scope mismatch')
            result = evaluate_prerequisites(snapshot, operation=source['operation'],
                rules=rule, as_of=when, simulation_label='SIMULATED')
            for field, target in [('s5_outcome', 'outcome'), ('s5_reason_codes', 'reason_codes')]:
                equal(s['expected'][field], source['expected'][target], sid + ': S5 label drift')
                equal(s['expected'][field], result[target], sid + ': evaluator mismatch')
            for field, value in {'projection_only': True, 'effects_applied': False,
                    'automatic_approval': False, 'bank_verified': False, 'software_moves_money': False,
                    'consequential_decision_requires_human': True, 'future_actions_are_simulations': True}.items():
                equal(result[field], value, sid + ': unsafe evaluator projection')
            view = {} if result['outcome'] == 'DENIED' else {
                'persisted_case_status': snapshot['case']['status'],
                'persisted_version': snapshot['case']['version'],
                'persisted_monitoring_active': snapshot['monitoring_active'],
                'path': snapshot['case']['path'], 'mode': snapshot['case']['mode']}
            equal(s['view_data'], view, sid + ': saved state/scope or projection leak')
        else:
            state, view, controls = PRESENTATION[sid]
            equal(s['state'], state, sid + ': state mismatch')
            equal(s['condition'], {'trigger': state}, sid + ': trigger mismatch')
            equal(s['view_data'], view, sid + ': presentation/unknown/error payload mismatch')
            actor = {'role_label': 'CLEARANCE_UNIT', 'scope_unit': 'GRANTS'} if screen == 'clearance_queue' else {
                'role_label': 'INSTITUTION' if screen == 'wizard' else 'AUTHORITY', 'scope_institution_ids': [101]}
            equal(s['actor'], actor, sid + ': presentation actor/scope mismatch')
        equal(s['expected']['prohibited_controls'], controls, sid + ': prohibited controls changed')

    for s in public:
        sid = s['id']
        keys(s, ['id', 'screen', 'state', 'view_data', 'expected', 's5_lineage_ref'], sid + ': public shape')
        state, heading = PUBLIC[sid]
        equal(s['screen'], 'public_verify', sid + ': screen mismatch')
        equal(s['state'], state, sid + ': public state mismatch')
        equal(s['expected']['heading'], heading, sid + ': unsafe public heading')
        equal(s['expected']['prohibited_controls'], ['view_private_case', 'download_private_pdf'], sid + ': private controls')
        equal(s['s5_lineage_ref'], 'S5-36' if state == 'REVOKED' else None, sid + ': public lineage')
        if state in {'ISSUED', 'REVOKED'}:
            keys(s['view_data'], PUBLIC_FIELDS, sid + ': public data leak or missing field')
            equal(s['view_data'], {'serial': 'SYNTH-NOC-2026-001', 'issue_date': '2026-10-24',
                'institution_name': 'Synthetic Demo Institute A', 'kind': 'NOC', 'status': state}, sid + ': invalid synthetic public record')
            date.fromisoformat(s['view_data']['issue_date'])
        else:
            equal(s['view_data'], {}, sid + ': public error/loading disclosure')
    equal(sources['S5-36']['expected']['outcome'], 'PUBLIC_REVOKED_RECORD_ONLY', 'Revoked lineage mismatch')
    return {'result': 'passed', 'scenarios': 53, 'private_scenarios': 48,
        'public_scenarios': 5, 's5_comparisons': 33, 'database_queries': 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, default=FIXTURES)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    try:
        result = validate(load(args.fixtures))
    except FixtureError as exc:
        # Controlled labels use fixed schema names/known scenario IDs only.
        print(f'S6 fixture validation failed: {exc}', file=sys.stderr)
        return 1
    except (ValueError, KeyError, TypeError, OSError, RecursionError):
        print('S6 fixture validation failed; check the local fixture contract.', file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
