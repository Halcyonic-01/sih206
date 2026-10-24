"""Read-only coverage of explicitly reviewed requirements; never invent a policy."""
from portal.models import Instrument


def coverage(obligation, as_of):
    rule = obligation.rule_version
    reviewed = bool(rule and rule.approved_by_id and rule.source_clause and rule.source_document)
    exempt = obligation.status == 'EXEMPT' and bool(obligation.exemption_approved_by_id)
    known = exempt or (reviewed and obligation.required_paise is not None and obligation.status != 'UNKNOWN')
    holdings = list(obligation.instruments.filter(status='ACCEPTED', superseded_at__isnull=True,
        released_at__isnull=True, issue_date__lte=as_of, maturity_date__gte=as_of)
        .order_by('-maturity_date', 'pk'))
    held = sum(item.amount_paise for item in holdings)
    required = obligation.required_paise if known else None
    shortfall = max(0, required-held) if required is not None else None
    end, accumulated = None, 0
    if required and shortfall == 0:
        for item in holdings:
            accumulated += item.amount_paise
            if accumulated >= required:
                end = item.maturity_date
                break
    return {'obligation_id': obligation.pk, 'institution_id': obligation.institution_id,
        'institution': obligation.institution.name, 'known': known, 'required_paise': required,
        'held_paise': held, 'shortfall_paise': shortfall, 'coverage_end': end,
        'term_end': obligation.term_end, 'term_gap': bool(known and required and obligation.term_end and
            (end is None or end < obligation.term_end)), 'exempt': exempt,
        'holdings': [item.pk for item in holdings],
        'notice': 'Accepted holdings are tracked amounts, not independently bank-confirmed funds.'}


def scoped_obligations(user):
    from portal.permissions import institution_for, role
    from .models import DepositObligation
    items = DepositObligation.objects.select_related('institution', 'rule_version')
    if role(user) in ('officer', 'authority'):
        return items
    return items.filter(institution=institution_for(user))
