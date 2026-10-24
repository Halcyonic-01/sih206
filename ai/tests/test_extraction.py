import os
import subprocess
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import override_settings

from ai.models import AiRun
from ai.services import extract, FIELD_NAMES
from portal.tests.common import PortalTestCase


class ExtractionTests(PortalTestCase):
    def output(self, **values):
        return {'fields': {name: {'value': values.get(name), 'page': 1 if name in values else None} for name in FIELD_NAMES}}

    @override_settings(AI_ENABLED=False)
    def test_disabled_and_cross_institution_access_never_call_provider(self):
        item = self.draft()
        with patch('ai.services.call_model') as provider:
            result = extract(self.a, item.documents.get())
            self.assertEqual(result['status'], 'disabled')
            provider.assert_not_called()
        self.assertEqual(AiRun.objects.get().status, 'DISABLED')
        with self.assertRaises(PermissionDenied):
            extract(self.b, item.documents.get(), consent=True, synthetic=True)

    @override_settings(AI_ENABLED=True)
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-test-key'})
    def test_suggestions_and_mismatches_cannot_mutate_records(self):
        item = self.draft()
        before = (item.amount_paise, item.status, item.verification_level, item.version, item.audit_events.count())
        with patch('ai.services.call_model', return_value=self.output(amount='400000.00')) as provider:
            result = extract(self.a, item.documents.get(), consent=True, synthetic=True)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['findings'][0]['code'], 'AI_MISMATCH')
        self.assertNotIn('tools', provider.call_args.args[0])
        item.refresh_from_db()
        self.assertEqual(before, (item.amount_paise, item.status, item.verification_level, item.version, item.audit_events.count()))

    @override_settings(AI_ENABLED=True)
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-test-key'})
    def test_consent_schema_and_timeout_fail_safely(self):
        item = self.draft()
        doc = item.documents.get()
        with patch('ai.services.call_model') as provider:
            self.assertEqual(extract(self.a, doc)['status'], 'unavailable')
            provider.assert_not_called()
        for failure in [subprocess.TimeoutExpired('synthetic', 30), ValueError('private provider details')]:
            with patch('ai.services.call_model', side_effect=failure):
                result = extract(self.a, doc, consent=True, synthetic=True)
                self.assertEqual(result['status'], 'unavailable')
                self.assertNotIn('private provider', str(result))
        invalid = self.output(amount='123.00')
        invalid['fields']['amount']['page'] = 999
        with patch('ai.services.call_model', return_value=invalid):
            self.assertEqual(extract(self.a, doc, consent=True, synthetic=True)['status'], 'unavailable')

    @override_settings(AI_ENABLED=False)
    def test_api_uses_session_scope_and_returns_manual_fallback(self):
        item = self.draft()
        path = f'/api/documents/{item.documents.get().pk}/ai-extract/'
        self.assertEqual(self.client.post(path, {}, content_type='application/json').json()['status'], 'disabled')
        self.client.force_login(self.b)
        self.assertEqual(self.client.post(path, {}, content_type='application/json').status_code, 404)
