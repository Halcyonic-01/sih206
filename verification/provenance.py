"""Where each declared value stands: declared, document-reviewed, confirmed by an independent source, or contradicted (P1-5).

Derived on read from append-only evidence and the audit trail; nothing is stored. A field is judged against the value
the record holds *now*: evidence that saw a different value no longer confirms it, and evidence that saw a different value
is a mismatch while the two disagree. "Confirmed" here means a statement line or bank response agreed with the
value; in this prototype both are SIMULATED and never establish bank authenticity.
"""
from decimal import Decimal, InvalidOperation

DECLARED, DOCUMENT_REVIEWED, CONFIRMED, MISMATCH = 'DECLARED', 'DOCUMENT_REVIEWED', 'CONFIRMED', 'MISMATCH'
FIELDS = ('amount', 'reference', 'ifsc', 'bank', 'holder_names', 'issue_date', 'maturity_date', 'utr', 'lien_marked')
_RANK = {DECLARED: 0, DOCUMENT_REVIEWED: 1, CONFIRMED: 2, MISMATCH: 3}
_SNAPSHOT_TO_FIELD = {'amount_paise': 'amount'} | {name: name for name in FIELDS}
_LABELS = {'OFFICER_REVIEW': 'Officer review', 'SIMULATED_STATEMENT': 'Bank statement line',
           'SIMULATED_BANK': 'Bank email confirmation', 'BANK_CONFIRMATION': 'Bank email confirmation'}


def _text(value):
    return ' '.join(str(value or '').split()).casefold()


def _current(item):
    return {'amount': item.amount_paise, 'reference': _text(item.reference), 'ifsc': _text(item.ifsc),
            'bank': _text(item.bank), 'holder_names': _text(item.holder_names),
            'issue_date': item.issue_date.isoformat(), 'maturity_date': item.maturity_date.isoformat(),
            'utr': _text(item.utr), 'lien_marked': item.lien_marked}


def _observed(evidence):
    """What one evidence row saw, in the same normal form as `_current`; fields it did not look at are absent."""
    seen = evidence.fields_observed or {}
    if evidence.method == 'SIMULATED_STATEMENT':
        values = {}
        if 'utr' in seen:
            values['utr'] = _text(seen['utr'])
        if type(seen.get('amount_paise')) is int:
            values['amount'] = seen['amount_paise']
        if 'value_date' in seen:
            values['issue_date'] = str(seen['value_date'])
        return values
    if evidence.method in ('SIMULATED_BANK', 'BANK_CONFIRMATION'):
        values = {}
        for key in ('reference', 'ifsc', 'holder_names'):
            if key in seen:
                values[key] = _text(seen[key])
        for key in ('issue_date', 'maturity_date'):
            if key in seen:
                values[key] = str(seen[key])
        if 'lien_marked' in seen:
            values['lien_marked'] = {'yes': True, 'no': False}.get(seen['lien_marked'])
        if 'amount' in seen:
            try:
                values['amount'] = int(Decimal(str(seen['amount'])) * 100)
            except (InvalidOperation, ValueError):
                pass
        return values
    return {}


def _corrected_after(corrections, reviewed_at):
    changed = set()
    for event in corrections:
        if event.created_at > reviewed_at:
            for key, name in _SNAPSHOT_TO_FIELD.items():
                if (event.before or {}).get(key) != (event.after or {}).get(key):
                    changed.add(name)
    return changed


def derive(item, evidence, corrections=()):
    """`evidence`: the instrument's VerificationEvidence rows; `corrections`: its OFFICER_CORRECTION audit events."""
    current = _current(item)
    result = {name: {'status': DECLARED, 'source': 'Entered by the institution', 'simulated': False,
                     'evidence_id': None, 'at': None} for name in FIELDS}

    def raise_to(name, status, row, simulated):
        if _RANK[status] > _RANK[result[name]['status']]:
            result[name] = {'status': status, 'source': _LABELS.get(row.method, row.method) + (' (SIMULATED)' if simulated else ''),
                            'simulated': simulated, 'evidence_id': row.pk, 'at': row.created_at}

    rows = sorted(evidence, key=lambda row: row.pk, reverse=True)
    review = next((row for row in rows if row.method == 'OFFICER_REVIEW'), None)
    if review is not None:
        for name in set(FIELDS) - _corrected_after(corrections, review.created_at):
            raise_to(name, DOCUMENT_REVIEWED, review, False)
    done = set()
    for row in rows:  # newest first: the latest evidence that looked at a field decides it
        if row.method == 'OFFICER_REVIEW':
            continue
        simulated = row.method.startswith('SIMULATED')
        denied = row.method in ('SIMULATED_BANK', 'BANK_CONFIRMATION') and (row.fields_observed or {}).get('authentic') != 'yes'
        for name, value in _observed(row).items():
            if name in done:
                continue
            done.add(name)
            raise_to(name, CONFIRMED if value == current[name] and not denied else MISMATCH, row, simulated)
    return result
