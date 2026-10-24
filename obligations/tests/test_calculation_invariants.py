"""Bounded synthetic invariants, independent daily oracle and error boundaries.

No Hypothesis dependency, database, HTTP adapter or policy interpretation added.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta
from fractions import Fraction
from itertools import permutations, product
import random

from django.test import SimpleTestCase

from obligations.calculations import coverage, penalty_proposal, required_amount, term_end
from obligations.catalogue import draft_payload
from obligations.checks import obligation_findings
from obligations.rules import RuleInputError
from .test_calculations import TODAY, approval, holding, obligation, rules


def daily_oracle(item, as_of, holdings):
    """Enumerate every day; deliberately does not use S2's boundary algorithm."""
    eligible = [h for h in holdings if h.status == 'ACCEPTED'
                and h.superseded is False and h.released is False]
    current = [h for h in eligible if h.issue_date <= as_of <= h.maturity_date]
    held = sum(h.amount_paise for h in current)
    first_gap = end = gap = None
    if item.required_paise is not None and item.term_end is not None:
        days = (item.term_end - max(as_of, item.term_start)).days + 1
        day = max(as_of, item.term_start)
        for offset in range(max(days, 0)):
            on = day + timedelta(days=offset)
            balance = sum(h.amount_paise for h in eligible
                          if h.issue_date <= on <= h.maturity_date)
            if balance < item.required_paise:
                first_gap = on
                break
        gap = 0 if first_gap is None else (item.term_end - first_gap).days + 1
        if days > 0 and item.required_paise != 0:
            if first_gap is None:
                end = item.term_end
            elif first_gap > day:
                end = first_gap - timedelta(days=1)
    return dict(held_paise=held,
        shortfall_paise=None if item.required_paise is None else max(item.required_paise - held, 0),
        first_uncovered_on=first_gap.isoformat() if first_gap else None,
        coverage_end=end.isoformat() if end else None, term_gap_days=gap,
        holding_ids=[h.id for h in current])


class CoverageInvariantTests(SimpleTestCase):
    def test_400_generated_ledgers_match_independent_daily_oracle(self):
        rng = random.Random(26265)
        outcomes = set()
        for case in range(400):
            start = date(2024, 2, 26) if case % 2 else date(2026, 12, 27)
            end = start + timedelta(days=12)
            as_of = start + timedelta(days=rng.randrange(-2, 16))
            item = obligation(required_paise=rng.choice([None, 0, 1, 50, 100]),
                              term_start=start, term_end=end)
            rows = []
            for identity in range(1, rng.randrange(1, 7)):
                issue = start + timedelta(days=rng.randrange(-3, 16))
                rows.append(holding(id=identity, amount_paise=rng.choice([1, 25, 60, 100]),
                    issue_date=issue, maturity_date=issue + timedelta(days=rng.randrange(0, 18)),
                    status=rng.choice(['ACCEPTED', 'ACCEPTED', 'DRAFT', 'SUBMITTED', 'CHANGES_REQUESTED']),
                    superseded=rng.choice([False, False, True]),
                    released=rng.choice([False, False, True])))
            with self.subTest(case=case, item=item, as_of=as_of, holdings=rows):
                actual = coverage(item, as_of, holdings=rows)
                outcomes.add('unknown' if actual['term_gap_days'] is None else
                             'covered' if actual['term_gap_days'] == 0 else 'gap')
                for key, expected in daily_oracle(item, as_of, rows).items():
                    self.assertEqual(actual[key], expected, key)
        self.assertEqual(outcomes, {'unknown', 'covered', 'gap'})

    def test_permutation_preserves_amounts_dates_and_eligible_id_set(self):
        rows = [holding(amount_paise=60), holding(id=2, amount_paise=40, maturity_date=TODAY),
                holding(id=3, amount_paise=40, issue_date=TODAY + timedelta(days=1)),
                holding(id=4, status='SUBMITTED')]
        baseline = coverage(obligation(), TODAY, holdings=rows)
        for ordered in permutations(rows):
            actual = coverage(obligation(), TODAY, holdings=ordered)
            self.assertEqual(set(actual.pop('holding_ids')), set(baseline['holding_ids']))
            self.assertEqual(actual, {k: v for k, v in baseline.items() if k != 'holding_ids'})

    def test_positive_top_up_cannot_worsen_amount_or_first_gap(self):
        for amount, extra, days in product([1, 60, 100, 150], [1, 40, 100], [0, 1, 10]):
            end = TODAY + timedelta(days=10)
            item = obligation(term_end=end)
            rows = [holding(amount_paise=amount, maturity_date=TODAY + timedelta(days=days))]
            before = coverage(item, TODAY, holdings=rows)
            after = coverage(item, TODAY, holdings=rows + [holding(id=2, amount_paise=extra, maturity_date=end)])
            self.assertGreaterEqual(after['held_paise'], before['held_paise'])
            self.assertLessEqual(after['shortfall_paise'], before['shortfall_paise'])
            self.assertLessEqual(after['term_gap_days'], before['term_gap_days'])
            if after['first_uncovered_on'] and before['first_uncovered_on']:
                self.assertGreaterEqual(after['first_uncovered_on'], before['first_uncovered_on'])

    def test_split_and_merge_same_interval_preserve_financial_assessment(self):
        for amount in [2, 101, 2**53 + 1, 2**63 - 1]:
            item = obligation(required_paise=amount)
            one = coverage(item, TODAY, holdings=[holding(amount_paise=amount)])
            split = coverage(item, TODAY, holdings=[holding(amount_paise=1), holding(id=2, amount_paise=amount - 1)])
            self.assertEqual({k: v for k, v in one.items() if k != 'holding_ids'},
                             {k: v for k, v in split.items() if k != 'holding_ids'})
            self.assertEqual(split['held_paise'], amount)
            self.assertIs(type(split['held_paise']), int)

    def test_pending_renewal_does_not_count_and_accepted_successor_replaces_once(self):
        old, successor = holding(), holding(id=2, status='SUBMITTED')
        pending = coverage(obligation(), TODAY, holdings=[old, successor])
        accepted = coverage(obligation(), TODAY, holdings=[replace(old, superseded=True),
                            replace(successor, status='ACCEPTED')])
        self.assertEqual((pending['held_paise'], pending['holding_ids']), (100, [1]))
        self.assertEqual((accepted['held_paise'], accepted['holding_ids']), (100, [2]))
        released = coverage(obligation(), TODAY, holdings=[replace(old, superseded=True),
                            replace(successor, status='ACCEPTED', released=True)])
        self.assertEqual((released['held_paise'], released['holding_ids']), (0, []))

    def test_excluded_rows_still_cannot_hide_duplicate_or_cross_scope_ids(self):
        for row, reason in [(holding(status='DRAFT'), 'Duplicate'),
                            (holding(id=2, institution_id=2, released=True), 'outside'),
                            (holding(id=2, obligation_id=2, superseded=True), 'outside')]:
            with self.subTest(row=row), self.assertRaisesMessage(RuleInputError, reason):
                coverage(obligation(), TODAY, holdings=[holding(), row])

    def test_unknown_term_is_distinct_from_unknown_requirement_and_empty_ledger(self):
        for required, start, end in [(None, TODAY, TODAY), (100, None, None), (None, None, None)]:
            result = coverage(obligation(required_paise=required, term_start=start, term_end=end), TODAY, holdings=[])
            self.assertEqual(result['held_paise'], 0)
            self.assertEqual(result['shortfall_paise'], None if required is None else 100)
            for key in ['coverage_end', 'first_uncovered_on', 'term_gap_days']:
                self.assertIsNone(result[key])

    def test_one_day_renewal_gap_survives_later_recovery(self):
        end = TODAY + timedelta(days=5)
        result = coverage(obligation(term_end=end), TODAY, holdings=[holding(maturity_date=TODAY),
            holding(id=2, issue_date=TODAY + timedelta(days=2), maturity_date=end)])
        self.assertEqual(result['shortfall_paise'], 0)
        self.assertEqual(result['first_uncovered_on'], (TODAY + timedelta(days=1)).isoformat())
        self.assertEqual(result['term_gap_days'], 5)  # Remaining term, not one accumulated gap day.

    def test_coverage_inputs_and_detached_output_do_not_mutate_each_other(self):
        item, rows = obligation(), [holding(), holding(id=2, status='DRAFT')]
        original = deepcopy((item, rows))
        first = coverage(item, TODAY, holdings=rows)
        first['holding_ids'].clear()
        self.assertEqual((item, rows), original)
        self.assertEqual(coverage(item, TODAY, holdings=iter(rows))['holding_ids'], [1])


class CalculationBoundaryTests(SimpleTestCase):
    def test_first_and_last_calendar_dates_do_not_overflow_coverage(self):
        for when in [date.min, date.max]:
            item = obligation(term_start=when, term_end=when)
            for rows, gap in [([], 1), ([holding(issue_date=when, maturity_date=when)], 0)]:
                result = coverage(item, when, holdings=rows)
                self.assertEqual(result['term_gap_days'], gap)
                self.assertEqual(result['first_uncovered_on'], when.isoformat() if gap else None)

    def test_issue_and_maturity_are_inclusive_for_a_single_day_holding(self):
        rows = [holding(issue_date=TODAY, maturity_date=TODAY)]
        for offset, expected in [(-1, 0), (0, 100), (1, 0)]:
            self.assertEqual(coverage(obligation(), TODAY + timedelta(days=offset), holdings=rows)['held_paise'], expected)

    def test_after_term_end_current_shortfall_remains_separate_from_term_gap(self):
        result = coverage(obligation(term_end=TODAY), TODAY + timedelta(days=1), holdings=[])
        self.assertEqual(result['shortfall_paise'], 100)
        self.assertEqual(result['term_gap_days'], 0)
        self.assertIsNone(result['coverage_end'])

    def test_leap_century_and_last_representable_term_anniversaries(self):
        record = rules(effective_from=date.min)
        for start, expected in [(date(2096, 2, 29), date(2106, 2, 28)),
                                (date(2390, 2, 28), date(2400, 2, 28)),
                                (date(9989, 12, 31), date.max),
                                (date.min, date(11, 1, 1))]:
            self.assertEqual(term_end(start, record, as_of=start), expected)
        for start in [date(9990, 1, 1), date.max]:
            with self.subTest(start=start), self.assertRaises(RuleInputError):
                term_end(start, record, as_of=start)

    def test_boolean_fractional_and_invalid_id_fields_fail_closed(self):
        for field in ['id', 'institution_id']:
            for value in [False, True, 0, -1, 1.5, '1', None]:
                with self.subTest(field=field, value=value), self.assertRaises(RuleInputError):
                    coverage(obligation(**{field: value}), TODAY, holdings=[])
        for field in ['id', 'institution_id', 'obligation_id', 'amount_paise']:
            for value in [False, True, 0, -1, 1.5, '1', None]:
                with self.subTest(field=field, value=value), self.assertRaises(RuleInputError):
                    coverage(obligation(), TODAY, holdings=[holding(**{field: value})])
        for value in [False, True, -1, 1.5, '100']:
            with self.subTest(required=value), self.assertRaises(RuleInputError):
                coverage(obligation(required_paise=value), TODAY, holdings=[])

    def test_lifecycle_flags_require_actual_booleans(self):
        for field in ['superseded', 'released']:
            for value in [0, 1, None, 'false', [], {}]:
                with self.subTest(field=field, value=value), self.assertRaises(RuleInputError):
                    coverage(obligation(), TODAY, holdings=[holding(**{field: value})])

    def test_date_fields_reject_strings_and_datetimes(self):
        for field in ['issue_date', 'maturity_date']:
            for value in [None, '2026-04-20', datetime(2026, 4, 20)]:
                with self.subTest(field=field, value=value), self.assertRaises(RuleInputError):
                    coverage(obligation(), TODAY, holdings=[holding(**{field: value})])
        for field in ['term_start', 'term_end']:
            for value in ['2026-04-20', datetime(2026, 4, 20)]:
                with self.subTest(field=field, value=value), self.assertRaises(RuleInputError):
                    coverage(obligation(**{field: value}), TODAY, holdings=[])
        for value in ['2026-04-20', datetime(2026, 4, 20), None]:
            with self.subTest(as_of=value), self.assertRaises(RuleInputError):
                coverage(obligation(), value, holdings=[])

    def test_approval_order_and_repeat_calls_preserve_total_and_inputs(self):
        rows = [approval(land='LEASED'), approval('MANAGEMENT', 'PG', building='LEASED')]
        record = rules()
        original = deepcopy((record, rows))
        for ordered in permutations(rows):
            result = required_amount(ordered, record, as_of=TODAY)
            self.assertEqual(result['required_paise'], 1000000000)
            self.assertEqual(result['multiplier'], 2)
            result['breakdown'].clear()
        self.assertEqual((record, rows), original)
        self.assertEqual(len(required_amount(iter(rows), record, as_of=TODAY)['breakdown']), 2)

    def test_large_amounts_and_rounding_are_exact_and_monotonic(self):
        for kind, bps in [('premature_encashment', 1000), ('closure_six_years', 5000)]:
            prior = -1
            for amount in [1, 4, 5, 6, 9, 10, 11, 15, 2**53 + 1, 2**63 - 1]:
                result = penalty_proposal(kind, amount, rules(), as_of=TODAY)
                exact = Fraction(amount * bps, 10000)
                lower = exact.numerator // exact.denominator
                expected = lower + int(exact - lower >= Fraction(1, 2))
                self.assertEqual(result['amount_paise'], expected)
                self.assertIs(type(result['amount_paise']), int)
                self.assertGreaterEqual(result['amount_paise'], prior)
                self.assertTrue(result['human_confirmation_required'])
                prior = result['amount_paise']

    def test_large_rule_amount_preserves_paise_above_javascript_safe_range(self):
        payload = draft_payload()
        payload['amounts']['ENGINEERING_TECHNOLOGY']['UG'] = 2**53 + 1
        result = required_amount([approval(land='LEASED')], rules(payload=payload), as_of=TODAY)
        self.assertEqual(result['required_paise'], 2 * (2**53 + 1))
        self.assertIs(type(result['required_paise']), int)

    def test_findings_are_readonly_and_return_detached_evidence(self):
        record, item, rows = rules(), obligation(), [holding(amount_paise=60)]
        original = deepcopy((record, item, rows))
        args = dict(as_of=TODAY, holdings=rows, intimation_date=TODAY - timedelta(days=16))
        first = obligation_findings(item, record, **args)
        expected = deepcopy([f.as_dict() for f in first])
        for finding in first:
            finding.values.clear()
        self.assertEqual([f.as_dict() for f in obligation_findings(item, record, **args)], expected)
        self.assertEqual((record, item, rows), original)


class MalformedCodeBoundaryTests(SimpleTestCase):
    def test_non_text_approval_codes_and_tenures_are_controlled_errors(self):
        for field in ['programme', 'level', 'land_tenure', 'building_tenure']:
            for value in [[], {}, None, True, 7]:
                with self.subTest(field=field, value=value), self.assertRaises(RuleInputError):
                    required_amount([replace(approval(), **{field: value})], rules(), as_of=TODAY)

    def test_non_text_institution_types_are_controlled_errors(self):
        for value in [[], {}, None, True, 7]:
            with self.subTest(value=value), self.assertRaises(RuleInputError):
                required_amount([approval()], rules(), as_of=TODAY, institution_type=value)

    def test_non_text_holding_statuses_are_controlled_errors(self):
        for value in [[], {}, None, True, 7]:
            with self.subTest(value=value), self.assertRaises(RuleInputError):
                coverage(obligation(), TODAY, holdings=[holding(status=value)])

    def test_non_text_penalty_kinds_are_controlled_errors(self):
        for value in [[], {}, None, True, 7]:
            with self.subTest(value=value), self.assertRaises(RuleInputError):
                penalty_proposal(value, 100, rules(), as_of=TODAY)
