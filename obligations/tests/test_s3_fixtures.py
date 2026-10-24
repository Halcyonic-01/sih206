"""Preparation checks only: these do not test an implemented S3 UI or API."""
from contextlib import redirect_stderr
from copy import deepcopy
from io import StringIO
import json
from unittest.mock import patch

from django.test import SimpleTestCase

from docs.s3.validate_fixtures import FIXTURES, FixtureError, main, validate


class S3FixtureTests(SimpleTestCase):
    def setUp(self):
        self.original = FIXTURES.read_bytes()
        self.dataset = json.loads(self.original)

    def scenario(self, identifier):
        return next(s for s in self.dataset['scenarios'] if s['id'] == identifier)

    def test_all_scenarios_without_database_access_or_fixture_mutation(self):
        self.assertEqual(validate(self.dataset), {
            'scenarios': 19, 'calculation_cases': 7, 'expected_rejections': 1,
            'database_queries': 0, 'result': 'passed'})
        self.assertEqual(FIXTURES.read_bytes(), self.original)

    def test_missing_duplicate_scenarios_and_lineage_are_rejected(self):
        for change in ['missing', 'duplicate', 'lineage']:
            self.dataset = json.loads(self.original)
            if change == 'missing':
                self.dataset['scenarios'].pop()
            elif change == 'duplicate':
                self.dataset['scenarios'][-1] = deepcopy(self.dataset['scenarios'][0])
            else:
                self.scenario('detail-covered')['s2_lineage'] = ['does-not-exist']
            with self.subTest(change=change), self.assertRaises(FixtureError):
                validate(self.dataset)

    def test_wrong_coverage_and_display_money_are_rejected(self):
        for path, key, value in [('coverage', 'shortfall_paise', 0),
                                 ('coverage', 'held_paise', True),
                                 ('expected_display', 'held_display', 'INR 0.00')]:
            self.dataset = json.loads(self.original)
            s = self.scenario('detail-shortfall')
            (s if path == 'expected_display' else s['screen_data'])[path][key] = value
            with self.subTest(key=key), self.assertRaises(FixtureError):
                validate(self.dataset)

    def test_list_and_detail_scope_leaks_are_rejected(self):
        for sid in ['list-own', 'detail-covered']:
            self.dataset = json.loads(self.original)
            self.scenario(sid)['actor']['institution_id'] = 202
            with self.subTest(sid=sid), self.assertRaises(FixtureError):
                validate(self.dataset)

    def test_access_errors_cannot_contain_protected_data(self):
        for sid in ['detail-not-found', 'detail-forbidden']:
            self.dataset = json.loads(self.original)
            self.scenario(sid)['screen_data'] = {'institution_ref': 'inst-a'}
            with self.subTest(sid=sid), self.assertRaises(FixtureError):
                validate(self.dataset)

    def test_unknown_and_unavailable_must_not_become_zero(self):
        for sid in ['detail-unknown', 'detail-adapter-unavailable']:
            self.dataset = json.loads(self.original)
            self.scenario(sid)['screen_data']['coverage']['shortfall_paise'] = 0
            with self.subTest(sid=sid), self.assertRaises(FixtureError):
                validate(self.dataset)

    def test_findings_deadlines_and_rule_fingerprint_are_checked(self):
        for change in ['findings', 'deadline', 'fingerprint']:
            self.dataset = json.loads(self.original)
            s = self.scenario('detail-proof-overdue')['screen_data']
            if change == 'findings':
                s['finding_codes'] = []
            elif change == 'deadline':
                s['next_action']['due_date'] = '2026-04-15'
            else:
                self.dataset['rule']['sha256'] = '0' * 64
            with self.subTest(change=change), self.assertRaises(FixtureError):
                validate(self.dataset)

    def test_invalid_calculator_case_must_really_be_rejected(self):
        s = self.scenario('calculator-invalid')
        for inputs in [s['calculation_inputs']['approvals'], s['screen_data']['draft_approvals']]:
            inputs[0]['level'] = 'PG'
        with self.assertRaisesMessage(FixtureError, 'expected rejection did not occur'):
            validate(self.dataset)

    def test_stale_preview_and_wrong_multiplier_are_rejected(self):
        for sid in ['calculator-conflict', 'calculator-preview']:
            self.dataset = json.loads(self.original)
            if sid == 'calculator-conflict':
                self.scenario(sid)['screen_data']['preview'] = {'required_paise': 1}
            else:
                self.scenario(sid)['screen_data']['preview']['multiplier'] = 4
            with self.subTest(sid=sid), self.assertRaises(FixtureError):
                validate(self.dataset)

    def test_cli_fails_nonzero_for_invalid_json(self):
        with patch('sys.argv', ['validate_fixtures.py']), \
                patch.object(type(FIXTURES), 'read_text', return_value='{'), \
                redirect_stderr(StringIO()) as error:
            self.assertEqual(main(), 1)
        self.assertIn('S3 fixture validation failed', error.getvalue())
