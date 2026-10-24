from datetime import date
import hashlib
import json
from unittest.mock import patch

from django.test import SimpleTestCase

from evaluation.s2.run import DATASET, evaluate
from obligations.catalogue import draft_payload
from obligations.calculations import ObligationInput, penalty_proposal
from obligations.checks import obligation_findings
from obligations.rules import RuleInputError, rule_snapshot
from .test_calculations import rules, TODAY

DATASET_SHA256 = '75dfa245a38d9319d2266cbe3f52bce24658025205406e86b940240eba543bd3'


class CorrectnessReviewTests(SimpleTestCase):
    def test_frozen_literal_labels_and_review_status(self):
        self.assertEqual(hashlib.sha256(DATASET.read_bytes()).hexdigest(), DATASET_SHA256)
        data = json.loads(DATASET.read_text())
        self.assertEqual(data['review_status'], 'AUTHOR_REVIEWED_NOT_SECOND_REVIEWER_ADJUDICATED')
        self.assertEqual(len(data['cases']), 76)
        self.assertTrue(all(case['rationale'].strip() for case in data['cases']))

    def test_all_labelled_scenarios_match_without_database_queries(self):
        # SimpleTestCase forbids database access; this evaluator must stay pure.
        result = evaluate()
        for row in result['cases']:
            with self.subTest(case=row['id']):
                self.assertTrue(row['passed'], row)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(result['finding_cases'], 10)

    def test_evaluator_detects_false_negatives_without_changing_labels(self):
        before = DATASET.read_bytes()
        with patch('obligations.checks.obligation_findings', return_value=[]):
            result = evaluate()
        self.assertGreater(result['failed'], 0)
        for code, expected in [('AMOUNT_SHORTFALL', 2), ('TERM_GAP', 3), ('PROOF_OVERDUE', 3)]:
            self.assertEqual(result['finding_metrics'][code]['fn'], expected)
            self.assertEqual(result['finding_metrics'][code]['recall'], 0)
        self.assertEqual(DATASET.read_bytes(), before)

    def test_required_release_requirements_cannot_be_removed_or_misspelled(self):
        for key, value in [('common_documents', ['REQUEST_LETTER']),
                           ('clearance_units', ['PGRC']),
                           ('clearance_units', ['PGRC', 'PGRC', 'GRANTS']),
                           ('mode_documents', {'FDR': 'TYPO', 'RTGS': 'PAYMENT_PROOF', 'RPGF': 'RPGF_PROOF'}),
                           ('external_noc_if_embezzlement', False),
                           ('conversion_requires_no_pending_proceedings', False)]:
            payload = draft_payload()
            payload['release'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(RuleInputError):
                rule_snapshot(rules(payload=payload), TODAY)

    def test_escalations_reject_typoes_duplicates_missing_triggers_and_wrong_direction(self):
        for change in ['recipient', 'trigger', 'duplicate', 'missing', 'direction']:
            payload = draft_payload()
            entries = payload['escalation']
            if change == 'recipient': entries[0]['recipients'] = ['TYPO']
            if change == 'trigger': entries[0]['trigger'] = 'TYPO'
            if change == 'duplicate': entries.append(dict(entries[0]))
            if change == 'missing': payload['escalation'] = [e for e in entries if e['trigger'] != 'CLEARANCE_SLA']
            if change == 'direction': entries[0]['days'] = 90
            with self.subTest(change=change), self.assertRaises(RuleInputError):
                rule_snapshot(rules(payload=payload), TODAY)
        payload = draft_payload()
        payload['escalation'][0]['days'] = -80
        rule_snapshot(rules(version=2, payload=payload), TODAY)

    def test_proof_overflow_is_a_controlled_error_in_both_callers(self):
        item = ObligationInput(1, 1, None, None, None)
        for proof_days in [15, 10 ** 30]:
            payload = draft_payload()
            payload['proof_days'] = proof_days
            record = rules(payload=payload)
            with self.subTest(proof_days=proof_days):
                with self.assertRaises(RuleInputError):
                    penalty_proposal('late_proof', 100, record, as_of=date.max,
                                     intimation_date=date.max, cycle_year=9999)
                with self.assertRaises(RuleInputError):
                    obligation_findings(item, record, as_of=date.max, holdings=[], intimation_date=date.max)

    def test_last_representable_deadline_still_works(self):
        result = penalty_proposal('late_proof', 100, rules(), as_of=date.max,
                                  intimation_date=date(9999, 12, 16), cycle_year=9999)
        self.assertEqual(result['status'], 'NOT_DUE')
        self.assertEqual(obligation_findings(ObligationInput(1, 1, None, None, None),
            rules(), as_of=date.max, holdings=[], intimation_date=date(9999, 12, 16)), [])
