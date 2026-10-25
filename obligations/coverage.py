"""Read-only coverage of explicitly reviewed requirements; never invent a policy."""
from portal.models import Instrument


def coverage(obligation, as_of):
    rule = obligation.rule_version
    sourced = bool(rule and rule.source_clause and rule.source_document)
    reviewed = sourced and bool(rule.approved_by_id)
    exempt = obligation.status == 'EXEMPT' and bool(obligation.exemption_approved_by_id)
    # A recorded requirement under a sourced rule set is assessed, as on the institution page (S2); a draft rule
    # set is labelled DRAFT_DEMO_NOT_APPROVED rather than hidden. No rule set or amount stays unknown.
    known = exempt or (sourced and obligation.required_paise is not None)
    holdings = list(obligation.instruments.filter(status='ACCEPTED', superseded_at__isnull=True,
        released_at__isnull=True, issue_date__lte=as_of, maturity_date__gte=as_of)
        .order_by('-maturity_date', 'pk'))
    from .calculations import coverage as calculate, HoldingInput, ObligationInput
    required = obligation.required_paise if known else None
    ledger = calculate(ObligationInput(obligation.pk, obligation.institution_id, required,
        obligation.term_start, obligation.term_end), as_of, holdings=tuple(HoldingInput(
        item.pk, item.institution_id, item.obligation_id, item.amount_paise, item.issue_date,
        item.maturity_date, item.status, False, False) for item in holdings))
    held, shortfall, end = ledger['held_paise'], ledger['shortfall_paise'], ledger['coverage_end']
    return {'obligation_id': obligation.pk, 'institution_id': obligation.institution_id,
        'institution': obligation.institution.name, 'known': known, 'required_paise': required,
        'held_paise': held, 'shortfall_paise': shortfall, 'coverage_end': end,
        'term_end': obligation.term_end, 'term_gap': bool(known and ledger['term_gap_days']), 'exempt': exempt,
        'policy_label': 'APPROVED' if reviewed else 'DRAFT_DEMO_NOT_APPROVED',
        'holdings': [item.pk for item in holdings],
        'notice': 'Accepted holdings are tracked amounts, not independently bank-confirmed funds.'}


def scoped_obligations(user):
    from portal.permissions import institution_for, role
    from .models import DepositObligation
    items = DepositObligation.objects.select_related('institution', 'rule_version')
    if role(user) in ('officer', 'authority'):
        return items
    return items.filter(institution=institution_for(user))
