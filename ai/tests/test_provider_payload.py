"""The Gemini transport: request shape, response parsing and the real worker process against a local fake server."""
import io
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch
from urllib.error import HTTPError

from django.test import SimpleTestCase, override_settings

from ai import provider_worker
from ai.services import EXTRACTION_SCHEMA, FIELD_NAMES, MAX_TOKENS, ProviderUnavailable, call_model, extract, gemini_request
from portal.tests.common import PortalTestCase

FIELDS = {'fields': {name: {'value': None, 'page': None} for name in FIELD_NAMES}}


def gemini_reply(output, finish='STOP', thought=True):
    parts = ([{'text': 'thinking about it', 'thought': True}] if thought else []) + [{'text': json.dumps(output)}]
    return {'candidates': [{'content': {'role': 'model', 'parts': parts}, 'finishReason': finish}]}


class ExtractionRequestTests(PortalTestCase):
    @override_settings(AI_ENABLED=True, AI_MODEL='gemini-3.8-flash')
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-test-key'})
    def test_extraction_sends_the_pdf_schema_and_model(self):
        item = self.draft()
        with patch('ai.services.call_model', return_value=FIELDS) as provider:
            result = extract(self.a, item.documents.get(), consent=True, synthetic=True)
        self.assertEqual(result['status'], 'success')
        payload = provider.call_args.args[0]
        self.assertEqual(payload['model'], 'gemini-3.8-flash')
        self.assertEqual(payload['schema'], EXTRACTION_SCHEMA)
        self.assertEqual(payload['max_output_tokens'], MAX_TOKENS)
        self.assertIn('pdf', payload['parts'][0])
        self.assertNotIn('tools', payload)

    @override_settings(AI_ENABLED=True)
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-test-key'})
    def test_a_provider_failure_code_is_logged_and_the_user_continues_manually(self):
        from ai.models import AiRun
        item = self.draft()
        with patch('ai.services.call_model', side_effect=ProviderUnavailable('RATE_LIMITED')):
            result = extract(self.a, item.documents.get(), consent=True, synthetic=True)
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(AiRun.objects.get().error_code, 'RATE_LIMITED')


class WorkerShapeTests(SimpleTestCase):
    payload = gemini_request('gemini-3.8-flash', 'system text', [{'pdf': 'QUJD'}, {'text': 'extract'}], EXTRACTION_SCHEMA)

    def test_body_matches_generate_content(self):
        body = provider_worker.build(self.payload)
        self.assertEqual(body['system_instruction'], {'parts': [{'text': 'system text'}]})
        self.assertEqual(body['contents'][0]['parts'][0], {'inline_data': {'mime_type': 'application/pdf', 'data': 'QUJD'}})
        config = body['generationConfig']
        self.assertEqual(config['responseFormat']['text'], {'mimeType': 'APPLICATION_JSON', 'schema': EXTRACTION_SCHEMA})
        self.assertEqual(config['thinkingConfig'], {'thinkingLevel': 'low'})
        self.assertEqual(config['maxOutputTokens'], MAX_TOKENS)
        legacy = provider_worker.build(self.payload, 'json_schema')['generationConfig']
        self.assertEqual((legacy['responseMimeType'], legacy['responseJsonSchema']), ('application/json', EXTRACTION_SCHEMA))

    def test_parse_skips_thoughts_and_rejects_cut_off_or_blocked_answers(self):
        self.assertEqual(provider_worker.parse(gemini_reply(FIELDS)), FIELDS)
        for reply, code in [(gemini_reply(FIELDS, finish='MAX_TOKENS'), 'MAX_TOKENS'),
                            (gemini_reply(FIELDS, finish='SAFETY'), 'FINISH_SAFETY'),
                            ({'promptFeedback': {'blockReason': 'SAFETY'}}, 'BLOCKED'), ({}, 'NO_OUTPUT'),
                            ({'candidates': [{'content': {'parts': [{'text': 'not json'}]}, 'finishReason': 'STOP'}]},
                             'INVALID_JSON')]:
            with self.subTest(code=code), self.assertRaises(provider_worker.ProviderError) as failure:
                provider_worker.parse(reply)
            self.assertEqual(failure.exception.code, code)

    @patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-test-key'})
    def test_unknown_field_falls_back_once_and_errors_map_to_codes(self):
        unknown = HTTPError('u', 400, 'Bad', {}, io.BytesIO(b'Invalid JSON payload received. Unknown name "responseFormat"'))
        ok = io.BytesIO(json.dumps(gemini_reply(FIELDS)).encode())
        with patch.object(provider_worker, 'urlopen', side_effect=[unknown, ok]) as call:
            self.assertEqual(provider_worker.request(self.payload), FIELDS)
        second = json.loads(call.call_args_list[1].args[0].data)
        self.assertIn('responseJsonSchema', second['generationConfig'])
        self.assertEqual(call.call_args_list[0].args[0].get_header('X-goog-api-key'), 'synthetic-test-key')
        for status, text, code in [(403, b'denied', 'KEY_REJECTED'), (400, b'API key not valid', 'KEY_REJECTED'),
                                   (404, b'not found', 'MODEL_NOT_FOUND'), (429, b'quota', 'RATE_LIMITED')]:
            error = HTTPError('u', status, 'x', {}, io.BytesIO(text))
            with self.subTest(code=code), patch.object(provider_worker, 'urlopen', side_effect=error), \
                    self.assertRaises(provider_worker.ProviderError) as failure:
                provider_worker.request(self.payload)
            self.assertEqual(failure.exception.code, code)

    def test_missing_key_and_unsafe_model_name(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(provider_worker.ProviderError) as failure:
            provider_worker.request(self.payload)
        self.assertEqual(failure.exception.code, 'NOT_CONFIGURED')
        with self.assertRaises(provider_worker.ProviderError) as failure:
            provider_worker.request(self.payload | {'model': '../../evil'})
        self.assertEqual(failure.exception.code, 'INVALID_MODEL')


class FakeGemini(BaseHTTPRequestHandler):
    seen = []
    reply = {}
    status = 200

    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        FakeGemini.seen.append((self.path, self.headers.get('x-goog-api-key'), json.loads(body)))
        payload = json.dumps(FakeGemini.reply).encode()
        self.send_response(FakeGemini.status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class WorkerProcessTests(SimpleTestCase):
    """The real child process, stdin/stdout contract and HTTP call, against a fake Gemini on 127.0.0.1."""

    def setUp(self):
        self.server = HTTPServer(('127.0.0.1', 0), FakeGemini)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        FakeGemini.seen, FakeGemini.status = [], 200
        endpoint = f'http://127.0.0.1:{self.server.server_port}'
        patcher = patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-test-key', 'GEMINI_TEST_ENDPOINT': endpoint})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_call_model_end_to_end(self):
        FakeGemini.reply = gemini_reply({'status': 'ok'})
        output = call_model(gemini_request('gemini-3.8-flash', 'system', [{'text': 'hello'}], {'type': 'object'}))
        self.assertEqual(output, {'status': 'ok'})
        path, key, body = FakeGemini.seen[0]
        self.assertEqual(path, '/v1beta/models/gemini-3.8-flash:generateContent')
        self.assertEqual(key, 'synthetic-test-key')
        self.assertEqual(body['contents'][0]['parts'], [{'text': 'hello'}])

    def test_failures_surface_as_a_code_without_the_key(self):
        FakeGemini.status, FakeGemini.reply = 429, {'error': {'message': 'quota'}}
        with self.assertRaises(ProviderUnavailable) as failure:
            call_model(gemini_request('gemini-3.8-flash', 'system', [{'text': 'hello'}], {'type': 'object'}))
        self.assertEqual(failure.exception.code, 'RATE_LIMITED')
        self.assertNotIn('synthetic-test-key', str(failure.exception))
