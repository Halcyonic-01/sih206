"""Advisory v3 obligation checks; not wired into the existing portal decisions."""
from portal.validation import Finding
from .calculations import coverage
from .rules import RuleInputError, add_days, day, rule_snapshot

CHECKS_VERSION = 'obligations-v3-draft'


def obligation_findings(obligation, ruleset, *, as_of, holdings,
                        intimation_date=None, payment_proof_on=None, affidavit_on=None):
    rule = rule_snapshot(ruleset, as_of)
    result = coverage(obligation, as_of, holdings=holdings)
    findings = []
    def finding(code, clause, message, values):
        return Finding(code, 'warning', message, {
            'checks_version': CHECKS_VERSION, 'as_of': as_of.isoformat(),
            'obligation_id': obligation.id, **rule.evidence(clause), **values})
    if result['shortfall_paise']:
        findings.append(finding('AMOUNT_SHORTFALL', 'amount',
            'Draft rule assessment: current eligible holdings are below the supplied requirement.',
            {key: result[key] for key in ['required_paise', 'held_paise', 'shortfall_paise', 'holding_ids']}))
    if result['term_gap_days']:
        findings.append(finding('TERM_GAP', 'term',
            'Draft rule assessment: continuous coverage does not reach the supplied obligation term end.',
            {key: result[key] for key in ['coverage_end', 'term_gap_days', 'first_uncovered_on']} |
            {'term_end': obligation.term_end.isoformat(),
             'action_due_on': result['coverage_end'] or result['first_uncovered_on']}))
    for name, value in [('payment_proof_on', payment_proof_on), ('affidavit_on', affidavit_on)]:
        if value is not None:
            day(value, name)
            if value > as_of:
                raise RuleInputError('Future document receipt cannot satisfy proof requirements.')
    if intimation_date is not None:
        day(intimation_date, 'intimation_date')
        due = add_days(intimation_date, rule.payload['proof_days'])
        missing = [kind for kind, received in [('PAYMENT_PROOF', payment_proof_on),
                                              ('AFFIDAVIT_3', affidavit_on)] if received is None]
        if as_of > due and missing:
            findings.append(finding('PROOF_OVERDUE', 'proof',
                'Draft rule assessment: payment proof and Affidavit-3 are not both recorded by the deadline.',
                {'due_date': due.isoformat(), 'days_overdue': (as_of - due).days,
                 'missing_documents': missing}))
    return findings
