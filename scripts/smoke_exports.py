"""Read-only HTTP verification of scoped CSV, filters and optional packaged scenarios."""
import argparse
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path
import re
from statistics import median
from time import perf_counter
from urllib.parse import urlencode

import smoke_http
from smoke_http import Browser, login, ROOT
from smoke_maturity import ReportPage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    parser.add_argument('--scenarios', action='store_true', help='Also check initial synthetic manifest scope and documents.')
    args = parser.parse_args()
    smoke_http.BASE = args.base.rstrip('/')
    passwords = {}
    for name in ('demo-credentials.txt', 'authority-credentials.txt'):
        for line in (ROOT / 'data' / name).read_text().splitlines():
            if ': ' in line:
                username, password = line.split(': ', 1)
                passwords[username] = password
    assert Browser().request('/instruments/export.csv')[2].startswith(smoke_http.BASE + '/accounts/login/')
    categories = ('all', 'pending', 'accepted', 'approaching', 'today', 'matured')
    elapsed, exported, documents = [], {}, set()
    for username in ('institution_a', 'institution_b', 'officer', 'authority'):
        browser = login(username, passwords)
        for category in categories:
            query = urlencode({'category': category, 'as_of': '2026-10-23', 'institution': 'forged'})
            page = browser.page('/?' + query)
            parsed = ReportPage(page)
            start = perf_counter()
            status, body, _ = browser.request('/instruments/export.csv?' + query)
            elapsed.append((perf_counter() - start) * 1000)
            assert status == 200
            rows = list(csv.DictReader(StringIO(body.decode('utf-8-sig'))))
            assert {int(row['ID']) for row in rows} == parsed.ids
            assert all(row['Evaluation date'] == '2026-10-23' for row in rows)
            assert 'Export this view as CSV' in page
            if category == 'all':
                exported[username] = set(parsed.ids)
        assert browser.request('/instruments/export.csv?category=invalid')[0] == 400
        assert browser.request('/instruments/export.csv?as_of=invalid')[0] == 400
        if args.scenarios:
            ids = json.loads((ROOT / 'data/scenarios-v1.json').read_text())['instruments']
            expected = (set(ids.values()) - {ids['other_institution']} if username == 'institution_a'
                        else {ids['other_institution']} if username == 'institution_b'
                        else set(ids.values()) - {ids['duplicate_proposal']})
            assert exported[username] == expected
            allowed_hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in (ROOT / 'fixtures').glob('*.pdf')}
            for pk in expected:
                html = browser.page(f'/instruments/{pk}/')
                for path in re.findall(r'href="(/documents/\d+/download/)"', html):
                    status, content, _ = browser.request(path)
                    assert status == 200 and hashlib.sha256(content).hexdigest() in allowed_hashes
                    documents.add(path)
            if username == 'institution_a':
                assert browser.request(f'/instruments/{ids["other_institution"]}/')[0] == 404
        dashboard = browser.page('/dashboard/?as_of=2026-10-23')
        assert 'http://' not in dashboard and 'https://' not in dashboard
        assert browser.request('/static/css/app.css')[0] == 200
    print(json.dumps({'result': 'PASS', 'role_category_comparisons': 24, 'documents_checked': len(documents),
                      'visible_counts': {key: len(value) for key, value in exported.items()},
                      'csv_http_ms': {'n': len(elapsed), 'median': round(median(elapsed), 2),
                                      'min': round(min(elapsed), 2), 'max': round(max(elapsed), 2)}}, indent=2))


if __name__ == '__main__':
    main()
