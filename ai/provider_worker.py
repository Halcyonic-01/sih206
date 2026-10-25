"""Tool-free Gemini generateContent transport, run in a child process; secrets never appear in stdout.

Input (stdin): {"model", "fallback_models", "system", "parts": [{"pdf": base64} | {"text": str}], "schema",
"max_output_tokens"}. Output (stdout): {"output": <parsed JSON>, "model": <model used>} or {"error": <short code>}
with exit status 1. All attempts share one time budget that ends before the parent's 30 s limit.
"""
import json
import os
import re
import socket
import sys
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
# Tests point the worker at a fake server on this machine; nothing else may redirect the key.
_TEST_ENDPOINT = os.environ.get('GEMINI_TEST_ENDPOINT', '')
if _TEST_ENDPOINT.startswith('http://127.0.0.1:'):
    ENDPOINT = _TEST_ENDPOINT.rstrip('/') + '/v1beta/models/{model}:generateContent'
MAX_RESPONSE_BYTES = 1024 * 1024
BUDGET_SECONDS = 27
# Busy or slow: worth one try on the fallback model. Anything else (bad key, bad request) is final.
RETRY_ON_NEXT_MODEL = {'OVERLOADED', 'RATE_LIMITED', 'TIMEOUT', 'HTTP_500', 'HTTP_502', 'HTTP_504'}


class ProviderError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def build(payload, variant='current', thinking=True):
    """The request body. 'current' is the documented REST shape; 'json_schema' is the earlier generationConfig form."""
    parts = [{'inline_data': {'mime_type': 'application/pdf', 'data': part['pdf']}} if 'pdf' in part
             else {'text': part['text']} for part in payload['parts']]
    config = {'maxOutputTokens': payload['max_output_tokens']}
    if thinking:
        config['thinkingConfig'] = {'thinkingLevel': 'low'}
    if variant == 'current':
        config['responseFormat'] = {'text': {'mimeType': 'APPLICATION_JSON', 'schema': payload['schema']}}
    else:
        config.update(responseMimeType='application/json', responseJsonSchema=payload['schema'])
    return {'system_instruction': {'parts': [{'text': payload['system']}]},
            'contents': [{'role': 'user', 'parts': parts}], 'generationConfig': config}


def post(model, body, timeout):
    call = Request(ENDPOINT.format(model=model), data=json.dumps(body).encode(), method='POST', headers={
        'Content-Type': 'application/json', 'x-goog-api-key': os.environ['GEMINI_API_KEY']})
    with urlopen(call, timeout=timeout) as response:
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


def http_code(error, detail):
    if error.code == 400 and b'API key' in detail:
        return 'KEY_REJECTED'
    return {400: 'BAD_REQUEST', 401: 'KEY_REJECTED', 403: 'KEY_REJECTED', 404: 'MODEL_NOT_FOUND',
            429: 'RATE_LIMITED', 503: 'OVERLOADED'}.get(error.code, f'HTTP_{error.code}')


def attempt(model, payload, deadline):
    """One model: the documented request first; adjust once for an unrecognised field or thinking level."""
    variant, thinking = 'current', True
    for _ in range(3):
        remaining = deadline - monotonic()
        if remaining < 1:
            raise ProviderError('TIMEOUT')
        try:
            return parse(post(model, build(payload, variant, thinking), remaining))
        except HTTPError as error:
            detail = error.read(4096)
            if error.code == 400 and variant == 'current' and b'Unknown name' in detail:
                variant = 'json_schema'
                continue
            if error.code == 400 and thinking and b'hinking' in detail:
                thinking = False
                continue
            raise ProviderError(http_code(error, detail)) from None
        except (socket.timeout, TimeoutError):
            raise ProviderError('TIMEOUT') from None
        except URLError as error:
            raise ProviderError('TIMEOUT' if isinstance(error.reason, (socket.timeout, TimeoutError))
                                else 'NETWORK') from None
        except OSError:
            raise ProviderError('NETWORK') from None
    raise ProviderError('BAD_REQUEST')


def request(payload):
    """Returns (output, model used). Tries the fallback models only when the previous one was busy or slow."""
    models = [payload['model'], *payload.get('fallback_models', [])]
    if not all(re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,63}', model) for model in models):
        raise ProviderError('INVALID_MODEL')
    if not os.environ.get('GEMINI_API_KEY'):
        raise ProviderError('NOT_CONFIGURED')
    deadline = monotonic() + BUDGET_SECONDS
    for index, model in enumerate(models):
        try:
            return attempt(model, payload, deadline), model
        except ProviderError as failure:
            if failure.code not in RETRY_ON_NEXT_MODEL or index == len(models) - 1:
                raise


if __name__ == '__main__':
    try:
        output, used = request(json.loads(sys.stdin.read()))
        print(json.dumps({'output': output, 'model': used}))
    except ProviderError as failure:
        print(json.dumps({'error': failure.code}))
        raise SystemExit(1)
    except Exception:
        print(json.dumps({'error': 'PROVIDER_UNAVAILABLE'}))
        raise SystemExit(1)
