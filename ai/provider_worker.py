"""Tool-free Anthropic Messages transport; secrets never appear in stdout."""
import json
import os
import sys
from urllib.request import Request, urlopen


def request(payload):
    encoded = json.dumps(payload).encode()
    call = Request('https://api.anthropic.com/v1/messages', data=encoded, method='POST', headers={
        'Content-Type': 'application/json', 'anthropic-version': '2023-06-01',
        'x-api-key': os.environ['ANTHROPIC_API_KEY']})
    with urlopen(call, timeout=25) as response:
        body = response.read(1024 * 1024 + 1)
    if len(body) > 1024 * 1024:
        raise ValueError('oversized output')
    result = json.loads(body)
    if result.get('stop_reason') != 'end_turn':
        raise ValueError('incomplete output')
    text = ''.join(part['text'] for part in result.get('content', []) if part.get('type') == 'text')
    return json.loads(text)


if __name__ == '__main__':
    try:
        print(json.dumps({'output': request(json.loads(sys.stdin.read()))}))
    except Exception:
        print(json.dumps({'error': 'PROVIDER_UNAVAILABLE'}))
        raise SystemExit(1)
