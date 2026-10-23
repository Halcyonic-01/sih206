"""Live Milestone 4 checks; adds two synthetic instruments without modifying existing records."""
import argparse
import hashlib
import json
import re
import uuid

import smoke_http as http
from smoke_maturity import ReportPage, cards, command_report

RESULT = http.ROOT / 'data' / 'milestone4-smoke-result.json'


def version(html):
    return http.Fields(html).values['version']


def verify(institution, other, officer, saved):
    parent, child = saved['parent'], saved['child']
    parent_html, child_html = institution.page(parent['detail']), institution.page(child['detail'])
    assert '<strong>Superseded</strong>' in parent_html
    assert f'data-lineage="successor" href="{child["detail"]}"' in parent_html
    assert f'data-lineage="predecessor" href="{parent["detail"]}"' in child_html
    assert 'SUPERSEDED' in parent_html and 'Manually accepted the successor.' in parent_html
    assert 'Not independently bank-verified' in parent_html and 'Not independently bank-verified' in child_html
    assert 'Included in accepted maturity monitoring.' in child_html
    report = command_report()
    assert parent['reference'] + '\t' not in report
    assert child['reference'] + '\t' in report
    current = cards(officer)
    accepted_ids = ReportPage(officer.page(current['accepted']['url'])).ids
    assert parent['id'] not in accepted_ids and child['id'] in accepted_ids
    for entry in (parent, child):
        assert other.request(entry['detail'])[0] == 404
        for path in entry['documents']:
            http.check_document(institution, path, saved['hash'])
            assert other.request(path)[0] == 404


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='Check saved scenario after restart, without creating records.')
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    http.BASE = args.base_url.rstrip('/')
    passwords = {}
    for line in (http.ROOT / 'data' / 'demo-credentials.txt').read_text().splitlines():
        if ': ' in line:
            name, password = line.split(': ', 1)
            passwords[name] = password
    institution, other, officer = [http.login(name, passwords) for name in ('institution_a', 'institution_b', 'officer')]
    if args.verify:
        verify(institution, other, officer, json.loads(RESULT.read_text()))
        print('PASS: renewal lineage, historical PDFs, supersession audit and current monitoring persist after restart.')
        return

    prefix = 'RENEWAL-' + uuid.uuid4().hex[:8]
    original = {'reference': prefix + '-ORIGINAL', 'bank': 'Fictional Renewal Bank',
                'amount': '500000.00', 'issue_date': '2026-01-01', 'maturity_date': '2026-10-22'}
    status, body, url = institution.post('/instruments/new/', original, upload=True)
    assert status == 200
    parent_detail = url.removeprefix(http.BASE)
    html = body.decode()
    assert institution.post(parent_detail + 'submit/', {'version': version(html)}, html)[0] == 200
    html = officer.page(parent_detail)
    assert officer.post(parent_detail + 'review/', {
        'version': version(html), 'decision': 'accept', 'reason': 'Manually reviewed the original synthetic instrument.',
    }, html)[0] == 200
    original_count = cards(officer)['accepted']['count']
    assert original['reference'] + '\t' in command_report()
    html = institution.page(parent_detail + 'renew/')
    fields = http.Fields(html).values
    renewal = {'reference': prefix + '-SUCCESSOR', 'bank': original['bank'], 'amount': '600000.00',
               'issue_date': '2026-10-23', 'maturity_date': '2026-10-30',
               'predecessor_version': fields['predecessor_version']}
    status, body, url = institution.post(parent_detail + 'renew/', renewal, html, upload=True)
    assert status == 200 and b'Linked renewal draft saved.' in body
    child_detail = url.removeprefix(http.BASE)
    assert officer.request(child_detail)[0] == 404
    assert prefix + '-SUCCESSOR' not in officer.page(parent_detail)
    assert institution.post(parent_detail + 'renew/', renewal, institution.page(parent_detail), upload=True)[0] == 409
    assert original['reference'] + '\t' in command_report()

    html = institution.page(child_detail)
    assert institution.post(child_detail + 'submit/', {'version': version(html)}, html)[0] == 200
    html = officer.page(child_detail)
    assert officer.post(child_detail + 'review/', {
        'version': version(html), 'decision': 'changes', 'reason': 'Confirm the successor declaration and add the corrected PDF.',
    }, html)[0] == 200
    assert original['reference'] + '\t' in command_report()
    html = institution.page(child_detail + 'edit/')
    corrected = {key: value for key, value in renewal.items() if key != 'predecessor_version'}
    corrected['version'] = version(html)
    status, body, _ = institution.post(child_detail + 'edit/', corrected, html, upload=True)
    assert status == 200
    html = body.decode()
    assert institution.post(child_detail + 'submit/', {'version': version(html)}, html)[0] == 200
    html = officer.page(child_detail)
    assert officer.post(child_detail + 'review/', {
        'version': version(html), 'decision': 'accept', 'reason': 'Manually accepted the successor.',
    }, html)[0] == 200
    assert cards(officer)['accepted']['count'] == original_count

    saved = {'hash': hashlib.sha256((http.ROOT / 'fixtures' / 'sample-fdr.pdf').read_bytes()).hexdigest()}
    for name, detail, reference in [('parent', parent_detail, original['reference']),
                                     ('child', child_detail, renewal['reference'])]:
        html = institution.page(detail)
        saved[name] = {'detail': detail, 'reference': reference,
                       'id': int(re.search(r'/instruments/(\d+)/', detail).group(1)),
                       'documents': list(dict.fromkeys(re.findall(r'href="(/documents/\d+/download/)"', html)))}
    assert len(saved['parent']['documents']) == 1 and len(saved['child']['documents']) == 2
    verify(institution, other, officer, saved)
    RESULT.write_text(json.dumps(saved, indent=2))
    print('PASS: linked draft, correction, competing-proposal rejection, atomic acceptance, preserved PDFs and current monitoring.')
    print('Two synthetic RENEWAL instruments remain. Restart, then run with --verify without adding records.')


if __name__ == '__main__':
    main()
