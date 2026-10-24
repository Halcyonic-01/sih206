"""Pure synthetic S5 prerequisite checks; never execute a release or permission."""
from datetime import date

from .calculations import penalty_proposal
from .rules import RuleInputError, RuleSnapshot, rule_snapshot

OPERATIONS = {'ASSESS', 'REQUEST', 'APPROVE', 'REJECT', 'COMPLETE', 'ISSUE_LETTER', 'PUBLIC_VERIFY'}
SECTIONS = {
    'actor': 'id role_label scope_institution_ids',
    'case': 'id institution_id instrument_id requester_id version expected_version assessment_version status path mode other_active_release',
    'instrument': 'id institution_id status superseded released maturity_date successor_proposal_exists',
    'obligation': 'id institution_id term_end term_elapsed_reviewed',
    'basis': 'closure_order_ref merger_order_ref conversion_order_ref deposit_matured_for_exception certificate_exception_reviewed child_institution_ids child_scope_complete child_certificates',
    'affidavit_review': 'template_ref all_required_answers_recorded signed_pdf_consistency reviewed',
    'holds': 'trustee_dispute financial_embezzlement pending_complaints pending_disciplinary_proceedings external_noc_status',
    'penalty_review': 'status assessments',
    'letter': 'state kind ref digitally_signed',
    'completion': 'new_evidence_ref evidence_is_new parse_status notes refund_reference',
}
TOP = set(SECTIONS) | {'document_context_complete', 'documents', 'clearance_context_complete',
                        'required_units', 'clearances', 'decision_reason', 'monitoring_active'}


class PrerequisiteInputError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise PrerequisiteInputError(message)


def _plain(value, depth=0):
    """Copy only concrete JSON values; no ORM/lazy objects, floats or cycles."""
    _require(depth <= 24, 'Snapshot nesting exceeds the supported depth.')
    if type(value) is dict:
        _require(all(type(k) is str and len(k) <= 100 for k in value), 'Snapshot keys must be bounded strings.')
        return {k: _plain(v, depth + 1) for k, v in value.items()}
    if type(value) is list:
        return [_plain(v, depth + 1) for v in value]
    _require(value is None or type(value) in {str, int, bool}, 'Use concrete JSON values only.')
    return value


def _keys(value, names):
    _require(type(value) is dict and set(value) == set(names.split()), 'Incomplete or unexpected snapshot fields.')


def _integer(value, minimum=1):
    _require(type(value) is int and value >= minimum, 'Expected an integer in the supported range.')


def _flag(value, nullable=True):
    _require(type(value) is bool or (nullable and value is None), 'Use explicit boolean or unknown facts.')


def _text(value, nullable=False):
    _require((nullable and value is None) or (type(value) is str and len(value) <= 2000),
             'Expected a bounded text value.')


def _present(value):
    return type(value) is str and bool(value.strip())


def _day(value):
    if value is None:
        return None
    _require(type(value) is str, 'Snapshot dates must be ISO date strings or unknown.')
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise PrerequisiteInputError('Invalid snapshot date.') from exc
    _require(parsed.isoformat() == value, 'Snapshot dates must use YYYY-MM-DD.')
    return parsed


def _validate(s):
    _require(set(s) == TOP, 'Incomplete or unexpected top-level snapshot fields.')
    for name, keys in SECTIONS.items():
        _keys(s[name], keys)
    for section, fields in [('actor', 'id'), ('case', 'id institution_id instrument_id requester_id version expected_version assessment_version'),
                            ('instrument', 'id institution_id'), ('obligation', 'id institution_id')]:
        for key in fields.split():
            _integer(s[section][key])
    for section, fields in [('case', 'other_active_release'), ('instrument', 'superseded released successor_proposal_exists'),
            ('obligation', 'term_elapsed_reviewed'), ('basis', 'deposit_matured_for_exception certificate_exception_reviewed child_scope_complete'),
            ('affidavit_review', 'all_required_answers_recorded reviewed'),
            ('holds', 'trustee_dispute financial_embezzlement pending_complaints pending_disciplinary_proceedings'),
            ('completion', 'evidence_is_new')]:
        for key in fields.split():
            _flag(s[section][key])
    for field in ['document_context_complete', 'clearance_context_complete']:
        _flag(s[field])
    _flag(s['monitoring_active'], nullable=False)
    for section, fields in [('actor', 'role_label'), ('case', 'status path mode'), ('instrument', 'status'),
            ('basis', 'closure_order_ref merger_order_ref conversion_order_ref'),
            ('affidavit_review', 'template_ref signed_pdf_consistency'), ('holds', 'external_noc_status'),
            ('penalty_review', 'status'), ('letter', 'state kind ref'),
            ('completion', 'new_evidence_ref parse_status notes refund_reference')]:
        for field in fields.split():
            _text(s[section][field], nullable=True)
    _text(s['decision_reason'], nullable=True)
    _flag(s['letter']['digitally_signed'], nullable=False)
    _day(s['obligation']['term_end'])
    _day(s['instrument']['maturity_date'])
    units, children = s['required_units'], s['basis']['child_institution_ids']
    _require(type(units) is list and all(_present(u) for u in units), 'Required units must be explicit text codes.')
    _require(len(units) == len(set(units)), 'Duplicate required clearance unit.')
    _require(type(children) is list, 'Child institutions must be an explicit list.')
    for child in children:
        _integer(child)
    _require(len(children) == len(set(children)), 'Duplicate child institution.')
    certs = s['basis']['child_certificates']
    _require(type(certs) is dict and all(k.isascii() and k.isdecimal() and str(int(k)) == k for k in certs),
             'Child certificate keys must be canonical institution IDs.')
    for ref in certs.values():
        _text(ref, nullable=True)
    _require(type(s['documents']) is dict and type(s['clearances']) is dict, 'Supply concrete evidence and clearance maps.')
    for doc in s['documents'].values():
        if doc is None:
            continue
        _keys(doc, 'ref institution_id instrument_id review_status parse_status')
        _integer(doc['institution_id']); _integer(doc['instrument_id'])
        for key in ['ref', 'review_status', 'parse_status']:
            _text(doc[key], nullable=True)
    for task in s['clearances'].values():
        if task is None:
            continue
        _keys(task, 'status actor_id reason evidence_ref')
        if task['actor_id'] is not None:
            _integer(task['actor_id'])
        for key in ['status', 'reason', 'evidence_ref']:
            _text(task[key], nullable=True)
    assessments = s['penalty_review']['assessments']
    _require(assessments is None or type(assessments) is list, 'Penalty context must be a list or explicitly unavailable.')
    for assessment in assessments or []:
        _keys(assessment, 'kind base_paise rate_bps amount_paise status actor_id reason')
        _integer(assessment['base_paise'])
        for field in ['rate_bps', 'amount_paise']:
            _integer(assessment[field], 0)
        _require(assessment['rate_bps'] <= 10000, 'Penalty rate exceeds 100 percent.')
        if assessment['actor_id'] is not None:
            _integer(assessment['actor_id'])
        for field in ['kind', 'status', 'reason']:
            _text(assessment[field], nullable=True)


def evaluate_prerequisites(snapshot, *, operation, rules, as_of, simulation_label):
    """Return prerequisite findings and hypothetical projections, never actions.

    Role, review, parse and completeness labels are supplied synthetic facts, not
    proof of actual authorization, document validity or published policy.
    """
    _require(simulation_label == 'SIMULATED', 'Only explicitly SIMULATED inputs are supported.')
    _require(type(operation) is str and operation in OPERATIONS, 'Unknown simulated operation.')
    _require(type(as_of) is date and type(rules) is RuleSnapshot, 'Supply an explicit date and frozen rule snapshot.')
    s = _plain(snapshot)
    _require(type(s) is dict and type(s.get('actor')) is dict and type(s.get('case')) is dict,
             'Supply a materialized snapshot with actor and case context.')
    actor, case = s['actor'], s['case']
    _keys(actor, SECTIONS['actor'])
    _integer(actor['id']); _integer(case.get('institution_id'))
    _require(type(actor['scope_institution_ids']) is list, 'Supply explicit synthetic institution scope.')
    for identity in actor['scope_institution_ids']:
        _integer(identity)
    _require(len(set(actor['scope_institution_ids'])) == len(actor['scope_institution_ids']), 'Duplicate institution scope.')
    _flag(s.get('monitoring_active'), nullable=False)
    findings, assessment_context = [], None

    def result(outcome, codes=None, **projection):
        return {'format': 's5-prerequisites-v1', 'simulation_label': 'SIMULATED',
                'policy_label': 'DRAFT_DEMO_NOT_APPROVED', 'outcome': outcome,
                'reason_codes': list(dict.fromkeys(codes if codes is not None else [f['code'] for f in findings])),
                'findings': [] if outcome == 'DENIED' else findings,
                'projection_only': True, 'effects_applied': False, 'automatic_approval': False,
                'bank_verified': False, 'software_moves_money': False,
                'future_actions_are_simulations': True,
                'consequential_decision_requires_human': True,
                'assessment_context': None if outcome == 'DENIED' else assessment_context,
                'monitoring_after_action': s['monitoring_active'], **projection}

    # No foreign case/evidence details or rule fingerprints are returned on denial.
    scope = set(actor['scope_institution_ids'])
    if operation != 'PUBLIC_VERIFY' and case['institution_id'] not in scope:
        return result('DENIED', ['CASE_OUTSIDE_SCOPE'])
    _validate(s)
    try:
        rule = rule_snapshot(rules, as_of)
    except RuleInputError as exc:
        raise PrerequisiteInputError('Selected draft rule is invalid for this assessment.') from exc
    assessment_context = {'as_of': as_of.isoformat(), **rule.evidence('release')}
    payload = rule.payload['release']
    instrument, obligation, basis = s['instrument'], s['obligation'], s['basis']
    if operation == 'PUBLIC_VERIFY':
        state = s['letter']['state']
        public_kind = {'FDR':'NOC','RPGF':'NOC','RTGS':'SANCTION_ORDER'}.get(case['mode'])
        if (state in {'ISSUED', 'REVOKED'} and _present(s['letter']['ref']) and
                public_kind is not None and s['letter']['kind'] == public_kind):
            return result('PUBLIC_REVOKED_RECORD_ONLY' if state == 'REVOKED' else 'PUBLIC_ISSUED_RECORD_ONLY',
                          ['LETTER_REVOKED'] if state == 'REVOKED' else [])
        return result('PUBLIC_NOT_FOUND', ['LETTER_NOT_FOUND'])
    if (case['instrument_id'] != instrument['id'] or
            {instrument['institution_id'], obligation['institution_id']} != {case['institution_id']}):
        return result('DENIED', ['CASE_CONTEXT_MISMATCH'])
    for doc in s['documents'].values():
        if doc is not None and (doc['institution_id'] != case['institution_id'] or doc['instrument_id'] != instrument['id']):
            return result('DENIED', ['EVIDENCE_SCOPE_MISMATCH'])
    if not set(basis['child_institution_ids']) <= scope or not {int(k) for k in basis['child_certificates']} <= scope:
        return result('DENIED', ['CHILD_SCOPE_MISMATCH'])
    role = actor['role_label']
    if role not in {'AUTHORITY', 'OFFICER', 'INSTITUTION'} or (
            operation in {'APPROVE', 'REJECT', 'COMPLETE', 'ISSUE_LETTER'} and role != 'AUTHORITY'):
        return result('DENIED', ['ACTION_ROLE_FORBIDDEN'])
    if operation == 'REQUEST' and (role != 'INSTITUTION' or actor['id'] != case['requester_id']):
        return result('DENIED', ['REQUEST_ACTOR_MISMATCH'])
    if operation in {'APPROVE', 'REJECT', 'COMPLETE', 'ISSUE_LETTER'} and actor['id'] == case['requester_id']:
        return result('DENIED', ['REQUESTER_SELF_DECISION'])
    if operation in {'APPROVE', 'REJECT'} and any(task is not None and task['actor_id'] == actor['id']
                                                for task in s['clearances'].values()):
        return result('DENIED', ['CLEARANCE_DECIDER_CONFLICT'])
    if case['expected_version'] != case['version']:
        return result('CONFLICT', ['STALE_VERSION'])
    if case['assessment_version'] != case['version']:
        return result('CONFLICT', ['STALE_ASSESSMENT'])
    if instrument['status'] is None or instrument['superseded'] is None or instrument['released'] is None:
        return result('CONTEXT_UNAVAILABLE', ['INSTRUMENT_CONTEXT_UNKNOWN'])
    if instrument['status'] != 'ACCEPTED' or instrument['superseded'] is not False or instrument['released'] is not False:
        return result('CONFLICT', ['INSTRUMENT_NOT_CURRENT'])
    if s['monitoring_active'] is not True:
        return result('CONFLICT', ['MONITORING_CONTEXT_INCONSISTENT'])
    if case['other_active_release'] is not False:
        return result('CONFLICT' if case['other_active_release'] else 'CONTEXT_UNAVAILABLE',
                      ['ACTIVE_RELEASE_EXISTS' if case['other_active_release'] else 'ACTIVE_RELEASE_STATUS_UNKNOWN'])
    if instrument['successor_proposal_exists'] is not False:
        return result('CONFLICT' if instrument['successor_proposal_exists'] else 'CONTEXT_UNAVAILABLE',
                      ['RENEWAL_CONFLICT' if instrument['successor_proposal_exists'] else 'RENEWAL_STATUS_UNKNOWN'])
    if case['path'] not in payload['paths']:
        return result('INVALID_INPUT', ['UNSUPPORTED_PATH'])
    if case['mode'] not in payload['mode_documents']:
        return result('INVALID_INPUT', ['UNSUPPORTED_MODE'])
    required_state = 'APPROVED' if operation in {'COMPLETE', 'ISSUE_LETTER'} else 'PENDING'
    if case['status'] != required_state:
        return result('CONFLICT', ['CASE_STATE_CONFLICT'])

    def issue(code, field, outcome='BLOCKED', values=None, clause='release'):
        findings.append({'code': code, 'field': field, 'outcome': outcome,
                         'as_of': as_of.isoformat(), **rule.evidence(clause),
                         'values': {} if values is None else values})

    def document(kind):
        doc = s['documents'].get(kind)
        field = 'documents.' + kind
        if doc is None or not _present(doc['ref']):
            issue('REQUIRED_DOCUMENT_MISSING', field)
            return False
        if doc['parse_status'] != 'VALID_SYNTHETIC_METADATA':
            issue('DOCUMENT_UNUSABLE', field, values={'parse_status': doc['parse_status']})
            return False
        if doc['review_status'] != 'REVIEWED_SYNTHETIC_METADATA':
            issue('DOCUMENT_REVIEW_REQUIRED', field)
            return False
        return True

    if not _present(s['decision_reason']):
        issue('REASON_REQUIRED', 'decision_reason')
    if s['document_context_complete'] is not True:
        issue('DOCUMENT_CONTEXT_UNAVAILABLE', 'document_context_complete', 'CONTEXT_UNAVAILABLE')
    else:
        for kind in payload['common_documents'] + [payload['mode_documents'][case['mode']]]:
            document(kind)
    affidavit = s['affidavit_review']
    if not _present(affidavit['template_ref']) or affidavit['reviewed'] is not True or affidavit['all_required_answers_recorded'] is not True:
        issue('AFFIDAVIT_REVIEW_INCOMPLETE', 'affidavit_review', 'CONTEXT_UNAVAILABLE')
    elif affidavit['signed_pdf_consistency'] != 'MATCHES_SYNTHETIC_REVIEW':
        issue('AFFIDAVIT_CONTRADICTION', 'affidavit_review.signed_pdf_consistency')
    path = case['path']
    if path == 'TERM_COMPLETE':
        term = _day(obligation['term_end'])
        if term is None or obligation['term_elapsed_reviewed'] is None:
            issue('TERM_BASIS_UNKNOWN', 'obligation', 'CONTEXT_UNAVAILABLE', clause='term')
        elif term == as_of:
            issue('TERM_END_BOUNDARY_UNRESOLVED', 'obligation.term_end', 'CONTEXT_UNAVAILABLE', clause='term')
        elif term > as_of or obligation['term_elapsed_reviewed'] is not True:
            issue('TERM_NOT_ELAPSED', 'obligation.term_end', values={'term_end': term.isoformat()}, clause='term')
    else:
        ref = ('merger_order_ref' if path == 'MERGER' else 'conversion_order_ref'
               if path == 'CONVERSION_TO_UNIVERSITY' else 'closure_order_ref')
        if not _present(basis[ref]):
            issue('PATH_BASIS_UNKNOWN', 'basis.' + ref, 'CONTEXT_UNAVAILABLE')
        if path == 'PROGRESSIVE_CLOSURE':
            if s['documents'].get('NO_STUDENTS_CERTIFICATE') is not None:
                document('NO_STUDENTS_CERTIFICATE')
            elif basis['deposit_matured_for_exception'] is None:
                issue('MATURITY_EXCEPTION_UNESTABLISHED', 'basis.deposit_matured_for_exception', 'CONTEXT_UNAVAILABLE')
            elif not (basis['deposit_matured_for_exception'] is True and basis['certificate_exception_reviewed'] is True):
                issue('NO_STUDENTS_CERTIFICATE_REQUIRED', 'documents.NO_STUDENTS_CERTIFICATE')
        if path == 'MERGER':
            if basis['child_scope_complete'] is not True or not basis['child_institution_ids']:
                issue('CHILD_SCOPE_UNKNOWN', 'basis.child_institution_ids', 'CONTEXT_UNAVAILABLE')
            elif any(not _present(basis['child_certificates'].get(str(child))) for child in basis['child_institution_ids']):
                issue('CHILD_CERTIFICATE_MISSING', 'basis.child_certificates')
    holds = s['holds']
    for flag in ['pending_complaints', 'pending_disciplinary_proceedings']:
        if holds[flag] is None:
            code = 'CONVERSION_COMPLAINT_STATUS_UNKNOWN' if path == 'CONVERSION_TO_UNIVERSITY' and flag == 'pending_complaints' else 'PROCEEDINGS_STATUS_UNKNOWN'
            issue(code, 'holds.' + flag, 'CONTEXT_UNAVAILABLE')
        elif holds[flag]:
            issue('CONVERSION_PROCEEDINGS_PENDING' if path == 'CONVERSION_TO_UNIVERSITY' else 'PROCEEDINGS_HOLD', 'holds.' + flag)
    if holds['trustee_dispute'] is True:
        issue('DISPUTE_HOLD', 'holds.trustee_dispute')
    elif holds['trustee_dispute'] is None:
        issue('HOLD_STATUS_UNKNOWN', 'holds.trustee_dispute', 'CONTEXT_UNAVAILABLE')
    if holds['financial_embezzlement'] is None:
        issue('HOLD_STATUS_UNKNOWN', 'holds.financial_embezzlement', 'CONTEXT_UNAVAILABLE')
    elif holds['financial_embezzlement']:
        if holds['external_noc_status'] != 'REVIEWED_SYNTHETIC_NOC':
            issue('EXTERNAL_NOC_REQUIRED', 'holds.external_noc_status')
        else:
            document('EXTERNAL_NOC')
    if operation != 'REQUEST':
        if s['clearance_context_complete'] is not True or not set(payload['clearance_units']) <= set(s['required_units']):
            issue('CLEARANCE_SCOPE_UNKNOWN', 'required_units', 'CONTEXT_UNAVAILABLE')
        else:
            for unit in sorted(s['required_units']):
                task = s['clearances'].get(unit)
                if task is None or task['status'] is None:
                    issue('CLEARANCE_UNAVAILABLE', 'clearances.' + unit, 'CONTEXT_UNAVAILABLE')
                elif task['status'] != 'CLEARED':
                    issue({'OPEN':'CLEARANCE_OPEN', 'OBJECTION':'CLEARANCE_OBJECTION', 'HOLD':'CLEARANCE_HOLD'}.get(
                        task['status'], 'CLEARANCE_UNAVAILABLE'), 'clearances.' + unit,
                        'BLOCKED' if task['status'] in {'OPEN','OBJECTION','HOLD'} else 'CONTEXT_UNAVAILABLE')
                elif task['actor_id'] is None or not _present(task['reason']) or not _present(task['evidence_ref']):
                    issue('CLEARANCE_EVIDENCE_INCOMPLETE', 'clearances.' + unit, 'CONTEXT_UNAVAILABLE')
        review = s['penalty_review']
        if review['assessments'] is None or review['status'] == 'UNAVAILABLE':
            issue('PENALTY_REVIEW_UNAVAILABLE', 'penalty_review', 'CONTEXT_UNAVAILABLE')
        else:
            if review['status'] == 'COMPLETE_NO_PENALTY' and review['assessments']:
                issue('PENALTY_CONTEXT_INCONSISTENT', 'penalty_review', 'INVALID_INPUT')
            if not review['assessments'] and review['status'] not in {'COMPLETE','COMPLETE_NO_PENALTY'}:
                issue('PENALTY_REVIEW_UNAVAILABLE', 'penalty_review', 'CONTEXT_UNAVAILABLE')
            for index, assessment in enumerate(review['assessments']):
                field = f'penalty_review.assessments.{index}'
                try:
                    proposal = penalty_proposal(assessment['kind'], assessment['base_paise'], rule, as_of=as_of)
                except RuleInputError:
                    issue('PENALTY_CONTEXT_UNSUPPORTED', field, 'CONTEXT_UNAVAILABLE')
                    continue
                if (assessment['rate_bps'], assessment['amount_paise']) != (proposal['rate_bps'], proposal['amount_paise']):
                    issue('PENALTY_ARITHMETIC_MISMATCH', field, 'INVALID_INPUT', clause=assessment['kind'])
                if assessment['status'] == 'WAIVED':
                    issue('WAIVER_AUTHORITY_UNESTABLISHED', field, 'CONTEXT_UNAVAILABLE', clause=assessment['kind'])
                elif assessment['status'] != 'CONFIRMED' or assessment['actor_id'] is None or not _present(assessment['reason']):
                    issue('PENALTY_DISPOSITION_PENDING', field, clause=assessment['kind'])
                elif review['status'] != 'COMPLETE':
                    issue('PENALTY_REVIEW_INCOMPLETE', field, 'CONTEXT_UNAVAILABLE', clause=assessment['kind'])
    kind = 'SANCTION_ORDER' if case['mode'] == 'RTGS' else 'NOC'
    if operation == 'ISSUE_LETTER':
        if s['letter']['state'] == 'GENERATION_FAILED':
            issue('LETTER_ISSUANCE_FAILED', 'letter.state', 'RETRYABLE_FAILURE')
        elif s['letter']['state'] != 'NOT_ISSUED':
            issue('LETTER_ALREADY_ISSUED_OR_REVOKED', 'letter.state', 'CONFLICT')
    if operation == 'COMPLETE':
        letter, completion = s['letter'], s['completion']
        if letter['state'] != 'ISSUED' or letter['kind'] != kind or not _present(letter['ref']):
            issue('ISSUED_LETTER_REQUIRED', 'letter')
        original_refs = {d['ref'] for d in s['documents'].values() if d and d['ref'] is not None}
        if (not _present(completion['new_evidence_ref']) or completion['evidence_is_new'] is not True or
                completion['new_evidence_ref'] in original_refs or completion['new_evidence_ref'] == letter['ref']):
            issue('NEW_COMPLETION_EVIDENCE_REQUIRED', 'completion.new_evidence_ref')
        elif completion['parse_status'] != 'VALID_SYNTHETIC_METADATA':
            issue('DOCUMENT_UNUSABLE', 'completion.parse_status')
        if not _present(completion['notes']):
            issue('COMPLETION_EXPLANATION_REQUIRED', 'completion.notes')
        if case['mode'] == 'RTGS' and not _present(completion['refund_reference']):
            issue('REFUND_REFERENCE_REQUIRED', 'completion.refund_reference')
    if findings:
        priority = ['CONFLICT', 'INVALID_INPUT', 'CONTEXT_UNAVAILABLE', 'BLOCKED', 'RETRYABLE_FAILURE']
        return result(next(outcome for outcome in priority if any(f['outcome'] == outcome for f in findings)))
    outcomes = {'ASSESS':'READY_FOR_AUTHORITY_REVIEW', 'REQUEST':'REQUEST_PREREQUISITES_MET_IN_DEMO',
                'APPROVE':'AUTHORIZATION_RECORDABLE_IN_DEMO', 'REJECT':'REJECTION_RECORDABLE_IN_DEMO',
                'ISSUE_LETTER':'LETTER_PREREQUISITES_MET_IN_DEMO', 'COMPLETE':'COMPLETION_RECORDABLE_IN_DEMO'}
    projection = {'proposed_letter_kind': kind}
    if operation in {'APPROVE','REJECT','COMPLETE'}:
        projection['case_status_after_action'] = {'APPROVE':'APPROVED','REJECT':'REJECTED','COMPLETE':'COMPLETED'}[operation]
    if operation == 'COMPLETE':
        projection['monitoring_after_action'] = False
    return result(outcomes[operation], **projection)
