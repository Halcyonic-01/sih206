"""The request and response shapes of the live provider transport, without a network call."""
import io
import json
import os
from unittest.mock import patch

from django.test import override_settings

from ai import provider_worker
from ai.services import FIELD_NAMES, MAX_TOKENS, extract
from portal.tests.common import PortalTestCase


class ProviderPayloadTests(PortalTestCase):
    @override_settings(AI_ENABLED=True)
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'synthetic-test-key'})
    def test_extraction_leaves_room_for_thinking_and_uses_low_effort(self):
        item = self.draft()
        empty = {'fields': {name: {'value': None, 'page': None} for name in FIELD_NAMES}}
        with patch('ai.services.call_model', return_value=empty) as provider:
            extract(self.a, item.documents.get(), consent=True, synthetic=True)
        payload = provider.call_args.args[0]
        self.assertGreaterEqual(payload['max_tokens'], 16000)  # thinking and the JSON share this cap
        self.assertEqual(payload['output_config']['effort'], 'low')
        self.assertEqual(payload['output_config']['format']['type'], 'json_schema')
        self.assertEqual(payload['model'], 'claude-opus-5-5')
        self.assertEqual(MAX_TOKENS, payload['max_tokens'])

    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'synthetic-test-key'})
    def test_worker_reads_the_text_block_after_a_thinking_block(self):
        body = {'stop_reason': 'end_turn', 'content': [
            {'type': 'thinking', 'thinking': '...', 'signature': 'x'},
            {'type': 'text', 'text': json.dumps({'fields': {}})}]}
        with patch.object(provider_worker, 'urlopen', return_value=io.BytesIO(json.dumps(body).encode())) as call:
            self.assertEqual(provider_worker.request({'model': 'claude-opus-5-5'}), {'fields': {}})
        self.assertEqual(call.call_args.args[0].get_header('X-api-key'), 'synthetic-test-key')
        truncated = body | {'stop_reason': 'max_tokens'}
        with patch.object(provider_worker, 'urlopen', return_value=io.BytesIO(json.dumps(truncated).encode())):
            with self.assertRaises(ValueError):
                provider_worker.request({'model': 'claude-opus-5-5'})
