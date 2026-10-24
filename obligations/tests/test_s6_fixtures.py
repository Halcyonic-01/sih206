"""S6 preparation consistency; not API authorization or browser acceptance."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.db import connections
from django.test import SimpleTestCase

from docs.s6.validate_fixtures import (FIXTURES, MAX_BYTES, FixtureError,
    load, main, validate)


class S6FixtureTests(SimpleTestCase):
    def setUp(self):
        self.raw = FIXTURES.read_bytes()
        self.dataset = json.loads(self.raw)

    def scenario(self, sid):
        return next(s for s in self.dataset['private_scenarios'] +
                    self.dataset['public_scenarios'] if s['id'] == sid)

    def reject(self, sid, section, key, value):
        self.dataset = json.loads(self.raw)
        target = self.scenario(sid)
        (target[section] if section else target)[key] = value
        with self.assertRaises(FixtureError):
            validate(self.dataset)

    def test_original_53_without_queries_or_input_mutation(self):
        before = deepcopy(self.dataset)
        source = FIXTURES.parent.parent / 's5' / 'scenarios.json'
        source_before = source.read_bytes()
        self.assertEqual(validate(self.dataset), {
            'result': 'passed', 'scenarios': 53, 'private_scenarios': 48,
            'public_scenarios': 5, 's5_comparisons': 33, 'database_queries': 0})
        self.assertEqual(self.dataset, before)
        self.assertEqual(FIXTURES.read_bytes(), self.raw)
        self.assertEqual(source.read_bytes(), source_before)

    def test_missing_duplicate_renamed_and_swapped_scenarios(self):
        for change in ['missing', 'duplicate', 'renamed', 'swapped']:
            self.dataset = json.loads(self.raw)
            rows = self.dataset['private_scenarios']
            if change == 'missing':
                rows.pop()
            elif change == 'duplicate':
                rows[-1] = deepcopy(rows[0])
            elif change == 'renamed':
                rows[0]['id'] = 'unknown'
            else:
                rows[0]['screen'] = 'public_verify'
            with self.subTest(change=change), self.assertRaises(FixtureError):
                validate(self.dataset)

    def test_required_labels_and_context_cannot_be_removed(self):
        for key, value in [('simulation_label', 'LIVE'), ('data_classification', 'REAL'),
                ('rule_status', 'APPROVED'), ('assessment_date', '2026-10-25'),
                ('artifact_status', 'IMPLEMENTED'), ('all_examples_require', [])]:
            d = json.loads(self.raw)
            d[key] = value
            with self.subTest(key=key), self.assertRaises(FixtureError):
                validate(d)

    def test_wrong_lineage_operation_and_replaced_linked_state(self):
        for section, key, value in [('condition', 's5_ref', 'S5-02'),
                ('condition', 'operation', 'COMPLETE'), ('', 'state', 'ready')]:
            with self.subTest(key=key):
                self.reject('case-ready', section, key, value)

    def test_scope_and_actor_tampering_is_rejected(self):
        for sid, key, value in [('case-ready', 'scope_institution_ids', [999]),
                ('case-requester-authority', 'id', 3001),
                ('queue-open', 'scope_unit', 'VIGILANCE'),
                ('wizard-review-request', 'scope_institution_ids', [202])]:
            with self.subTest(sid=sid):
                self.reject(sid, 'actor', key, value)

    def test_wrong_outcome_or_missing_reasons_is_rejected(self):
        for sid, key, value in [('case-clearance-open', 's5_outcome', 'READY_FOR_AUTHORITY_REVIEW'),
                ('case-penalty-unavailable', 's5_reason_codes', []),
                ('case-ready', 's5_reason_codes', ['CLEARANCE_OPEN'])]:
            with self.subTest(sid=sid):
                self.reject(sid, 'expected', key, value)

    def test_projections_cannot_replace_saved_status_or_monitoring(self):
        for sid, key, value in [('case-complete-projection', 'persisted_case_status', 'COMPLETED'),
                ('case-complete-projection', 'persisted_monitoring_active', False),
                ('case-approve-projection', 'persisted_case_status', 'APPROVED'),
                ('case-reject-projection', 'persisted_case_status', 'REJECTED'),
                ('case-ready', 'persisted_version', True)]:
            with self.subTest(sid=sid, key=key):
                self.reject(sid, 'view_data', key, value)

    def test_denied_and_transient_states_cannot_disclose_cached_data(self):
        for sid in ['case-evidence-denied', 'wizard-cross-scope', 'case-requester-authority',
                'case-loading', 'case-service-unavailable', 'case-session-expired',
                'case-response-race', 'queue-denied', 'queue-stale', 'public-loading',
                'public-service-failed', 'public-not-found']:
            with self.subTest(sid=sid):
                self.reject(sid, '', 'view_data', {'institution_name': 'Leaked record'})

    def test_unknown_template_preview_upload_and_page_facts_remain_honest(self):
        for sid, key, value in [('wizard-template-unavailable', 'template_available', True),
                ('wizard-review-request', 'penalty_review', []),
                ('wizard-path-changed', 'preview_valid', True),
                ('wizard-upload-invalid', 'upload_accepted', True),
                ('case-viewer-failed', 'page_count', 1),
                ('case-legacy', 'persisted_monitoring_active', False)]:
            with self.subTest(sid=sid):
                self.reject(sid, 'view_data', key, value)

    def test_missing_prohibitions_checks_and_added_action_grants(self):
        for sid, section, key, value in [
                ('case-ready', 'expected', 'checks', []),
                ('case-requester-authority', 'expected', 'prohibited_controls', ['complete']),
                ('case-ready', '', 'actions', {'can_approve': True}),
                ('queue-open', 'view_data', 'actions', {'can_decide': True})]:
            with self.subTest(sid=sid, key=key):
                self.reject(sid, section, key, value)

    def test_queue_scope_status_date_and_empty_are_checked(self):
        for key, value in [('unit', 'PGRC'), ('tasks', None), ('tasks', [])]:
            with self.subTest(key=key):
                self.reject('queue-open', 'view_data', key, value)
        self.dataset = json.loads(self.raw)
        self.scenario('queue-open')['view_data']['tasks'][0]['due_date'] = 'invalid'
        with self.assertRaises(FixtureError):
            validate(self.dataset)

    def test_public_allowlist_cannot_be_widened_or_leaked(self):
        for field in ['amount_paise', 'actor', 'monitoring_after_action', 'assessment_context',
                'private_pdf_url', 'refund_reference', 'token']:
            with self.subTest(field=field):
                self.reject('public-issued', 'view_data', field, 'private')
        self.dataset = json.loads(self.raw)
        self.dataset['public_record_allowlist'].append('amount_paise')
        with self.assertRaises(FixtureError):
            validate(self.dataset)
        self.reject('public-issued', '', 'actor', {'id': 3001})

    def test_revocation_and_public_failure_cannot_be_success(self):
        for sid, section, key, value in [('public-revoked', 'view_data', 'status', 'ISSUED'),
                ('public-revoked', 'expected', 'heading', 'Valid NOC'),
                ('public-service-failed', '', 'state', 'NOT_FOUND'),
                ('public-revoked', '', 's5_lineage_ref', 'S5-01')]:
            with self.subTest(sid=sid, key=key):
                self.reject(sid, section, key, value)

    def test_malformed_shapes_and_non_plain_values_are_controlled(self):
        for value in [None, [], {'unexpected': True}]:
            with self.subTest(value=value), self.assertRaises(FixtureError):
                validate(value)
        for value in [1.5, object(), 2**54]:
            self.dataset = json.loads(self.raw)
            self.dataset['usage'] = value
            with self.subTest(value=type(value)), self.assertRaises(FixtureError):
                validate(self.dataset)
        self.dataset = json.loads(self.raw)
        self.dataset['usage'] = self.dataset
        with self.assertRaises(FixtureError):
            validate(self.dataset)
        self.reject('case-ready', '', 'expected', None)

    def test_loader_rejects_invalid_utf8_duplicate_keys_nonfinite_and_large_files(self):
        with TemporaryDirectory() as folder:
            candidate = Path(folder) / 'candidate.json'
            for raw in [b'{', b'\xff', b'{"x":1,"x":2}', b'{"x":NaN}', b' ' * (MAX_BYTES + 1)]:
                candidate.write_bytes(raw)
                with self.subTest(raw=raw[:24]), self.assertRaises(FixtureError):
                    load(candidate)

    def test_cli_success_failure_and_redacted_error(self):
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(out.getvalue())['s5_comparisons'], 33)
        with patch('docs.s6.validate_fixtures.load', side_effect=OSError('SECRET')), \
                redirect_stderr(StringIO()) as err:
            self.assertEqual(main(['--fixtures', 'missing']), 1)
        self.assertIn('S6 fixture validation failed', err.getvalue())
        self.assertNotIn('SECRET', err.getvalue())

    def test_cli_from_other_directory_and_optimized_python(self):
        script = FIXTURES.with_name('validate_fixtures.py')
        with TemporaryDirectory() as folder:
            ok = subprocess.run([sys.executable, '-O', str(script)], cwd=folder,
                capture_output=True, text=True, timeout=30)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            candidate = Path(folder) / 'bad.json'
            self.scenario('case-complete-projection')['view_data']['persisted_monitoring_active'] = False
            candidate.write_text(json.dumps(self.dataset), encoding='utf-8')
            bad = subprocess.run([sys.executable, '-O', str(script), '--fixtures', str(candidate)],
                cwd=folder, capture_output=True, text=True, timeout=30)
            self.assertEqual(bad.returncode, 1)
            self.assertIn('validation failed', bad.stderr)

    def test_query_rejection_wrapper_is_installed_and_removed(self):
        connection = connections['default']
        before = list(connection.execute_wrappers)

        def try_query(_):
            # Exercise the installed guard directly without opening a connection.
            return connection.execute_wrappers[-1](lambda *a: None, 'SELECT 1', (), False, {})

        with patch('docs.s6.validate_fixtures._validate', side_effect=try_query), \
                self.assertRaisesMessage(FixtureError, 'Database access forbidden'):
            validate(self.dataset)
        self.assertEqual(connection.execute_wrappers, before)
