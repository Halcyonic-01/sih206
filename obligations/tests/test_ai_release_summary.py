from django.test import SimpleTestCase, override_settings
from django.urls import resolve

from casework.ai_summary import LABEL, validate_output


class AiReleaseSummaryContractTests(SimpleTestCase):
    def test_valid_output_is_bounded_and_preserves_field_evidence(self):
        output = validate_output({'summary': 'Clearance is still open.', 'risk_flags': [{
            'field': 'clearances[0].status', 'severity': 'warning', 'message': 'Clearance must be reviewed.'}]})
        self.assertEqual(output['risk_flags'][0]['field'], 'clearances[0].status')
        self.assertEqual(len(output['risk_flags']), 1)

    def test_invalid_or_overlong_output_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_output({'summary': 'x', 'risk_flags': [{}]})
        with self.assertRaises(ValueError):
            validate_output({'summary': 'x', 'risk_flags': [{'field': 'bad field', 'severity': 'warning', 'message': 'x'}]})
        with self.assertRaises(ValueError):
            validate_output({'summary': 'x', 'risk_flags': [{'field': f'case.{i}', 'severity': 'info', 'message': 'x'} for i in range(6)]})

    @override_settings(ROOT_URLCONF='obligations.test_urls')
    def test_summary_route_precedes_generic_case_action(self):
        match = resolve('/api/releases/17/ai-summary')
        self.assertEqual(match.func.cls.__name__, 'AiSummary')
        self.assertEqual(match.kwargs, {'pk': 17})
        self.assertEqual(LABEL, 'AI-generated: verify before use')

    @override_settings(ROOT_URLCONF='config.urls')
    def test_production_router_discovers_summary_route(self):
        match = resolve('/api/releases/17/ai-summary')
        self.assertEqual(match.func.cls.__name__, 'AiSummary')
