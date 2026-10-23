"""Live Milestone 5 checks; adds two synthetic instruments and preserves all existing records."""
import argparse
import hashlib
import json
import re
import uuid

import smoke_http as http
from smoke_maturity import ReportPage, cards, command_report

RESULT = http.ROOT / 'data' / 'milestone5-smoke-result.json'
EVIDENCE = http.ROOT / 'fixtures' / 'release-evidence.pdf'
APPROVAL = 'Authorized after manual review of this synthetic request.'
COMPLETION = 'Manually inspected the attached synthetic discharge PDF.'
REJECTION = 'Rejected: prescribed supporting confirmation is absent in this demo.'


def version(html):
    return http.Fields(html).values['version']


def release_id(html):
    return int(re.search(r'data-release-id="(\d+)" data-release-status="PENDING"', html).group(1))


def verify(institution, other, officer, authority, saved):
    completed, rejected = saved['completed'], saved['rejected']
    html = institution.page(completed['detail'])
    assert '<strong>Release completion recorded</strong>' in html
    assert 'data-release-status="COMPLETED"' in html and APPROVAL in html and COMPLETION in html
    assert 'RELEASE_REQUESTED' in html and 'RELEASE_APPROVED' in html and 'RELEASE_COMPLETED' in html
    assert 'Not independently bank-verified' in html
    rejected_html = institution.page(rejected['detail'])
    assert 'data-release-status="REJECTED"' in rejected_html and REJECTION in rejected_html
    assert 'Included in accepted maturity monitoring.' in rejected_html
    report = command_report()
    assert completed['reference'] + '\t' not in report
    assert rejected['reference'] + '\t' in report
    current = cards(officer)
    ids = ReportPage(officer.page(current['accepted']['url'])).ids
    assert completed['id'] not in ids and rejected['id'] in ids
    for record in (completed, rejected):
        assert other.request(record['detail'])[0] == 404
        for path in record['original_documents']:
            http.check_document(institution, path, saved['original_hash'])
            assert other.request(path)[0] == 404
    http.check_document(institution, completed['evidence'], saved['evidence_hash'])
    http.check_document(authority, completed['evidence'], saved['evidence_hash'])
    assert other.request(completed['evidence'])[0] == 404
    pending = authority.page('/releases/')
    assert completed['reference'] not in pending and rejected['reference'] not in pending
    assert completed['reference'] in authority.page('/releases/?status=COMPLETED')
    assert rejected['reference'] in authority.page('/releases/?status=REJECTED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='Verify saved scenario without creating more records.')
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    http.BASE = args.base_url.rstrip('/')
    passwords = {}
    for filename in ('demo-credentials.txt', 'authority-credentials.txt'):
        for line in (http.ROOT / 'data' / filename).read_text().splitlines():
            if ': ' in line:
                name, password = line.split(': ', 1)
                passwords[name] = password
    institution, other, officer, authority = [http.login(name, passwords) for name in
                                             ('institution_a', 'institution_b', 'officer', 'authority')]
    if args.verify:
        verify(institution, other, officer, authority, json.loads(RESULT.read_text()))
        print('PASS: release decisions, original PDFs, completion evidence, protected access and monitoring persist after restart.')
        return

    prefix = 'RELEASE-' + uuid.uuid4().hex[:8]
    saved = {'original_hash': hashlib.sha256((http.ROOT / 'fixtures' / 'sample-fdr.pdf').read_bytes()).hexdigest(),
             'evidence_hash': hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()}
    for outcome in ('completed', 'rejected'):
        reference = prefix + '-' + outcome
        values = {'reference': reference, 'bank': 'Fictional Release Bank', 'amount': '100000.00',
                  'issue_date': '2026-01-01', 'maturity_date': '2026-10-22'}
        status, body, url = institution.post('/instruments/new/', values, upload=True)
        assert status == 200
        detail = url.removeprefix(http.BASE)
        html = body.decode()
        assert institution.post(detail + 'submit/', {'version': version(html)}, html)[0] == 200
        html = officer.page(detail)
        assert officer.post(detail + 'review/', {'version': version(html), 'decision': 'accept',
            'reason': 'Manually reviewed synthetic FDR.'}, html)[0] == 200
        html = institution.page(detail)
        original_documents = list(dict.fromkeys(re.findall(r'href="(/documents/\d+/download/)"', html)))
        status, body, _ = institution.post(detail + 'release-requests/', {
            'version': version(html), 'reason': 'Synthetic release request for human assessment.',
        }, html)
        assert status == 200
        html = body.decode()
        request_id = release_id(html)
        decision_path = detail + f'release-requests/{request_id}/decision/'
        completion_path = detail + f'release-requests/{request_id}/completion/'
        assert reference in authority.page('/releases/')
        pending_version = version(authority.page(detail))
        for actor in (institution, officer):
            page = actor.page(detail)
            assert actor.post(decision_path, {'version': pending_version, 'decision': 'approve',
                                              'reason': 'Unauthorized decision.'}, page)[0] == 403
        assert institution.request(detail + 'renew/')[0] == 409
        assert institution.post(detail + 'release-requests/', {
            'version': pending_version, 'reason': 'Duplicate request.',
        }, html)[0] == 409
        html = authority.page(detail)
        status, body, _ = authority.post(decision_path, {
            'version': version(html), 'decision': 'approve' if outcome == 'completed' else 'reject',
            'reason': APPROVAL if outcome == 'completed' else REJECTION,
        }, html)
        assert status == 200
        html = body.decode()
        saved[outcome] = {'reference': reference, 'detail': detail, 'release_id': request_id,
                          'id': int(re.search(r'/instruments/(\d+)/', detail).group(1)),
                          'original_documents': original_documents}
        if outcome == 'completed':
            assert 'Release authorized; completion pending.' in html
            assert reference + '\t' in command_report()
            accepted_before = cards(officer)['accepted']['count']
            completion_version = version(html)
            assert authority.post(completion_path, {'version': completion_version, 'notes': COMPLETION}, html)[0] == 400
            status, body, _ = authority.post(completion_path, {'version': completion_version, 'notes': COMPLETION},
                                             html, upload=True, upload_path=EVIDENCE)
            assert status == 200
            html = body.decode()
            evidence_path = re.search(r'data-release-evidence="\d+" href="([^"]+)"', html).group(1)
            saved[outcome]['evidence'] = evidence_path
            assert cards(officer)['accepted']['count'] == accepted_before - 1
            assert authority.post(completion_path, {'version': completion_version, 'notes': 'Repeat.'}, html,
                                   upload=True, upload_path=EVIDENCE)[0] == 409
        else:
            assert reference + '\t' in command_report()
            assert authority.post(completion_path, {'version': pending_version, 'notes': 'Rejected request.'}, html,
                                   upload=True, upload_path=EVIDENCE)[0] == 409
    verify(institution, other, officer, authority, saved)
    RESULT.write_text(json.dumps(saved, indent=2))
    print('PASS: pending requests, role separation, authority approval/rejection, evidence-required completion and monitoring cutover.')
    print('Two synthetic RELEASE records remain. Restart, then run with --verify without adding records.')


if __name__ == '__main__':
    main()
