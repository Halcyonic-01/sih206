from copy import deepcopy
from pathlib import Path
from unittest import TestCase
from ai.evaluation import load_manifest, score_case, summarize
from ai.services import validate_output


class EvaluationTests(TestCase):
    def setUp(self):
        self.data = load_manifest(Path(__file__).resolve().parents[2] / 'fixtures/ai-evaluation/manifest.json')

    def test_manifest_has_twelve_labelled_cases_and_disjoint_heldout_subset(self):
        self.assertEqual(len(self.data['cases']), 12)
        self.assertEqual(sum(c['subset'] == 'heldout' for c in self.data['cases']), 4)
        self.assertFalse(self.data['label_review'] == 'INDEPENDENTLY_REVIEWED')

    def test_perfect_scoring_and_undefined_precision(self):
        case = self.data['cases'][0]
        row = score_case(case, {'status': 'success', 'fields': case['expected'], 'findings': []})
        result = summarize([row])
        self.assertEqual(result['field_exact_accuracy'], 1)
        self.assertEqual(result['field_recall'], 1)
        self.assertEqual(result['page_accuracy_among_predictions'], 1)
        self.assertIsNone(result['mismatch_precision'])

    def test_wrong_value_wrong_page_missing_value_and_false_finding_count(self):
        case = self.data['cases'][0]
        fields = deepcopy(case['expected'])
        fields['bank']['value'] = 'Wrong bank'
        fields['amount'] = {'value': None, 'page': None}
        fields['ifsc']['page'] = 2
        row = score_case(case, {'status': 'success', 'fields': fields,
            'findings': [{'code': 'AI_MISMATCH', 'field': 'bank'}]})
        self.assertEqual(row['counts']['wrong_values'], 1)
        self.assertEqual(row['counts']['missing_values'], 1)
        self.assertEqual(row['counts']['correct_pages'], 3)
        self.assertEqual(row['counts']['fp'], 1)

    def test_failure_is_in_denominator_and_mismatch_false_negatives_count(self):
        case = next(c for c in self.data['cases'] if c['id'] == 'M02')
        result = summarize([score_case(case, {'status': 'unavailable'})])
        self.assertEqual(result['field_recall'], 0)
        self.assertEqual(result['counts']['fn'], 2)
        self.assertEqual(result['mismatch_recall'], 0)
        self.assertEqual(result['counts']['exact'], 0)

    def test_values_without_page_evidence_are_rejected(self):
        output = {'fields': deepcopy(self.data['cases'][0]['expected'])}
        output['fields']['bank']['page'] = None
        with self.assertRaises(ValueError):
            validate_output(output, 1)

