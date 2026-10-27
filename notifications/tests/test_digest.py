"""Synthetic digest preparation only: no email, ORM queries or scheduler."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from notifications.digest import build_digest, business_window, DigestInputError

ROOT = Path(__file__).resolve().parents[2]


class WeeklyDigestTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dataset = json.loads((ROOT/'docs/digests/scenarios.json').read_text())
        cls.base = cls.dataset['cases'][0]

    def build(self, case=None, origin='https://portal.example.invalid'):
        case = case or self.base
        return build_digest(case['recipient'], case['facts'], as_of=case['as_of'], portal_base_url=origin)

    def case(self, identity):
        return deepcopy(next(case for case in self.dataset['cases'] if case['id'] == identity))

    def test_labelled_scenarios(self):
        self.assertTrue(self.dataset['synthetic_only'])
        for case in self.dataset['cases']:
            with self.subTest(case=case['id']):
                result = self.build(case)
                values = {row['code']: row['value'] for row in result['metrics']}
                self.assertEqual(values, case['expected'])
                self.assertEqual(result['delivery_state'], 'PREVIEW_ONLY')
                self.assertIn('SIMULATED', result['body'])

    def test_foreign_institution_is_refused_even_if_it_would_not_change_count(self):
        case = deepcopy(self.base)
        case['facts']['deposits'][0]['institution_id'] = 999
        with self.assertRaises(DigestInputError):
            self.build(case)

    def test_clearance_cannot_count_another_unit(self):
        case = self.case('clearance_unit_only')
        case['facts']['clearances'][0]['unit'] = 'VIGILANCE'
        with self.assertRaises(DigestInputError):
            self.build(case)

    def test_each_role_gets_only_its_own_minimal_source_contract(self):
        case = deepcopy(self.base)
        case['facts']['audit_alerts'] = []
        with self.assertRaises(DigestInputError):
            self.build(case)

    def test_active_recipient_and_explicit_optin_and_email_are_required(self):
        for field, reason in [('active','INACTIVE'),('digest_enabled','OPTED_OUT'),('email_available','NO_EMAIL')]:
            case = deepcopy(self.base); case['recipient'][field] = False
            self.assertEqual(self.build(case)['reason'], reason)
        for roles, reason in [([], 'NO_VALID_ROLE'), (['unknown'],'NO_VALID_ROLE'),
                              (['officer','authority'],'AMBIGUOUS_ROLE')]:
            case = deepcopy(self.base); case['recipient']['roles'] = roles
            self.assertEqual(self.build(case)['reason'], reason)

    def test_ist_monday_boundary_and_equivalent_utc_instant(self):
        ist = business_window('2026-10-26T00:00:00+05:30')
        utc = business_window('2026-10-25T18:30:00+00:00')
        self.assertEqual(ist, utc)
        self.assertEqual(ist['previous_start'].isoformat(), '2026-10-19T00:00:00+05:30')
        self.assertEqual(ist['previous_end'].isoformat(), '2026-10-26T00:00:00+05:30')
        sunday = business_window('2026-10-25T23:59:59+05:30')
        self.assertEqual(sunday['week_start'].date().isoformat(), '2026-10-19')

    def test_naive_and_invalid_dates_are_refused(self):
        for value in ['2026-10-26T09:00:00', datetime(2026,10,26), 'not-a-date']:
            with self.assertRaises(DigestInputError):
                business_window(value)
        case = deepcopy(self.base); case['facts']['deposits'][0]['maturity_date'] = '2026-02-30'
        with self.assertRaises(DigestInputError):
            self.build(case)

    def test_month_leap_and_year_boundaries(self):
        for as_of, dates, expected in [
                ('2024-02-26T09:00:00+05:30',['2024-02-25','2024-02-29','2024-03-01'],1),
                ('2026-12-28T09:00:00+05:30',['2026-12-28','2026-12-31','2027-01-01'],2),
                ('2027-01-04T09:00:00+05:30',['2026-12-31','2027-01-05','2027-02-01'],1)]:
            case = deepcopy(self.base); case['as_of'] = as_of
            sample = case['facts']['deposits'][0]
            case['facts']['deposits'] = [sample|{'id':i+1,'maturity_date':day} for i,day in enumerate(dates)]
            self.assertEqual(self.build(case)['metrics'][0]['value'],expected)

    def test_released_superseded_and_unaccepted_deposits_do_not_count(self):
        case = deepcopy(self.base)
        sample = case['facts']['deposits'][0]
        case['facts']['deposits'] = [sample|{'released':True},sample|{'id':10,'superseded':True},
                                    sample|{'id':11,'status':'DRAFT'}]
        self.assertEqual(self.build(case)['metrics'][0]['value'],0)

    def test_previous_week_is_half_open_and_incomplete_history_is_unknown(self):
        case = self.case('officer_work_and_duration')
        sample = case['facts']['reviews'][0]
        case['facts']['reviews'] = [sample|{'submitted_at':'2026-10-18T00:00:00+05:30',
            'accepted_at':'2026-10-19T00:00:00+05:30'}, sample|{'id':2,
            'submitted_at':'2026-10-25T00:00:00+05:30','accepted_at':'2026-10-26T00:00:00+05:30'}]
        metric = self.build(case)['metrics'][2]
        self.assertEqual((metric['sample_count'],metric['value']),(1,'1.0'))
        case['facts']['reviews'][0]['history_complete'] = False
        self.assertIsNone(self.build(case)['metrics'][2]['value'])

    def test_negative_and_future_review_times_are_refused(self):
        for timestamp in ['2026-10-01T00:00:00+05:30','2026-10-27T00:00:00+05:30']:
            case = self.case('officer_work_and_duration')
            case['facts']['reviews'][0]['accepted_at'] = timestamp
            with self.assertRaises(DigestInputError):
                self.build(case)

    def test_missing_escalation_source_is_unknown_not_inferred_from_pending_cases(self):
        case = self.case('authority_escalation_source_unavailable')
        self.assertFalse(self.build(case)['metrics'][1]['available'])

    def test_duplicate_records_and_malformed_boolean_are_refused(self):
        case = deepcopy(self.base); case['facts']['deposits'].append(case['facts']['deposits'][0])
        with self.assertRaises(DigestInputError):
            self.build(case)
        case = deepcopy(self.base); case['facts']['observations'][0]['resolved'] = 1
        with self.assertRaises(DigestInputError):
            self.build(case)

    def test_role_scope_and_source_placeholders_do_not_silently_expand(self):
        case = deepcopy(self.base); case['recipient']['scope_institution_ids'] = [1,2]
        with self.assertRaises(DigestInputError):
            self.build(case)
        case = deepcopy(self.base); case['facts']['deposits'][0]['private_token'] = 'DO-NOT-INCLUDE'
        with self.assertRaises(DigestInputError):
            self.build(case)

    def test_snapshot_is_not_mutated_and_builder_never_sends_mail(self):
        saved = deepcopy(self.base)
        with patch('django.core.mail.send_mail', side_effect=AssertionError('Must not send')):
            self.build(saved)
        self.assertEqual(saved,self.base)

    def test_same_week_and_retry_keep_key_but_next_week_and_user_change_it(self):
        case = deepcopy(self.base); original = self.build(case)['idempotency_key']
        case['as_of'] = '2026-10-27T12:00:00+05:30'
        self.assertEqual(self.build(case)['idempotency_key'],original)
        case['as_of'] = '2026-11-02T09:00:00+05:30'
        self.assertNotEqual(self.build(case)['idempotency_key'],original)
        case = deepcopy(self.base); case['recipient']['id'] = 2
        self.assertNotEqual(self.build(case)['idempotency_key'],original)
        self.assertLess(len(original),200)

    def test_links_are_configured_origin_only_with_no_redirect_or_injection(self):
        for origin in ['http://example.org','https://example.org/redirect?next=https://evil.invalid',
                'https://user:password@example.org','https://example.org/#fragment',
                'javascript:alert(1)','https://example.org/" onclick="alert(1)']:
            with self.subTest(origin=origin), self.assertRaises(DigestInputError):
                self.build(origin=origin)
        result = self.build(origin='http://127.0.0.1:8011')
        self.assertEqual(result['portal_link'],'http://127.0.0.1:8011/records')
        self.assertIn('href="http://127.0.0.1:8011/records"',result['html'])
        self.assertNotIn('<script',result['html'])

    def test_only_explicit_synthetic_snapshots_are_supported_in_first_slice(self):
        case = deepcopy(self.base); case['facts']['simulation_label'] = 'REAL'
        with self.assertRaises(DigestInputError):
            self.build(case)
