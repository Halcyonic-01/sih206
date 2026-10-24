"""S4 preview preparation only; SimpleTestCase forbids database access."""
from copy import deepcopy
import csv
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from django.test import SimpleTestCase

from evaluation.s4.run import ROOT as FIXTURES, evaluate
from obligations.csv_validation import (COLUMNS, LIMITS, MAX_BYTES, MAX_ROWS,
    CsvInputError, ExistingIdentity, validate_institution_csv)

ROW = dict(zip(COLUMNS, ['SYNTH-01', 'SYNTH-01', 'Synthetic Institute',
    'Synthetic Trust', 'PRIVATE', 'DEMO_NORTH', 'Synthetic State',
    'demo@example.invalid', 'ACTIVE', 'SIMULATED']))


def csv_bytes(rows=None, columns=COLUMNS):
    stream = StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(columns)
    for row in [ROW] if rows is None else rows:
        writer.writerow([row[column] for column in columns] if isinstance(row, dict) else row)
    return stream.getvalue().encode('utf-8')


def validate(content=None, existing=()):
    return validate_institution_csv(csv_bytes() if content is None else content,
                                    existing_identities=existing)


class InstitutionCsvTests(SimpleTestCase):
    def test_labelled_synthetic_dataset(self):
        before = {p.name: p.read_bytes() for p in FIXTURES.glob('*') if p.is_file()}
        result = evaluate()
        self.assertEqual(result['case_count'], 7)
        self.assertEqual(result['failed'], 0, result)
        self.assertEqual(result['passed'], 7)
        self.assertEqual(result['review_status'], 'AUTHOR_LABELLED_NOT_INDEPENDENTLY_ADJUDICATED')
        self.assertEqual({p.name: p.read_bytes() for p in FIXTURES.glob('*') if p.is_file()}, before)

    def test_evaluator_detects_missing_existing_conflict_checks(self):
        with patch('obligations.csv_validation._context', return_value={
                'aicte_id': set(), 'institution_code': set()}):
            result = evaluate()
        failed = [row['id'] for row in result['cases'] if not row['passed']]
        self.assertEqual(failed, ['existing-and-legacy-identities-are-conflicts'])

    def test_normalization_bom_crlf_unicode_and_quoted_commas(self):
        row = ROW | {'aicte_id': ' 00001 ', 'institution_code': ' synth-a ',
                     'institution_name': ' सिंथेटिक, Institute ', 'trust_name': ' O\'Brien Synthetic Trust '}
        content = b'\xef\xbb\xbf' + csv_bytes([row])
        result = validate(content)
        self.assertEqual(result['status'], 'VALID')
        values = result['valid_rows'][0]['values']
        self.assertEqual(values['aicte_id'], '00001')
        self.assertEqual(values['institution_code'], 'SYNTH-A')
        self.assertEqual(values['institution_name'], 'सिंथेटिक, Institute')
        self.assertEqual(values['trust_name'], "O'Brien Synthetic Trust")
        self.assertEqual(result['source_sha256'], hashlib.sha256(content).hexdigest())

    def test_header_order_is_irrelevant_and_lf_is_supported(self):
        result = validate(csv_bytes(columns=tuple(reversed(COLUMNS))).replace(b'\r\n', b'\n'))
        self.assertEqual(result['valid_rows'][0]['values'], ROW)

    def test_empty_bom_only_and_header_only_fail_explicitly(self):
        for content, code in [(b'', 'EMPTY_FILE'), (b'\xef\xbb\xbf', 'EMPTY_FILE'),
                              (csv_bytes([]), 'NO_DATA')]:
            with self.subTest(code=code):
                self.assert_file_error(validate(content), code)

    def assert_file_error(self, result, code):
        self.assertEqual(result['status'], 'INVALID')
        self.assertEqual(result['errors'], [{'row': None, 'field': '__file__', 'code': code}])
        self.assertIsNone(result['row_count'])
        self.assertIsNone(result['invalid_count'])
        self.assertEqual(result['valid_count'], 0)
        self.assertEqual(result['valid_rows'], [])

    def test_invalid_encoding_and_delimiter_are_not_guessed(self):
        self.assert_file_error(validate(b'\xff\xfeID'), 'INVALID_UTF8')
        result = validate(csv_bytes().replace(b',', b';'))
        self.assertEqual(result['status'], 'INVALID')
        self.assertIn('HEADER_UNKNOWN', [e['code'] for e in result['errors']])
        self.assertEqual(result['valid_rows'], [])

    def test_missing_extra_duplicate_and_nonexact_headers_fail(self):
        for columns, expected in [(COLUMNS[:-1], 'HEADER_MISSING'),
                (COLUMNS + ('approved_by',), 'HEADER_UNKNOWN'),
                (COLUMNS + ('aicte_id',), 'HEADER_DUPLICATE'),
                (('AICTE_ID',) + COLUMNS[1:], 'HEADER_UNKNOWN'),
                ((' aicte_id',) + COLUMNS[1:], 'HEADER_UNKNOWN')]:
            with self.subTest(columns=columns):
                result = validate(csv_bytes([], columns))
                self.assertIn(expected, [e['code'] for e in result['errors']])
                self.assertEqual(result['valid_rows'], [])
                self.assertIsNone(result['row_count'])

    def test_required_fields_never_receive_defaults(self):
        for field in COLUMNS:
            with self.subTest(field=field):
                result = validate(csv_bytes([ROW | {field: '   '}]))
                self.assertEqual(result['errors'], [{'row': 2, 'field': field, 'code': 'REQUIRED'}])
                self.assertEqual(result['valid_rows'], [])

    def test_wrong_width_and_blank_records_are_row_errors(self):
        result = validate(csv_bytes([list(ROW.values())[:-1], [], list(ROW.values()) + ['extra'], ROW]))
        self.assertEqual(result['row_count'], 4)
        self.assertEqual(result['invalid_count'], 3)
        self.assertEqual([r['row'] for r in result['valid_rows']], [5])
        self.assertEqual(result['errors'], [
            {'row':2, 'field':'__row__', 'code':'COLUMN_COUNT'},
            {'row':3, 'field':'__row__', 'code':'EMPTY_ROW'},
            {'row':4, 'field':'__row__', 'code':'COLUMN_COUNT'}])

    def test_all_formula_prefixes_rejected_in_every_column(self):
        for field in COLUMNS:
            for prefix in '=+-@':
                with self.subTest(field=field, prefix=prefix):
                    result = validate(csv_bytes([ROW | {field: '  ' + prefix + '1'}]))
                    self.assertIn({'row':2, 'field':field, 'code':'FORMULA_PREFIX'}, result['errors'])

    def test_hidden_controls_bidi_and_quoted_newlines_are_rejected_before_trim(self):
        for value in ['\tSynthetic', 'Synthetic\x00', 'Synthetic\u202e',
                      'Synthetic\u200b', 'Synthetic\nInstitute', 'Synthetic\rInstitute']:
            with self.subTest(value=repr(value)):
                result = validate(csv_bytes([ROW | {'institution_name':value}]))
                self.assertEqual(result['row_count'], 1)
                self.assertEqual(result['errors'], [{'row':2, 'field':'institution_name', 'code':'CONTROL_CHARACTER'}])

    def test_text_field_length_boundaries_match_existing_models(self):
        from obligations.models import InstitutionProfile
        from portal.models import Institution
        mapping = {'aicte_id': (InstitutionProfile, 'aicte_id'),
            'institution_code': (Institution, 'code'), 'institution_name': (Institution, 'name'),
            **{key: (InstitutionProfile, key) for key in [
                'trust_name', 'institution_type', 'region', 'state', 'contact_email', 'status']}}
        for field, (model, name) in mapping.items():
            self.assertEqual(LIMITS[field], model._meta.get_field(name).max_length)
        for field in ['aicte_id', 'institution_code', 'institution_name', 'trust_name', 'region', 'state']:
            for excess in [0, 1]:
                with self.subTest(field=field, excess=excess):
                    result = validate(csv_bytes([ROW | {field: 'A' * (LIMITS[field] + excess)}]))
                    self.assertEqual(result['errors'], [] if excess == 0 else [
                        {'row':2, 'field':field, 'code':'TOO_LONG'}])

    def test_invalid_email_enum_tokens_and_label_are_precise(self):
        for field, value, code in [
            ('contact_email', 'not-an-email', 'INVALID_EMAIL'),
            ('institution_type', 'private', 'INVALID_CHOICE'),
            ('status', 'ACCEPTED', 'INVALID_CHOICE'),
            ('aicte_id', 'SYNTH ID', 'INVALID_TOKEN'),
            ('institution_code', 'SYNTH/01', 'INVALID_TOKEN'),
            ('data_classification', 'REAL', 'NOT_SIMULATED')]:
            with self.subTest(field=field):
                result = validate(csv_bytes([ROW | {field: value}]))
                self.assertEqual(result['errors'], [{'row':2, 'field':field, 'code':code}])

    def test_all_model_type_and_status_choices_are_supported_without_exemption(self):
        for institution_type in ['PRIVATE', 'GOVERNMENT', 'AIDED', 'UNIVERSITY']:
            for status in ['ACTIVE', 'INACTIVE']:
                result = validate(csv_bytes([ROW | {'institution_type':institution_type, 'status':status}]))
                self.assertEqual(result['status'], 'VALID')
                self.assertEqual(set(result['valid_rows'][0]['values']), set(COLUMNS))
                self.assertNotIn('exemption', result['valid_rows'][0]['values'])

    def test_both_sides_of_duplicates_are_rejected_even_if_one_row_has_other_errors(self):
        for field in ['aicte_id', 'institution_code']:
            second = ROW | {'aicte_id':'SYNTH-02', 'institution_code':'SYNTH-02', 'contact_email':'invalid'}
            second[field] = '  ' + ROW[field].lower() + '  '
            result = validate(csv_bytes([ROW, second]))
            self.assertEqual(result['valid_count'], 0)
            self.assertEqual([e['row'] for e in result['errors'] if e['code'] == 'DUPLICATE_IDENTITY'], [2,3])

    def test_existing_identity_and_legacy_conflicts_do_not_become_updates(self):
        for existing, field in [((ExistingIdentity(' synth-01 ', 'OTHER'),), 'aicte_id'),
                                ((ExistingIdentity(None, ' synth-01 '),), 'institution_code')]:
            result = validate(existing=existing)
            self.assertEqual(result['errors'], [{'row':2, 'field':field, 'code':'EXISTING_IDENTITY'}])
            self.assertEqual(result['valid_rows'], [])

    def test_snapshot_and_byte_contract_fail_before_any_lazy_iteration(self):
        class LazyContext:
            def __iter__(self):
                raise AssertionError('Lazy context must not be evaluated')
        for context in [None, [], LazyContext(), (ROW,), (ExistingIdentity('', 'CODE'),),
                        (ExistingIdentity(None, ''),), (ExistingIdentity(None, '\tCODE'),)]:
            with self.subTest(context=type(context).__name__), self.assertRaises(CsvInputError):
                validate(existing=context)
        for content in ['text', bytearray(b'CSV'), 3]:
            with self.subTest(content=type(content).__name__), self.assertRaises(CsvInputError):
                validate_institution_csv(content, existing_identities=())
        with self.assertRaises(TypeError):
            validate_institution_csv(csv_bytes())

    def test_row_limit_is_inclusive_and_excess_discards_all_candidates(self):
        rows = [ROW | {'aicte_id':f'SYNTH-{i}', 'institution_code':f'SYNTH-{i}'} for i in range(MAX_ROWS + 1)]
        result = validate(csv_bytes(rows[:MAX_ROWS]))
        self.assertEqual(result['valid_count'], MAX_ROWS)
        self.assertEqual(result['status'], 'VALID')
        self.assert_file_error(validate(csv_bytes(rows)), 'ROW_LIMIT')

    def test_byte_limit_is_inclusive_and_checked_before_decoding(self):
        at_limit = csv_bytes()
        at_limit += b' ' * (MAX_BYTES - len(at_limit))
        self.assertNotIn('FILE_TOO_LARGE', [e['code'] for e in validate(at_limit)['errors']])
        self.assert_file_error(validate(at_limit + b'\xff'), 'FILE_TOO_LARGE')

    def test_malformed_late_row_discards_valid_prefix(self):
        self.assert_file_error(validate(csv_bytes() + b'"unterminated'), 'CSV_SYNTAX')

    def test_repeated_calls_outputs_and_inputs_are_detached(self):
        context = (ExistingIdentity(None, 'UNRELATED'),)
        original = deepcopy(context)
        content = csv_bytes()
        first = validate(content, existing=context)
        second = validate(content, existing=context)
        self.assertEqual(first, second)
        first['valid_rows'][0]['values']['institution_name'] = 'Changed'
        first['errors'].append({'bad':'value'})
        self.assertEqual(validate(content, existing=context), second)
        self.assertEqual(context, original)

    def test_errors_do_not_echo_rejected_values_or_existing_names(self):
        secret = 'not-an-email-SYNTHETIC-REJECTED-VALUE'
        result = validate(csv_bytes([ROW | {'contact_email':secret}]))
        self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(result['errors'], [{'row':2, 'field':'contact_email', 'code':'INVALID_EMAIL'}])

    def test_standalone_validator_does_not_configure_django_or_import_models(self):
        env = os.environ.copy()
        env.pop('DJANGO_SETTINGS_MODULE', None)
        script = (
            'from pathlib import Path; import sys; from django.conf import settings; '
            'from obligations.csv_validation import validate_institution_csv; '
            "r=validate_institution_csv(Path('evaluation/s4/invalid-fields.csv').read_bytes(),existing_identities=()); "
            "assert r['invalid_count']==7; assert not settings.configured; "
            "assert 'django.db' not in sys.modules; assert 'obligations.models' not in sys.modules; "
            "print('pure validation passed')")
        result = subprocess.run([sys.executable, '-c', script], env=env,
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'pure validation passed')
