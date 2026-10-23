"""Live Milestone 2 acceptance check. Creates two synthetic records; no secrets printed."""
import argparse
import hashlib
import json
import re
import uuid

import smoke_http as http

RESULT = http.ROOT / 'data' / 'milestone2-smoke-result.json'
PDF = http.ROOT / 'fixtures' / 'scrutiny-fdr.pdf'
COMMENT = 'Manual amount mismatch: declared INR 500000.00; PDF page 1 states INR 600000.00.'
RESOLUTION = 'Manually rechecked page 1 against the corrected INR 600000.00 declaration.'


def version(html):
    return http.Fields(html).values['version']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='Verify the saved result after a server restart.')
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    http.BASE = args.base_url.rstrip('/')
    passwords = {}
    for line in (http.ROOT / 'data' / 'demo-credentials.txt').read_text().splitlines():
        if ': ' in line:
            name, password = line.split(': ', 1)
            passwords[name] = password
    institution = http.login('institution_a', passwords)
    if args.verify:
        saved = json.loads(RESULT.read_text())
        html = institution.page(saved['detail'])
        assert saved['reference'] in html and '<span class="badge">Accepted for tracking</span>' in html
        assert COMMENT in html and RESOLUTION in html and '<strong>Resolved</strong>' in html
        assert 'POSSIBLE_DUPLICATE' in html and 'Not independently bank-verified' in html
        for path in saved['documents']:
            http.check_document(institution, path, saved['hash'])
        print('PASS: scrutiny findings, original observation, page reference, resolution, decisions and PDFs persist after restart.')
        return

    reference = 'SCRUTINY-' + uuid.uuid4().hex[:8]
    values = {'reference': reference, 'bank': 'Fictional Scrutiny Bank', 'amount': '500000.00',
              'issue_date': '2026-01-01', 'maturity_date': '2027-01-01'}
    status, body, url = institution.post('/instruments/new/', values, upload=True, upload_path=PDF)
    assert status == 200 and b'Draft saved.' in body
    detail = url.removeprefix(http.BASE)
    # A second draft in the SAME institution creates an advisory duplicate warning.
    assert institution.post('/instruments/new/', values)[0] == 200
    html = institution.page(detail)
    assert 'POSSIBLE_DUPLICATE' in html
    status, _, _ = institution.post(detail + 'submit/', {'version': version(html)}, html)
    assert status == 200
    officer = http.login('officer', passwords)
    html = officer.page(detail)
    document = re.search(r'href="/documents/(\d+)/download/"', html).group(1)
    status, body, _ = officer.post(detail + 'observations/', {
        'version': version(html), 'document': document, 'page_number': 1,
        'severity': 'BLOCKING', 'comment': COMMENT,
    }, html)
    assert status == 200 and COMMENT.encode() in body and b'Page 1' in body
    html = body.decode()
    status, body, _ = officer.post(detail + 'review/', {
        'version': version(html), 'decision': 'accept', 'reason': 'Attempt with unresolved finding.',
    }, html)
    assert status == 409 and b'Resolve all blocking observations' in body
    assert COMMENT in institution.page(detail)

    html = officer.page(detail)
    assert officer.post(detail + 'review/', {
        'version': version(html), 'decision': 'changes', 'reason': 'Correct the declared amount using page 1.',
    }, html)[0] == 200
    html = institution.page(detail + 'edit/')
    status, body, _ = institution.post(detail + 'edit/', {
        **values, 'amount': '600000.00', 'version': version(html),
    }, html, upload=True, upload_path=PDF)
    assert status == 200
    html = body.decode()
    assert institution.post(detail + 'submit/', {'version': version(html)}, html)[0] == 200
    html = officer.page(detail)
    assert COMMENT in html and '<strong>Unresolved</strong>' in html
    status, body, _ = officer.post(detail + 'review/', {
        'version': version(html), 'decision': 'accept', 'reason': 'Finding still unresolved.',
    }, html)
    assert status == 409
    html = officer.page(detail)
    resolve_path = re.search(r'action="([^"]+/observations/\d+/resolve/)"', html).group(1)
    status, body, _ = officer.post(resolve_path, {'version': version(html), 'resolution': RESOLUTION}, html)
    assert status == 200 and b'<strong>Resolved</strong>' in body
    html = body.decode()
    assert officer.post(detail + 'review/', {
        'version': version(html), 'decision': 'accept', 'reason': 'Manual scrutiny complete; bank remains unverified.',
    }, html)[0] == 200

    html = institution.page(detail)
    assert '<span class="badge">Accepted for tracking</span>' in html
    assert 'Not independently bank-verified' in html and COMMENT in html and RESOLUTION in html
    assert 'OBSERVATION_ADDED' in html and 'OBSERVATION_RESOLVED' in html
    assert '50000000' in html and '60000000' in html
    documents = list(dict.fromkeys(re.findall(r'href="(/documents/\d+/download/)"', html)))
    assert len(documents) == 2
    digest = hashlib.sha256(PDF.read_bytes()).hexdigest()
    for path in documents:
        http.check_document(institution, path, digest)
    other = http.login('institution_b', passwords)
    assert other.request(detail)[0] == 404
    assert other.request(documents[0])[0] == 404
    RESULT.write_text(json.dumps({'detail': detail, 'reference': reference,
                                 'documents': documents, 'hash': digest}, indent=2))
    print('PASS: duplicate warning, manual PDF/page finding, blocked acceptance, correction, explicit resolution, audit and bank disclaimer.')
    print('Two synthetic SCRUTINY records remain in the local database. Restart, then run with --verify.')


if __name__ == '__main__':
    main()
