"""Read synthetic CSVs, compare literal labels, print counts; never import rows."""
import json
from pathlib import Path

from obligations.csv_validation import ExistingIdentity, validate_institution_csv

ROOT = Path(__file__).resolve().parent


def evaluate():
    dataset = json.loads((ROOT / 'cases.json').read_text(encoding='utf-8'))
    if dataset['data_classification'] != 'SYNTHETIC' or dataset['simulation_label'] != 'SIMULATED':
        raise ValueError('Synthetic labelled dataset required.')
    cases = dataset['cases']
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate scenario IDs.')
    rows = []
    for case in cases:
        path = (ROOT / case['file']).resolve()
        if path.parent != ROOT or path.suffix != '.csv':
            raise ValueError('Dataset CSV must be in this fixture folder.')
        actual = validate_institution_csv(path.read_bytes(), existing_identities=tuple(
            ExistingIdentity(**entry) for entry in case['existing']))
        comparable = {key: actual[key] for key in case['expected'] if key != 'valid_row_numbers'}
        comparable['valid_row_numbers'] = [row['row'] for row in actual['valid_rows']]
        passed = comparable == case['expected']
        by_number = {str(row['row']): row['values'] for row in actual['valid_rows']}
        for number, fields in case.get('expected_values', {}).items():
            passed &= all(by_number.get(number, {}).get(key) == value for key, value in fields.items())
        rows.append({'id': case['id'], 'passed': passed, 'source_sha256': actual['source_sha256']})
    return {'dataset_id': dataset['dataset_id'], 'review_status': dataset['review_status'],
            'case_count': len(rows), 'passed': sum(r['passed'] for r in rows),
            'failed': sum(not r['passed'] for r in rows), 'cases': rows}


if __name__ == '__main__':
    result = evaluate()
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result['failed'] else 0)
