"""Pure checklist correctness; no source adapter or authorization claim."""
from copy import deepcopy
import json
from pathlib import Path
from unittest import TestCase

from obligations.readiness import calculate, aggregate, ReadinessInputError


class ReadinessTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((Path(__file__).resolve().parents[2]/'docs/readiness/scenarios.json').read_text())
        cls.base = cls.data['cases'][0]['snapshot']

    def test_all_labelled_synthetic_scenarios(self):
        for case in self.data['cases']:
            with self.subTest(case=case['id']):
                result = calculate(case['snapshot'], institution_id=1)
                items = {item['id']: item for item in result['items']}
                deadline = items['affidavit_3']['deadline']
                for key, expected in case['expected'].items():
                    if key in items:
                        self.assertEqual(items[key]['state'], expected)
                    elif key in {'due_on', 'days_remaining', 'deadline_state'}:
                        self.assertEqual(deadline['state' if key == 'deadline_state' else key], expected)
                    else:
                        self.assertEqual(result[key], expected)

    def test_snapshots_are_not_mutated(self):
        original = deepcopy(self.base)
        calculate(self.base, institution_id=1)
        self.assertEqual(original, self.base)

    def test_permission_intents_are_explicit_and_no_urls_are_guessed(self):
        result = calculate(self.base, institution_id=1)
        self.assertEqual([item['next_action'] for item in result['items'] if item['next_action']],
                         ['UPLOAD_AFFIDAVIT_3', 'RECORD_PROOF_RECEIPTS'])
        snapshot = deepcopy(self.base); snapshot['allowed_actions'] = []
        self.assertTrue(all(item['next_action'] is None for item in calculate(snapshot, institution_id=1)['items']))

    def test_foreign_scope_duplicate_obligations_and_mixed_dates_are_rejected(self):
        with self.assertRaises(ReadinessInputError):
            calculate(self.base, institution_id=2)
        with self.assertRaises(ReadinessInputError):
            aggregate([self.base, self.base], institution_id=1)
        other = deepcopy(self.base); other.update(obligation_id=102, as_of='2026-10-28')
        with self.assertRaises(ReadinessInputError):
            aggregate([self.base, other], institution_id=1)

    def test_aggregate_uses_milestone_counts_not_percentage_mean(self):
        other = deepcopy(self.base); other['obligation_id'] = 102
        other['applicability'] = dict.fromkeys(other['applicability'], False)
        other['applicability']['accepted_deposit'] = True
        # 4/6 plus 1/1 = 5/7 (71%), not mean(67%, 100%).
        result = aggregate([self.base, other], institution_id=1)
        self.assertEqual((result['completed'], result['applicable'], result['percent']), (5, 7, 71))
        empty = aggregate([], institution_id=1)
        self.assertEqual((empty['percent'], empty['status']), (None, 'NO_OBLIGATIONS'))

    def test_uploaded_proofs_do_not_establish_officer_receipt_review(self):
        snapshot = deepcopy(self.base); snapshot['facts']['affidavit_3_uploaded'] = True
        items = {row['id']: row for row in calculate(snapshot, institution_id=1)['items']}
        self.assertEqual(items['affidavit_3']['state'], 'COMPLETE')
        self.assertEqual(items['proof_receipt']['state'], 'INCOMPLETE')

    def test_invalid_values_and_future_receipt_dates_are_rejected(self):
        for section, key, value in [('facts', 'held_paise', True), ('facts', 'required_paise', -1),
                ('facts', 'held_paise', 1.2), ('facts', 'payment_proof_uploaded', 'true'),
                ('facts', 'payment_proof_on', '2026-02-30'), ('facts', 'payment_proof_on', '2027-01-01'),
                ('deadline', 'intimation_date', '2027-01-01'), ('deadline', 'proof_days', False),
                ('deadline', 'proof_days', 0), ('deadline', 'proof_days', 367),
                ('deadline', 'intimation_date', '20261020'), ('facts', 'bank_status', 'BANK_VERIFIED'),
                ('facts', 'bank_status', []), ('facts', 'bank_status', {})]:
            with self.subTest(key=key, value=value):
                snapshot = deepcopy(self.base); snapshot[section][key] = value
                with self.assertRaises(ReadinessInputError):
                    calculate(snapshot, institution_id=1)

    def test_dates_require_a_real_review_even_when_not_in_future(self):
        snapshot = deepcopy(self.base); snapshot['facts']['payment_proof_on'] = '2026-10-26'
        with self.assertRaises(ReadinessInputError):
            calculate(snapshot, institution_id=1)

    def test_unknown_applicability_does_not_disappear_from_denominator(self):
        snapshot = deepcopy(self.base); snapshot['applicability'] = dict.fromkeys(snapshot['applicability'], None)
        result = calculate(snapshot, institution_id=1)
        self.assertEqual((result['completed'], result['applicable'], result['unknown'], result['percent']), (0, 6, 6, 0))

    def test_large_paise_values_are_compared_as_integers(self):
        snapshot = deepcopy(self.base)
        snapshot['facts'].update(required_paise=99999999999999999, held_paise=99999999999999998)
        result = calculate(snapshot, institution_id=1)
        self.assertEqual(next(row for row in result['items'] if row['id'] == 'amount_coverage')['state'], 'INCOMPLETE')

    def test_inapplicable_affidavit_does_not_need_an_affidavit_receipt_date(self):
        snapshot = deepcopy(self.base)
        snapshot['applicability']['affidavit_3'] = False
        snapshot['facts'].update(proof_reviewed=True, payment_proof_on='2026-10-26')
        rows = {row['id']: row for row in calculate(snapshot, institution_id=1)['items']}
        self.assertEqual(rows['affidavit_3']['state'], 'NOT_APPLICABLE')
        self.assertEqual(rows['proof_receipt']['state'], 'COMPLETE')

    def test_inconsistent_receipt_applicability_is_rejected(self):
        snapshot = deepcopy(self.base)
        for key in ('accepted_deposit', 'payment_proof', 'affidavit_3'):
            snapshot['applicability'][key] = False
        with self.assertRaises(ReadinessInputError):
            calculate(snapshot, institution_id=1)

    def test_incomplete_and_unexpected_contracts_are_rejected(self):
        for snapshot in [None, {}, self.base | {'unrecognized': True}, self.base | {'schema': True}]:
            with self.assertRaises(ReadinessInputError):
                calculate(snapshot, institution_id=1)
        snapshot = deepcopy(self.base); del snapshot['facts']['bank_status']
        with self.assertRaises(ReadinessInputError):
            calculate(snapshot, institution_id=1)

    def test_deadline_overflow_and_duplicate_actions_are_rejected(self):
        snapshot = deepcopy(self.base)
        snapshot.update(as_of='9999-12-31', deadline={'intimation_date': '9999-12-31', 'proof_days': 15})
        with self.assertRaises(ReadinessInputError):
            calculate(snapshot, institution_id=1)
        snapshot = deepcopy(self.base); snapshot['allowed_actions'] *= 2
        with self.assertRaises(ReadinessInputError):
            calculate(snapshot, institution_id=1)
