"""Tool-free Gemini generateContent transport, run in a child process; secrets never appear in stdout.

Input (stdin): {"model", "system", "parts": [{"pdf": base64} | {"text": str}], "schema", "max_output_tokens"}.
Output (stdout): {"output": <parsed JSON>} or {"error": <short code>} with exit status 1.
"""
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
# Tests point the worker at a fake server on this machine; nothing else may redirect the key.
_TEST_ENDPOINT = os.environ.get('GEMINI_TEST_ENDPOINT', '')
if _TEST_ENDPOINT.startswith('http://127.0.0.1:'):
    ENDPOINT = _TEST_ENDPOINT.rstrip('/') + '/v1beta/models/{model}:generateContent'
MAX_RESPONSE_BYTES = 1024 * 1024


class ProviderError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def build(payload, variant='current'):
    """The request body. 'current' is the documented REST shape; 'json_schema' is the earlier generationConfig form."""
    parts = [{'inline_data': {'mime_type': 'application/pdf', 'data': part['pdf']}} if 'pdf' in part
             else {'text': part['text']} for part in payload['parts']]
    config = {'maxOutputTokens': payload['max_output_tokens'], 'thinkingConfig': {'thinkingLevel': 'low'}}
    if variant == 'current':
        config['responseFormat'] = {'text': {'mimeType': 'APPLICATION_JSON', 'schema': payload['schema']}}
    else:
        config.update(responseMimeType='application/json', responseJsonSchema=payload['schema'])
    return {'system_instruction': {'parts': [{'text': payload['system']}]},
            'contents': [{'role': 'user', 'parts': parts}], 'generationConfig': config}


def post(model, body):
    call = Request(ENDPOINT.format(model=model), data=json.dumps(body).encode(), method='POST', headers={
        'Content-Type': 'application/json', 'x-goog-api-key': os.environ['GEMINI_API_KEY']})
    with urlopen(call, timeout=25) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ProviderError('OVERSIZED_OUTPUT')
    return json.loads(raw)


def parse(result):
    if (result.get('promptFeedback') or {}).get('blockReason'):
        raise ProviderError('BLOCKED')
    candidates = result.get('candidates') or []
    if not candidates:
        raise ProviderError('NO_OUTPUT')
    finish = candidates[0].get('finishReason')
    if finish != 'STOP':
        raise ProviderError('MAX_TOKENS' if finish == 'MAX_TOKENS' else f'FINISH_{finish or "NONE"}')
    parts = (candidates[0].get('content') or {}).get('parts') or []
    text = ''.join(part['text'] for part in parts if isinstance(part.get('text'), str) and not part.get('thought'))
    try:
        return json.loads(text)
    except ValueError:
        raise ProviderError('INVALID_JSON') from None


def request(payload):
    model = payload['model']
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,63}', model):
        raise ProviderError('INVALID_MODEL')
    if not os.environ.get('GEMINI_API_KEY'):
        raise ProviderError('NOT_CONFIGURED')
    for variant in ('current', 'json_schema'):
        try:
            return parse(post(model, build(payload, variant)))
        except HTTPError as error:
            detail = error.read(4096)
            # Only an unrecognised request field earns the second request shape; anything else is a real failure.
            if variant == 'current' and error.code == 400 and b'Unknown name' in detail:
                continue
            code = {400: 'BAD_REQUEST', 401: 'KEY_REJECTED', 403: 'KEY_REJECTED', 404: 'MODEL_NOT_FOUND',
                    429: 'RATE_LIMITED'}.get(error.code, f'HTTP_{error.code}')
            if error.code == 400 and b'API key' in detail:
                code = 'KEY_REJECTED'
            raise ProviderError(code) from None
        except (URLError, TimeoutError, OSError):
            raise ProviderError('NETWORK') from None
    raise ProviderError('BAD_REQUEST')


if __name__ == '__main__':
    try:
        print(json.dumps({'output': request(json.loads(sys.stdin.read()))}))
    except ProviderError as failure:
        print(json.dumps({'error': failure.code}))
        raise SystemExit(1)
    except Exception:
        print(json.dumps({'error': 'PROVIDER_UNAVAILABLE'}))
        raise SystemExit(1)
