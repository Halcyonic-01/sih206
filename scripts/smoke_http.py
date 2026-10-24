"""Exercise the local server over HTTP, with cookies, CSRF, and real PDF uploads.

Creates one synthetic accepted instrument. Run --verify after restarting the server.
No private credentials are printed. Standard library only; no browser dependency.
"""
import argparse
import hashlib
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import json
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, Request
import uuid

ROOT = Path(__file__).resolve().parent.parent
BASE = 'http://127.0.0.1:8000'
# The Django-template interface moved under /legacy/ when the React app took over the root.
LEGACY = '/legacy'
RESULT = ROOT / 'data' / 'live-smoke-result.json'


class Fields(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'input' and attributes.get('name'):
            self.values[attributes['name']] = attributes.get('value', '')


class Browser:
    def __init__(self):
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(self, path, data=None, headers=None):
        if not path.startswith((LEGACY + '/', '/api/')):
            path = LEGACY + path
        request = Request(BASE + path, data=data, headers=headers or {})
        try:
            response = self.opener.open(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.geturl()

    def page(self, path):
        status, body, _ = self.request(path)
        assert status == 200, f'Expected HTTP 200 at {path}; received {status}'
        return body.decode()

    def post(self, path, values, page=None, upload=False, upload_path=None):
        fields = Fields(page if page is not None else self.page(path)).values
        values = {'csrfmiddlewaretoken': fields['csrfmiddlewaretoken'], **values}
        if upload:
            boundary = 'fdr-' + uuid.uuid4().hex
            data = b''
            for key, value in values.items():
                data += (f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n').encode()
            data += (f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="synthetic.pdf"\r\n'
                     'Content-Type: application/pdf\r\n\r\n').encode()
            data += (upload_path or ROOT / 'fixtures' / 'sample-fdr.pdf').read_bytes()
            data += f'\r\n--{boundary}--\r\n'.encode()
            content_type = f'multipart/form-data; boundary={boundary}'
        else:
            data, content_type = urlencode(values).encode(), 'application/x-www-form-urlencoded'
        return self.request(path, data, {'Content-Type': content_type})


def login(username, passwords):
    browser = Browser()
    status, body, _ = browser.post('/accounts/login/', {'username': username, 'password': passwords[username]})
    assert status == 200 and b'Sign out' in body, f'Login failed for {username}'
    return browser


def check_document(browser, path, expected_hash):
    status, data, _ = browser.request(path)
    assert status == 200 and hashlib.sha256(data).hexdigest() == expected_hash


def main():
    global BASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--base-url', default=BASE)
    args = parser.parse_args()
    BASE = args.base_url.rstrip('/')
    passwords = {}
    for line in (ROOT / 'data' / 'demo-credentials.txt').read_text().splitlines():
        if ': ' in line:
            name, password = line.split(': ', 1)
            passwords[name] = password
    institution = login('institution_a', passwords)
    if args.verify:
        saved = json.loads(RESULT.read_text())
        html = institution.page(saved['detail'])
        assert saved['reference'] in html and 'Accepted for tracking' in html
        assert 'Correct the declared amount.' in html and 'Compared the corrected details.' in html
        for path in saved['documents']:
            check_document(institution, path, saved['hash'])
        print('PASS: record, decisions, correction history, and both PDFs survive server restart.')
        return

    reference = 'SMOKE-' + uuid.uuid4().hex[:8]
    values = {'reference': reference, 'bank': 'Fictional Bank', 'amount': '500000.00',
              'issue_date': '2026-01-01', 'maturity_date': '2027-01-01'}
    status, body, url = institution.post('/instruments/new/', values, upload=True)
    assert status == 200 and b'Draft saved.' in body
    detail = url.removeprefix(BASE)
    html = body.decode()
    assert 'DRAFT_CREATED' in html
    status, body, _ = institution.post(detail + 'submit/', {'version': Fields(html).values['version']}, html)
    assert status == 200 and b'Submitted for officer review.' in body

    officer = login('officer', passwords)
    assert reference in officer.page('/')
    html = officer.page(detail)
    status, body, _ = officer.post(detail + 'review/', {
        'version': Fields(html).values['version'], 'decision': 'changes', 'reason': 'Correct the declared amount.',
    }, html)
    assert status == 200 and b'CHANGES_REQUESTED' in body

    html = institution.page(detail + 'edit/')
    status, body, _ = institution.post(detail + 'edit/', {
        **values, 'amount': '600000.00', 'version': Fields(html).values['version'],
    }, html, upload=True)
    assert status == 200 and b'Changes saved.' in body
    html = body.decode()
    status, body, _ = institution.post(detail + 'submit/', {'version': Fields(html).values['version']}, html)
    assert status == 200
    html = officer.page(detail)
    status, body, _ = officer.post(detail + 'review/', {
        'version': Fields(html).values['version'], 'decision': 'accept', 'reason': 'Compared the corrected details.',
    }, html)
    assert status == 200 and b'Accepted for tracking' in body
    html = institution.page(detail)
    documents = re.findall(r'href="(/documents/\d+/download/)"', html)
    assert len(documents) == 2 and '50000000' in html and '60000000' in html
    digest = hashlib.sha256((ROOT / 'fixtures' / 'sample-fdr.pdf').read_bytes()).hexdigest()
    for path in documents:
        check_document(institution, path, digest)
    other = login('institution_b', passwords)
    assert reference not in other.page('/')
    assert other.request(detail)[0] == 404
    assert other.request(documents[0])[0] == 404
    assert Browser().request(documents[0])[2].startswith(BASE + LEGACY + '/accounts/login/')
    assert institution.request(detail + 'review/', b'decision=accept')[0] == 403
    RESULT.write_text(json.dumps({'detail': detail, 'reference': reference,
                                 'documents': documents, 'hash': digest}, indent=2))
    print('PASS: live HTTP login, PDF upload/download, submit, correction, resubmit, acceptance, history, isolation, and CSRF.')
    print('One accepted synthetic SMOKE record remains in the local database. Restart the server, then run with --verify.')


if __name__ == '__main__':
    main()
