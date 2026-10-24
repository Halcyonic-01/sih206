"""Independent S2 calculations over explicit, institution-scoped input snapshots."""
from dataclasses import dataclass
from datetime import date, timedelta

from .rules import RuleInputError, add_days, day, integer, rule_snapshot


@dataclass(frozen=True)
class ApprovalInput:
    programme: str
    level: str
    land_tenure: str
    building_tenure: str


def required_amount(approvals, ruleset, *, as_of, institution_type='PRIVATE'):
    rule = rule_snapshot(ruleset, as_of)
    if not isinstance(institution_type, str) or institution_type not in {'PRIVATE', 'GOVERNMENT', 'AIDED', 'UNIVERSITY'}:
        raise RuleInputError('Unknown institution type.')
    approvals = tuple(approvals)
    if not approvals:
        raise RuleInputError('No programme approvals supplied; requirement is unknown, not zero.')
    seen, rows = set(), []
    # Leased land OR building doubles the aggregate once, not once per asset.
    leased = False
    for approval in approvals:
        if not all(isinstance(value, str) for value in (
                approval.programme, approval.level, approval.land_tenure, approval.building_tenure)):
            raise RuleInputError('Programme, level and both tenures must be text codes.')
        key = (approval.programme, approval.level)
        if key in seen:
            raise RuleInputError('Duplicate programme/level; select the applicable approval once.')
        seen.add(key)
        if approval.land_tenure not in {'OWNED', 'LEASED'} or approval.building_tenure not in {'OWNED', 'LEASED'}:
            raise RuleInputError('Both land and building tenure must be known.')
        amount = rule.payload['amounts'].get(approval.programme, {}).get(approval.level)
        if amount is None:
            raise RuleInputError('Unsupported programme/level; no zero amount is inferred.')
        leased |= approval.land_tenure == 'LEASED' or approval.building_tenure == 'LEASED'
        rows.append({'programme': approval.programme, 'level': approval.level, 'base_paise': amount})
    multiplier = rule.payload['leased_multiplier'] if leased and institution_type == 'PRIVATE' else 1
    return {'required_paise': sum(row['base_paise'] for row in rows) * multiplier,
            'multiplier': multiplier, 'breakdown': rows, 'as_of': as_of.isoformat(),
            'exemption_assessed': False, **rule.evidence('amount')}


def term_end(start, ruleset, *, as_of):
    rule = rule_snapshot(ruleset, as_of)
    day(start, 'term start')
    year = start.year + rule.payload['term_years']
    if year > 9999:
        raise RuleInputError('Term end is outside the supported date range.')
    # Explicit demo convention: leap-day anniversary falls on February 28.
    try:
        return start.replace(year=year)
    except ValueError:
        return date(year, 2, 28)


@dataclass(frozen=True)
class ObligationInput:
    id: int
    institution_id: int
    required_paise: int | None
    term_start: date | None
    term_end: date | None


@dataclass(frozen=True)
class HoldingInput:
    id: int
    institution_id: int
    obligation_id: int
    amount_paise: int
    issue_date: date
    maturity_date: date
    status: str = 'ACCEPTED'
    superseded: bool = False
    released: bool = False


def coverage(obligation, as_of, *, holdings):
    """No ORM fallback: missing Y1 linkage must never appear as an empty ledger."""
    day(as_of, 'as_of')
    for value in [obligation.id, obligation.institution_id]:
        integer(value, 'identity', 1)
    if holdings is None:
        raise RuleInputError('TODO(Y1): supply explicitly scoped holdings; no implicit ORM lookup.')
    holdings = tuple(holdings)
    seen, eligible = set(), []
    for holding in holdings:
        integer(holding.id, 'holding identity', 1)
        integer(holding.institution_id, 'holding institution', 1)
        integer(holding.obligation_id, 'holding obligation', 1)
        if holding.id in seen:
            raise RuleInputError('Duplicate holding identity would double-count coverage.')
        seen.add(holding.id)
        if (holding.institution_id, holding.obligation_id) != (obligation.institution_id, obligation.id):
            raise RuleInputError('Holding is outside the supplied institution/obligation.')
        integer(holding.amount_paise, 'holding amount', 1)
        day(holding.issue_date, 'issue_date')
        day(holding.maturity_date, 'maturity_date')
        if holding.maturity_date < holding.issue_date:
            raise RuleInputError('Holding maturity precedes issue.')
        if not isinstance(holding.status, str) or holding.status not in {'DRAFT', 'SUBMITTED', 'CHANGES_REQUESTED', 'ACCEPTED'}:
            raise RuleInputError('Unknown holding review status.')
        if type(holding.superseded) is not bool or type(holding.released) is not bool:
            raise RuleInputError('Lifecycle flags must be booleans.')
        if holding.status == 'ACCEPTED' and not holding.superseded and not holding.released:
            eligible.append(holding)
    if (obligation.term_start is None) != (obligation.term_end is None):
        raise RuleInputError('Both term dates or neither are required.')
    if obligation.term_start is not None:
        day(obligation.term_start, 'term_start')
        day(obligation.term_end, 'term_end')
        if obligation.term_end < obligation.term_start:
            raise RuleInputError('Invalid obligation term.')
    required = obligation.required_paise
    if required is not None:
        integer(required, 'required amount')
    def held_on(when):
        return sum(h.amount_paise for h in eligible if h.issue_date <= when <= h.maturity_date)
    held = held_on(as_of)
    shortfall = None if required is None else max(required - held, 0)
    coverage_end, gap_days, first_gap = None, None, None
    if required is not None and obligation.term_end is not None:
        start = max(as_of, obligation.term_start)
        if start > obligation.term_end or required == 0:
            gap_days = 0
        else:
            # Evaluate each date where coverage can change. A later top-up cannot
            # hide an earlier uncovered interval; redundant short FDRs do not
            # shorten coverage provided sufficient long holdings remain.
            boundaries = {start}
            for h in eligible:
                if start <= h.issue_date <= obligation.term_end:
                    boundaries.add(h.issue_date)
                if h.maturity_date < date.max:
                    end = h.maturity_date + timedelta(days=1)
                    if start <= end <= obligation.term_end:
                        boundaries.add(end)
            first_gap = next((d for d in sorted(boundaries) if held_on(d) < required), None)
            coverage_end = first_gap - timedelta(days=1) if first_gap and first_gap > start else (
                None if first_gap else obligation.term_end)
            gap_days = (obligation.term_end - first_gap).days + 1 if first_gap else 0
    return {'obligation_id': obligation.id, 'institution_id': obligation.institution_id,
            'as_of': as_of.isoformat(), 'required_paise': required, 'held_paise': held,
            'shortfall_paise': shortfall, 'coverage_end': coverage_end.isoformat() if coverage_end else None,
            'term_gap_days': gap_days,
            'first_uncovered_on': first_gap.isoformat() if first_gap else None,
            'holding_ids': [h.id for h in eligible if h.issue_date <= as_of <= h.maturity_date]}


def penalty_proposal(kind, base_paise, ruleset, *, as_of, intimation_date=None,
                     proof_completed_on=None, cycle_year=None):
    rule = rule_snapshot(ruleset, as_of)
    integer(base_paise, 'penalty base', 1)
    if not isinstance(kind, str):
        raise RuleInputError('Penalty kind must be a text code.')
    rates = rule.payload['penalties_bps']
    if kind == 'late_proof':
        day(intimation_date, 'intimation_date')
        if intimation_date > as_of:
            raise RuleInputError('Intimation cannot be in the future.')
        evaluated = as_of
        if proof_completed_on is not None:
            day(proof_completed_on, 'proof_completed_on')
            if proof_completed_on > as_of:
                raise RuleInputError('Completed proof cannot be in the future.')
            evaluated = proof_completed_on
        due = add_days(intimation_date, rule.payload['proof_days'])
        if evaluated <= due:
            rate = 0
        else:
            integer(cycle_year, 'explicit approval cycle year', 1)
            if cycle_year != evaluated.year or cycle_year != intimation_date.year:
                raise RuleInputError('Cross-year penalty interpretation requires human policy review.')
            rate = rates['late_proof_may'] if evaluated <= date(cycle_year, 5, 31) else (
                rates['late_proof_july'] if evaluated <= date(cycle_year, 7, 31) else None)
    elif kind in {'premature_encashment', 'closure_lapsed', 'closure_six_years'}:
        rate = rates[kind]
    else:
        raise RuleInputError('Unsupported penalty kind.')
    return {'kind': kind, 'base_paise': base_paise, 'rate_bps': rate,
            'amount_paise': None if rate is None else (base_paise * rate + 5000) // 10000,
            'status': 'REQUIRES_AUTHORITY_REVIEW' if rate is None else ('NOT_DUE' if rate == 0 else 'PROPOSED'),
            'rounding': 'HALF_UP_TO_PAISE_DEMO_CONVENTION', 'human_confirmation_required': True,
            **rule.evidence(kind)}
