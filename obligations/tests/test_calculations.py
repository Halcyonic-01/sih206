from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta
from itertools import product
import json
from types import SimpleNamespace

from django.test import SimpleTestCase

from obligations.catalogue import SOURCE, draft_payload
from obligations.calculations import (ApprovalInput, HoldingInput, ObligationInput,
                                     coverage, penalty_proposal, required_amount, term_end)
from obligations.checks import obligation_findings
from obligations.rules import RuleInputError, rule_snapshot

TODAY = date(2026, 4, 20)


def rules(**overrides):
    return SimpleNamespace(**(dict(code='synthetic-rules', version=1,
        effective_from=date(2024, 1, 1), effective_to=None, payload=draft_payload(),
        source_document=SOURCE, source_clause='Synthetic demo of APH rules') | overrides))


def approval(programme='ENGINEERING_TECHNOLOGY', level='UG', land='OWNED', building='OWNED'):
    return ApprovalInput(programme, level, land, building)


def obligation(**overrides):
    return ObligationInput(**(dict(id=1, institution_id=1, required_paise=100,
        term_start=TODAY, term_end=date(2027, 4, 20)) | overrides))


def holding(**overrides):
    return HoldingInput(**(dict(id=1, institution_id=1, obligation_id=1, amount_paise=100,
        issue_date=TODAY, maturity_date=date(2027, 4, 20)) | overrides))


class RuleSnapshotTests(SimpleTestCase):
    def test_snapshot_is_detached_and_frozen(self):
        record = rules()
        snap = rule_snapshot(record, TODAY)
        original = snap.sha256
        record.payload['term_years'] = 20
        snap.payload['term_years'] = 30
        self.assertEqual(snap.payload['term_years'], 10)
        self.assertEqual(snap.sha256, original)
        with self.assertRaises(FrozenInstanceError):
            snap.version = 2

    def test_effective_dates_are_explicit_and_inclusive(self):
        record = rules(effective_from=TODAY, effective_to=TODAY)
        rule_snapshot(record, TODAY)
        for when in [TODAY - timedelta(days=1), TODAY + timedelta(days=1)]:
            with self.subTest(when=when), self.assertRaises(RuleInputError):
                rule_snapshot(record, when)

    def test_invalid_schema_and_money_types_are_rejected(self):
        payloads = []
        for value in [-1, 0, True, 1.5, '350000000']:
            p = draft_payload()
            p['amounts']['ENGINEERING_TECHNOLOGY']['UG'] = value
            payloads.append(p)
        for value in [False, 0, 2]:
            p = draft_payload()
            p['schema_version'] = value
            payloads.append(p)
        p = draft_payload(); del p['clauses']['amount']; payloads.append(p)
        p = draft_payload(); p['unexpected'] = 1; payloads.append(p)
        p = draft_payload(); p['label'] = 'APPROVED'; payloads.append(p)
        for p in payloads:
            with self.subTest(payload=p), self.assertRaises(RuleInputError):
                rule_snapshot(rules(payload=p), TODAY)

    def test_dates_and_version_reject_wrong_types(self):
        for invalid in [dict(version=True), dict(version=0), dict(effective_from='2024-01-01'),
                        dict(effective_to=date(2023, 1, 1)), dict(source_document='')]:
            with self.subTest(invalid=invalid), self.assertRaises(RuleInputError):
                rule_snapshot(rules(**invalid), TODAY)
        with self.assertRaises(RuleInputError):
            rule_snapshot(rules(), datetime(2026, 4, 20))

    def test_new_version_changes_do_not_rewrite_old_results(self):
        first = rule_snapshot(rules(), TODAY)
        before = required_amount([approval()], first, as_of=TODAY)
        p = draft_payload(); p['amounts']['ENGINEERING_TECHNOLOGY']['UG'] = 360000000
        second = rule_snapshot(rules(version=2, payload=p), TODAY)
        self.assertNotEqual(required_amount([approval()], second, as_of=TODAY)['required_paise'], before['required_paise'])
        self.assertEqual(required_amount([approval()], first, as_of=TODAY), before)

    def test_future_version_can_change_reminder_configuration(self):
        p = draft_payload(); p['reminders']['maturity_days'] = [60, 30, 5]
        self.assertEqual(rule_snapshot(rules(version=2, payload=p), TODAY).payload['reminders']['maturity_days'], [60, 30, 5])
        p['reminders']['maturity_days'] = [30, 30]
        with self.assertRaises(RuleInputError):
            rule_snapshot(rules(payload=p), TODAY)


class AmountTests(SimpleTestCase):
    def test_every_table_1_4_cell_against_explicit_ground_truth(self):
        expected = {'ENGINEERING_TECHNOLOGY': (15, 35, 15), 'PLANNING': (15, 15, 15),
                    'APPLIED_ARTS_CRAFTS': (15, 15, 15), 'DESIGN': (15, 15, 15),
                    'HMCT': (15, 15, 15), 'COMPUTER_APPLICATIONS': (None, 5, 15),
                    'MANAGEMENT': (None, 5, 15)}
        for programme, amounts in expected.items():
            for level, amount in zip(['DIPLOMA', 'UG', 'PG'], amounts):
                with self.subTest(programme=programme, level=level):
                    if amount is None:
                        with self.assertRaises(RuleInputError):
                            required_amount([approval(programme, level)], rules(), as_of=TODAY)
                    else:
                        self.assertEqual(required_amount([approval(programme, level)], rules(),
                            as_of=TODAY)['required_paise'], amount * 10000000)

    def test_planning_example_leased_engineering_and_management_is_100_lakh(self):
        result = required_amount([approval(land='LEASED'), approval('MANAGEMENT', 'PG', building='LEASED')],
                                 rules(), as_of=TODAY)
        self.assertEqual(result['required_paise'], 1000000000)
        self.assertEqual(result['multiplier'], 2)
        self.assertFalse(result['exemption_assessed'])

    def test_leased_land_or_building_doubles_once(self):
        for land, building in product(['OWNED', 'LEASED'], repeat=2):
            with self.subTest(land=land, building=building):
                expected = 350000000 * (2 if 'LEASED' in [land, building] else 1)
                self.assertEqual(required_amount([approval(land=land, building=building)], rules(),
                    as_of=TODAY)['required_paise'], expected)

    def test_institution_type_never_automatically_grants_exemption(self):
        result = required_amount([approval()], rules(), as_of=TODAY, institution_type='GOVERNMENT')
        self.assertEqual(result['required_paise'], 350000000)
        self.assertFalse(result['exemption_assessed'])

    def test_missing_duplicate_and_unknown_inputs_fail_closed(self):
        for values in [[], [approval(), approval()], [approval('UNKNOWN')],
                       [approval(land='UNKNOWN')], [approval(level='UNKNOWN')]]:
            with self.subTest(values=values), self.assertRaises(RuleInputError):
                required_amount(values, rules(), as_of=TODAY)

    def test_term_anniversary_and_leap_day(self):
        self.assertEqual(term_end(date(2026, 10, 24), rules(), as_of=TODAY), date(2036, 10, 24))
        self.assertEqual(term_end(date(2024, 2, 29), rules(), as_of=TODAY), date(2034, 2, 28))


class CoverageTests(SimpleTestCase):
    def test_top_up_clears_shortfall(self):
        first = holding(amount_paise=60)
        before = coverage(obligation(), TODAY, holdings=[first])
        self.assertEqual(before['shortfall_paise'], 40)
        after = coverage(obligation(), TODAY, holdings=[first, holding(id=2, amount_paise=40)])
        self.assertEqual((after['shortfall_paise'], after['term_gap_days']), (0, 0))

    def test_unknown_requirement_and_term_remain_unknown(self):
        result = coverage(obligation(required_paise=None, term_start=None, term_end=None), TODAY, holdings=[])
        self.assertIsNone(result['shortfall_paise'])
        self.assertIsNone(result['term_gap_days'])

    def test_missing_adapter_is_not_silently_an_empty_ledger(self):
        with self.assertRaises(RuleInputError):
            coverage(obligation(), TODAY, holdings=None)

    def test_scope_and_duplicate_guard(self):
        for holdings in [[holding(institution_id=2)], [holding(obligation_id=2)],
                         [holding(), holding()], [holding(institution_id=True)]]:
            with self.subTest(holdings=holdings), self.assertRaises(RuleInputError):
                coverage(obligation(), TODAY, holdings=holdings)

    def test_draft_superseded_and_released_do_not_count(self):
        for changes in [dict(status='DRAFT'), dict(status='SUBMITTED'), dict(status='CHANGES_REQUESTED'),
                        dict(superseded=True), dict(released=True)]:
            with self.subTest(changes=changes):
                self.assertEqual(coverage(obligation(), TODAY, holdings=[holding(**changes)])['held_paise'], 0)

    def test_maturity_day_is_inclusive_and_next_day_is_uncovered(self):
        item = holding(maturity_date=TODAY)
        self.assertEqual(coverage(obligation(), TODAY, holdings=[item])['held_paise'], 100)
        self.assertEqual(coverage(obligation(), TODAY + timedelta(days=1), holdings=[item])['held_paise'], 0)
        self.assertEqual(coverage(obligation(), TODAY, holdings=[item])['coverage_end'], TODAY.isoformat())

    def test_redundant_short_holding_does_not_shorten_sufficient_long_coverage(self):
        result = coverage(obligation(), TODAY, holdings=[holding(), holding(id=2, maturity_date=TODAY)])
        self.assertEqual((result['coverage_end'], result['term_gap_days']), ('2027-04-20', 0))

    def test_future_top_up_does_not_hide_an_earlier_gap(self):
        result = coverage(obligation(), TODAY, holdings=[holding(amount_paise=60),
            holding(id=2, amount_paise=40, issue_date=TODAY + timedelta(days=2))])
        self.assertEqual(result['shortfall_paise'], 40)
        self.assertIsNone(result['coverage_end'])
        self.assertGreater(result['term_gap_days'], 0)

    def test_future_term_and_contiguous_holdings(self):
        start = TODAY + timedelta(days=3)
        first_end = date(2026, 10, 1)
        result = coverage(obligation(term_start=start), TODAY, holdings=[
            holding(issue_date=start, maturity_date=first_end),
            holding(id=2, issue_date=first_end + timedelta(days=1))])
        self.assertEqual(result['term_gap_days'], 0)

    def test_negative_fractional_boolean_amounts_and_bad_dates_fail(self):
        for changes in [dict(amount_paise=-1), dict(amount_paise=1.5), dict(amount_paise=True),
                        dict(issue_date=date(2030, 1, 1)), dict(released='false'), dict(status='UNKNOWN')]:
            with self.subTest(changes=changes), self.assertRaises(RuleInputError):
                coverage(obligation(), TODAY, holdings=[holding(**changes)])
        for changes in [dict(required_paise=True), dict(term_start=None), dict(term_end=date(2020, 1, 1))]:
            with self.subTest(changes=changes), self.assertRaises(RuleInputError):
                coverage(obligation(**changes), TODAY, holdings=[])

    def test_shortfall_invariant_over_a_bounded_generated_grid(self):
        # Exhaustive small grid; no new property-testing dependency is needed.
        for required, first, second in product([1, 10, 100], [1, 5, 50, 100], [1, 20, 100]):
            result = coverage(obligation(required_paise=required), TODAY,
                              holdings=[holding(amount_paise=first), holding(id=2, amount_paise=second)])
            self.assertEqual(result['shortfall_paise'], max(required - first - second, 0))


class FindingAndPenaltyTests(SimpleTestCase):
    def test_all_three_findings_carry_values_and_rule_provenance(self):
        results = obligation_findings(obligation(), rules(), as_of=TODAY, holdings=[],
                                     intimation_date=TODAY - timedelta(days=16))
        self.assertEqual({f.code for f in results}, {'AMOUNT_SHORTFALL', 'TERM_GAP', 'PROOF_OVERDUE'})
        for f in results:
            self.assertEqual(f.severity, 'warning')
            self.assertTrue(f.values['source_clause'])
            self.assertEqual(len(f.values['rule_sha256']), 64)
            json.dumps(f.as_dict())

    def test_proof_deadline_minus_one_zero_plus_one(self):
        intimation = TODAY - timedelta(days=15)
        for offset, count in [(-1, 0), (0, 0), (1, 1)]:
            result = obligation_findings(obligation(required_paise=None, term_start=None, term_end=None),
                rules(), as_of=TODAY + timedelta(days=offset), holdings=[], intimation_date=intimation)
            self.assertEqual(len(result), count)

    def test_both_proof_documents_are_required_and_complete_proof_clears_overdue(self):
        item = obligation(required_paise=None, term_start=None, term_end=None)
        kwargs = dict(as_of=TODAY, holdings=[], intimation_date=TODAY - timedelta(days=20), payment_proof_on=TODAY)
        self.assertEqual(obligation_findings(item, rules(), **kwargs)[0].values['missing_documents'], ['AFFIDAVIT_3'])
        self.assertEqual(obligation_findings(item, rules(), **kwargs, affidavit_on=TODAY), [])

    def test_no_invented_deadline_and_no_future_receipts(self):
        item = obligation(required_paise=None, term_start=None, term_end=None)
        self.assertEqual(obligation_findings(item, rules(), as_of=TODAY, holdings=[]), [])
        with self.assertRaises(RuleInputError):
            obligation_findings(item, rules(), as_of=TODAY, holdings=[], payment_proof_on=TODAY + timedelta(days=1))

    def test_penalty_rates_and_integer_half_up_rounding(self):
        for kind, rate in [('premature_encashment', 1000), ('closure_lapsed', 1000), ('closure_six_years', 5000)]:
            with self.subTest(kind=kind):
                result = penalty_proposal(kind, 10005, rules(), as_of=TODAY)
                self.assertEqual(result['rate_bps'], rate)
                self.assertEqual(result['status'], 'PROPOSED')
                self.assertTrue(result['human_confirmation_required'])
        self.assertEqual(penalty_proposal('premature_encashment', 5, rules(), as_of=TODAY)['amount_paise'], 1)

    def test_late_proof_cutoff_boundaries(self):
        for when, expected in [(date(2026, 5, 30), 1000), (date(2026, 5, 31), 1000),
                               (date(2026, 6, 1), 2000), (date(2026, 7, 30), 2000),
                               (date(2026, 7, 31), 2000), (date(2026, 8, 1), None)]:
            with self.subTest(when=when):
                result = penalty_proposal('late_proof', 10000, rules(), as_of=when,
                    intimation_date=date(2026, 4, 1), cycle_year=2026)
                self.assertEqual(result['rate_bps'], expected)
                if expected is None:
                    self.assertEqual(result['status'], 'REQUIRES_AUTHORITY_REVIEW')
                    self.assertIsNone(result['amount_paise'])

    def test_late_proof_grace_period_and_recorded_completion(self):
        for delta, expected in [(14, 0), (15, 0), (16, 1000)]:
            result = penalty_proposal('late_proof', 10000, rules(), as_of=TODAY,
                intimation_date=TODAY - timedelta(days=delta), cycle_year=2026)
            self.assertEqual(result['rate_bps'], expected)
        result = penalty_proposal('late_proof', 10000, rules(), as_of=date(2026, 8, 1),
            intimation_date=date(2026, 4, 1), proof_completed_on=date(2026, 5, 31), cycle_year=2026)
        self.assertEqual(result['rate_bps'], 1000)

    def test_penalty_invalid_money_cycle_and_kind_fail(self):
        for amount in [-1, 0, True, 1.5]:
            with self.subTest(amount=amount), self.assertRaises(RuleInputError):
                penalty_proposal('premature_encashment', amount, rules(), as_of=TODAY)
        for kwargs in [dict(cycle_year=None), dict(cycle_year=2025), dict(proof_completed_on=date(2027, 1, 1))]:
            with self.subTest(kwargs=kwargs), self.assertRaises(RuleInputError):
                penalty_proposal('late_proof', 10000, rules(), as_of=TODAY,
                    intimation_date=date(2026, 1, 1), **kwargs)
        with self.assertRaises(RuleInputError):
            penalty_proposal('invented', 10000, rules(), as_of=TODAY)
        with self.assertRaises(RuleInputError):
            penalty_proposal('late_proof', 10000, rules(), as_of=TODAY,
                intimation_date=date(2025, 12, 1), cycle_year=2026)
