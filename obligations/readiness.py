"""Pure deposit-readiness calculation over explicit, already scoped facts.

This module performs no queries, authorization, policy publication or writes.
The future server adapter must supply current records and permission intents.
Readiness is a count of tracked steps, never a compliance certificate.
"""
from datetime import date, timedelta


ITEMS = ('accepted_deposit', 'payment_proof', 'affidavit_3', 'amount_coverage',
         'proof_receipt', 'bank_confirmation')
ACTIONS = {
    'accepted_deposit': 'OPEN_DEPOSIT_WORKFLOW', 'payment_proof': 'UPLOAD_PAYMENT_PROOF',
    'affidavit_3': 'UPLOAD_AFFIDAVIT_3', 'amount_coverage': 'VIEW_REQUIREMENT',
    'proof_receipt': 'RECORD_PROOF_RECEIPTS', 'bank_confirmation': 'VIEW_BANK_VERIFICATION',
}
BANK_STATES = {'CURRENT_CONFIRMED', 'MISSING', 'DISCREPANCY', 'SIMULATED', 'STALE', 'UNKNOWN'}


class ReadinessInputError(ValueError):
    pass


def _integer(value, name, minimum=0):
    if type(value) is not int or not minimum <= value <= 10**18:
        raise ReadinessInputError(f'{name} must be an integer in the supported range.')
    return value


def _day(value, name, *, nullable=False):
    if value is None and nullable:
        return None
    try:
        if type(value) is not str:
            raise ValueError()
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError()
        return parsed
    except ValueError as exc:
        raise ReadinessInputError(f'{name} must be a YYYY-MM-DD date or explicit unknown.') from exc


def _flag(value, name):
    if value is not None and type(value) is not bool:
        raise ReadinessInputError(f'{name} must be boolean or explicit unknown.')
    return value


def _progress(complete, applicable):
    # Integer half-up rounding, with no floating-point/banker's-rounding surprise.
    return (100 * complete * 2 + applicable) // (2 * applicable) if applicable else None


def calculate(snapshot, *, institution_id):
    """Return one obligation's six milestones without modifying the input.

    Snapshot IDs are scope assertions, not proof of authorization. Never expose
    this pure function directly to client JSON as an authoritative assessment.
    """
    _integer(institution_id, 'requested institution', 1)
    if type(snapshot) is not dict:
        raise ReadinessInputError('A complete readiness snapshot is required.')
    required = {'schema', 'institution_id', 'obligation_id', 'as_of', 'mode', 'applicability',
                'facts', 'deadline', 'allowed_actions', 'policy_source'}
    if set(snapshot) != required or type(snapshot['schema']) is not int or snapshot['schema'] != 1:
        raise ReadinessInputError('Unexpected or incomplete readiness snapshot.')
    if _integer(snapshot['institution_id'], 'snapshot institution', 1) != institution_id:
        raise ReadinessInputError('Snapshot belongs to another institution.')
    _integer(snapshot['obligation_id'], 'obligation', 1)
    when = _day(snapshot['as_of'], 'as_of')
    if snapshot['mode'] not in ('FDR', 'RTGS', 'RPGF'):
        raise ReadinessInputError('Unsupported deposit mode.')
    applicability = snapshot['applicability']
    if type(applicability) is not dict or set(applicability) != set(ITEMS):
        raise ReadinessInputError('All six applicability decisions must be explicit.')
    for key, value in applicability.items():
        _flag(value, f'applicability.{key}')
    allowed = snapshot['allowed_actions']
    if (type(allowed) is not list or any(type(code) is not str or code not in ACTIONS.values() for code in allowed)
            or len(allowed) != len(set(allowed))):
        raise ReadinessInputError('Unknown or duplicate action intent.')
    if type(snapshot['policy_source']) is not str or not 0 < len(snapshot['policy_source']) <= 500:
        raise ReadinessInputError('A bounded policy/context source label is required.')
    facts = snapshot['facts']
    keys = {'accepted_current', 'payment_proof_uploaded', 'affidavit_3_uploaded', 'required_paise',
            'held_paise', 'proof_reviewed', 'payment_proof_on', 'affidavit_on', 'bank_status'}
    if type(facts) is not dict or set(facts) != keys:
        raise ReadinessInputError('Incomplete or unexpected source facts.')
    for key in ('accepted_current', 'payment_proof_uploaded', 'affidavit_3_uploaded', 'proof_reviewed'):
        _flag(facts[key], key)
    for key in ('required_paise', 'held_paise'):
        if facts[key] is not None:
            _integer(facts[key], key)
    if type(facts['bank_status']) is not str or facts['bank_status'] not in BANK_STATES:
        raise ReadinessInputError('Unsupported bank-evidence state.')
    receipts = [_day(facts[key], key, nullable=True) for key in ('payment_proof_on', 'affidavit_on')]
    if any(value and value > when for value in receipts):
        raise ReadinessInputError('Receipt dates cannot be in the future.')
    if facts['proof_reviewed'] is not True and any(receipts):
        raise ReadinessInputError('Receipt dates require an explicit officer review.')
    deadline = snapshot['deadline']
    if type(deadline) is not dict or set(deadline) != {'intimation_date', 'proof_days'}:
        raise ReadinessInputError('Deadline provenance must be explicit.')
    intimation = _day(deadline['intimation_date'], 'intimation_date', nullable=True)
    days = deadline['proof_days']
    if days is not None:
        _integer(days, 'proof_days', 1)
        if days > 366:
            raise ReadinessInputError('Proof deadline interval exceeds the supported scope.')
    if intimation and intimation > when:
        raise ReadinessInputError('Intimation cannot be in the future.')
    due = None
    if intimation is not None and days is not None:
        try:
            due = intimation + timedelta(days=days)
        except OverflowError as exc:
            raise ReadinessInputError('Deadline is outside the supported date range.') from exc
    remaining = (due - when).days if due else None
    deadline_info = {'due_on': due.isoformat() if due else None, 'days_remaining': remaining,
        'state': 'UNKNOWN' if due is None else 'OVERDUE' if remaining < 0 else 'DUE_TODAY' if remaining == 0 else 'UPCOMING'}

    def binary(value):
        return ('UNKNOWN', 'SOURCE_UNKNOWN') if value is None else (
            ('COMPLETE', 'RECORDED') if value else ('INCOMPLETE', 'NOT_RECORDED'))

    states = {
        'accepted_deposit': binary(facts['accepted_current']),
        'payment_proof': binary(facts['payment_proof_uploaded']),
        'affidavit_3': binary(facts['affidavit_3_uploaded']),
    }
    required_amount, held = facts['required_paise'], facts['held_paise']
    states['amount_coverage'] = ('UNKNOWN', 'AMOUNT_CONTEXT_UNKNOWN') if required_amount is None or held is None else (
        ('COMPLETE', 'RECORDED_AMOUNT_COVERS_REQUIREMENT') if held >= required_amount
        else ('INCOMPLETE', 'RECORDED_SHORTFALL'))
    # Payment-proof upload can be inapplicable for FDR while receipt of the
    # deposit's FDR proof still applies. An explicitly inapplicable affidavit
    # must not require a fictional affidavit receipt date.
    receipt_unknown = ((applicability['accepted_deposit'] is None and applicability['payment_proof'] is not True)
                       or applicability['affidavit_3'] is None)
    needed_receipts = ([receipts[0]] if applicability['accepted_deposit'] is True
                       or applicability['payment_proof'] is True else [])
    if applicability['affidavit_3'] is True:
        needed_receipts.append(receipts[1])
    if applicability['proof_receipt'] is True and not needed_receipts and not receipt_unknown:
        raise ReadinessInputError('Receipt review cannot apply when no applicable proof requires receipt.')
    if facts['proof_reviewed'] is None or receipt_unknown:
        states['proof_receipt'] = ('UNKNOWN', 'RECEIPT_REVIEW_UNKNOWN')
    elif facts['proof_reviewed'] and all(needed_receipts):
        states['proof_receipt'] = ('COMPLETE', 'OFFICER_RECEIPT_DATES_RECORDED')
    else:
        states['proof_receipt'] = ('INCOMPLETE', 'OFFICER_RECEIPT_REVIEW_OR_DATES_MISSING')
    bank = facts['bank_status']
    states['bank_confirmation'] = {
        'CURRENT_CONFIRMED': ('COMPLETE', 'CURRENT_BANK_RESPONSE_RECORDED'),
        'SIMULATED': ('SIMULATED', 'SIMULATED_NOT_INDEPENDENTLY_CONFIRMED'),
        'DISCREPANCY': ('BLOCKED', 'BANK_DISCREPANCY'), 'STALE': ('UNKNOWN', 'BANK_EVIDENCE_STALE'),
        'MISSING': ('INCOMPLETE', 'NO_BANK_CONFIRMATION'), 'UNKNOWN': ('UNKNOWN', 'BANK_SOURCE_UNKNOWN'),
    }[bank]
    rows = []
    for key in ITEMS:
        applicable = applicability[key]
        state, reason = ('NOT_APPLICABLE', 'EXPLICIT_APPLICABILITY') if applicable is False else (
            ('UNKNOWN', 'APPLICABILITY_UNKNOWN') if applicable is None else states[key])
        action = ACTIONS[key] if state not in {'COMPLETE', 'NOT_APPLICABLE'} and ACTIONS[key] in allowed else None
        rows.append({'id': key, 'state': state, 'reason': reason, 'next_action': action,
            'deadline': dict(deadline_info) if key in {'payment_proof', 'affidavit_3', 'proof_receipt'}
                and state not in {'COMPLETE', 'NOT_APPLICABLE'} else None})
    complete = sum(row['state'] == 'COMPLETE' for row in rows)
    applicable_count = sum(row['state'] != 'NOT_APPLICABLE' for row in rows)
    return {'schema': 1, 'institution_id': institution_id, 'obligation_id': snapshot['obligation_id'],
        'as_of': when.isoformat(), 'label': 'Deposit readiness — recorded milestones, not regulatory compliance',
        'mode': snapshot['mode'], 'policy_source': snapshot['policy_source'], 'items': rows,
        'completed': complete, 'applicable': applicable_count, 'percent': _progress(complete, applicable_count),
        'unknown': sum(row['state'] == 'UNKNOWN' for row in rows),
        'simulated': sum(row['state'] == 'SIMULATED' for row in rows),
        'status': 'NOT_APPLICABLE' if not applicable_count else 'RECORDED_STEPS_COMPLETE'
            if complete == applicable_count else 'ACTION_OR_REVIEW_NEEDED'}


def aggregate(snapshots, *, institution_id):
    """Sum scoped obligation milestones, not an unweighted mean of percentages."""
    _integer(institution_id, 'institution', 1)
    if type(snapshots) is not list or len(snapshots) > 1000:
        raise ReadinessInputError('Supply a bounded obligation snapshot list.')
    rows = [calculate(snapshot, institution_id=institution_id) for snapshot in snapshots]
    if len({row['obligation_id'] for row in rows}) != len(rows):
        raise ReadinessInputError('Duplicate obligations would double-count readiness.')
    if len({row['as_of'] for row in rows}) > 1:
        raise ReadinessInputError('Institution summary requires one evaluation date.')
    complete, applicable = sum(row['completed'] for row in rows), sum(row['applicable'] for row in rows)
    return {'institution_id': institution_id, 'obligations': rows, 'completed': complete,
        'applicable': applicable, 'percent': _progress(complete, applicable),
        'status': 'NO_OBLIGATIONS' if not rows else 'NOT_APPLICABLE' if not applicable else
            'RECORDED_STEPS_COMPLETE' if complete == applicable else 'ACTION_OR_REVIEW_NEEDED'}
