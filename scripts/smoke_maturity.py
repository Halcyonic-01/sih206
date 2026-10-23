"""Live Milestone 3 acceptance checks. Adds synthetic records, never changes existing ones."""
import argparse
from datetime import date, timedelta
import hashlib
from html.parser import HTMLParser
import json
import re
import subprocess
import sys
import uuid

import smoke_http as http

AS_OF = date(2026, 10, 23)
RESULT = http.ROOT / 'data' / 'milestone3-smoke-result.json'


class ReportPage(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.cards = {}
        self.ids = set()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'a' and 'data-category' in attributes:
            self.cards[attributes['data-category']] = {
                'count': int(attributes['data-count']), 'url': attributes['href']}
        if tag == 'tr' and 'data-instrument-id' in attributes:
            self.ids.add(int(attributes['data-instrument-id']))


def cards(browser):
    html = browser.page('/dashboard/?as_of=' + AS_OF.isoformat())
    assert 'Demo evaluation date: 2026-10-23' in html
    result = ReportPage(html).cards
    assert len(result) == 6
    for category, card in result.items():
        listing = browser.page(card['url'])
        assert len(ReportPage(listing).ids) == card['count'], f'Dashboard/list mismatch: {category}'
    return result


def command_report():
    completed = subprocess.run([sys.executable, 'manage.py', 'due_actions', '--as-of', AS_OF.isoformat()],
                               cwd=http.ROOT, check=True, capture_output=True, text=True)
    return completed.stdout


def verify(institution, other, officer, saved):
    institution_cards = cards(institution)
    other_cards = cards(other)
    officer_cards = cards(officer)
    for name, expected in [('matured', {'past'}), ('today', {'today'}),
                           ('approaching', {'seven', 'fifteen', 'thirty'})]:
        ids = ReportPage(institution.page(institution_cards[name]['url'])).ids
        assert {saved['records'][key]['id'] for key in expected}.issubset(ids)
        assert saved['records']['other']['id'] not in ids
        for excluded in ('later', 'pending', 'draft'):
            assert saved['records'][excluded]['id'] not in ids
    assert saved['records']['other']['id'] in ReportPage(other.page(other_cards['approaching']['url'])).ids
    assert saved['records']['seven']['id'] not in ReportPage(other.page(other_cards['approaching']['url'])).ids
    assert saved['records']['draft']['id'] not in ReportPage(officer.page(officer_cards['all']['url'])).ids
    database = http.ROOT / 'data' / 'portal.sqlite3'
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    first, second = command_report(), command_report()
    assert first == second and hashlib.sha256(database.read_bytes()).hexdigest() == before
    total = sum(officer_cards[category]['count'] for category in ('approaching', 'today', 'matured'))
    assert f'Total due instruments: {total}' in first
    for key in ('past', 'today', 'seven', 'fifteen', 'thirty', 'other'):
        assert saved['records'][key]['reference'] + '\t' in first
    for key in ('later', 'pending', 'draft'):
        assert saved['records'][key]['reference'] + '\t' not in first
    assert http.Browser().request('/dashboard/')[2].startswith(http.BASE + '/accounts/login/')
    assert institution.request('/dashboard/?as_of=not-a-date')[0] == 400
    assert institution.request('/?category=unknown')[0] == 400


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='Recheck saved records without creating more.')
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    http.BASE = args.base_url.rstrip('/')
    passwords = {}
    for line in (http.ROOT / 'data' / 'demo-credentials.txt').read_text().splitlines():
        if ': ' in line:
            name, password = line.split(': ', 1)
            passwords[name] = password
    institution = http.login('institution_a', passwords)
    other = http.login('institution_b', passwords)
    officer = http.login('officer', passwords)
    if args.verify:
        verify(institution, other, officer, json.loads(RESULT.read_text()))
        print('PASS: maturity dashboard, filtered counts, scope and repeated read-only report remain correct after restart.')
        return

    prefix = 'MATURITY-' + uuid.uuid4().hex[:8]
    saved = {'as_of': AS_OF.isoformat(), 'records': {}}
    for key, days, owner, decision in [
        ('past', -1, institution, True), ('today', 0, institution, True),
        ('seven', 7, institution, True), ('fifteen', 15, institution, True),
        ('thirty', 30, institution, True), ('later', 31, institution, True),
        ('other', 7, other, True), ('pending', 7, institution, False),
        ('draft', -1, institution, None),
    ]:
        reference = prefix + '-' + key
        values = {'reference': reference, 'bank': 'Fictional Maturity Bank', 'amount': '100000.00',
                  'issue_date': '2026-01-01', 'maturity_date': (AS_OF + timedelta(days=days)).isoformat()}
        status, body, url = owner.post('/instruments/new/', values, upload=True)
        assert status == 200 and b'Draft saved.' in body
        detail = url.removeprefix(http.BASE)
        saved['records'][key] = {'id': int(re.search(r'/instruments/(\d+)/', detail).group(1)),
                                 'reference': reference, 'detail': detail}
        if decision is not None:
            html = body.decode()
            assert owner.post(detail + 'submit/', {'version': http.Fields(html).values['version']}, html)[0] == 200
        if decision:
            html = officer.page(detail)
            assert officer.post(detail + 'review/', {
                'version': http.Fields(html).values['version'], 'decision': 'accept',
                'reason': 'Synthetic maturity demonstration; manual review completed.',
            }, html)[0] == 200
    verify(institution, other, officer, saved)
    RESULT.write_text(json.dumps(saved, indent=2))
    print('PASS: maturity boundaries, dashboard/list counts, institution isolation, and identical read-only due-action runs.')
    print('Nine synthetic MATURITY records remain. Restart, then run with --verify to recheck without adding records.')


if __name__ == '__main__':
    main()
