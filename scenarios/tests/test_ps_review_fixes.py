"""PS scenarios 3, 6, 7 and 9 through the real API, settings and seed v2 (fixes found in the 25 Oct review check)."""
from datetime import date, timedelta
from io import StringIO
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from access.models import UnitAssignment
from access.tests.base import StaffTestCase
from audit.chain import verify_chain
from casework.adapters import AFFIDAVIT_6
from obligations.catalogue import draft_payload
from obligations.models import DepositObligation, IssuedLetter, RuleSet
from obligations.reports import kpi_report
from portal.models import Instrument
from portal.permissions import CLEARANCE_GROUP
from portal.tests.common import sample_pdf
from verification.services import import_statement


def answers(value=True):
    return {question['id']: value for question in AFFIDAVIT_6['questions']}


@override_settings(ROOT_URLCONF='config.urls', PORTAL_BASE_URL='https://portal.example', SAKSHAM_PUBLIC_BASE_URL='https://portal.example')
class ReleaseCaseEndToEnd(StaffTestCase):
    """PS 7 with the configured (not test-injected) release adapters: wizard -> clearances -> penalty -> decision -> NOC."""

    def setUp(self):
        super().setUp()
        self.grants = get_user_model().objects.create_user(username='clearance_grants')
        self.grants.groups.add(Group.objects.get(name=CLEARANCE_GROUP))
        UnitAssignment.objects.create(user=self.grants, unit=UnitAssignment.Unit.GRANTS)
        rule = RuleSet.objects.create(code='ps7-draft', version=1, effective_from=date(2016, 1, 1), payload=draft_payload(),
                                      source_document='Synthetic', source_clause='6.46')
        self.obligation = DepositObligation.objects.create(institution=self.institution_a, rule_version=rule,
            required_paise=150000000, term_start=date(2016, 1, 1), term_end=timezone.localdate() - timedelta(days=1))
        record = self.submitted()
        Instrument.objects.filter(pk=record.pk).update(obligation=self.obligation)
        self.client.force_login(self.officer)
        response = self.client.post(f'/api/instruments/{record.pk}/review/', {'version': record.version,
            'decision': 'accept', 'reason': 'Reviewed for tracking'}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.record = Instrument.objects.get(pk=record.pk)

    def as_user(self, user):
        self.client.force_login(user)
        return self.client

    def upload(self, kind, user=None):
        self.record.refresh_from_db()
        return self.as_user(user or self.a).post(f'/api/instruments/{self.record.pk}/documents/', {
            'version': self.record.version, 'kind': kind,
            'document': SimpleUploadedFile(f'{kind.lower()}.pdf', sample_pdf(), content_type='application/pdf')})

    def requirements(self, user=None, path='TERM_COMPLETE'):
        return self.as_user(user or self.a).get('/api/releases/requirements', {
            'instrument': self.record.pk, 'obligation': self.obligation.pk, 'path': path})

    def case(self, pk, user):
        response = self.as_user(user).get(f'/api/releases/{pk}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def act(self, user, path, payload, status=200):
        response = self.as_user(user).post(path, payload, content_type='application/json')
        self.assertEqual(response.status_code, status, response.content)
        return response.json()

    def test_full_release_with_real_adapters(self):
        detail = self.as_user(self.a).get(f'/api/instruments/{self.record.pk}/').json()
        self.assertTrue(detail['actions']['can_upload_release_documents'])
        self.assertTrue(detail['actions']['can_request_release'])
        self.assertFalse(self.requirements().json()['documents_ready'])
        for kind in ('REQUEST_LETTER', 'AFFIDAVIT_6', 'APPROVAL_LETTER'):
            self.assertEqual(self.upload(kind).status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, 'ACCEPTED')  # evidence added; deposit facts and status unchanged
        ready = self.requirements().json()
        self.assertTrue(ready['documents_ready'] and ready['eligible'] and ready['term_elapsed'])
        self.assertEqual(ready['questionnaire']['version'], AFFIDAVIT_6['version'])

        created = self.act(self.a, '/api/releases', {'instrument_id': self.record.pk, 'obligation_id': self.obligation.pk,
            'instrument_version': ready['instrument_version'], 'path': 'TERM_COMPLETE', 'declarations': answers(),
            'reason': 'Ten-year term complete', 'template_ref': AFFIDAVIT_6['version']}, 201)
        pk = created['id']
        self.assertEqual(created['status'], 'PENDING')
        self.assertEqual({t['unit'] for t in created['clearances']}, {'PGRC', 'VIGILANCE', 'GRANTS'})
        self.assertEqual(self.as_user(self.a).get(f'/api/instruments/{self.record.pk}/').json()['release_case_id'], pk)
        # Each task has an SLA due date and is visible to the scheduler's clearance SLA rule (K6).
        from notifications.rules import open_clearance_tasks
        tasks = open_clearance_tasks(timezone.localdate())
        self.assertEqual({(t['unit'], t['case_id']) for t in tasks}, {('PGRC', pk), ('VIGILANCE', pk), ('GRANTS', pk)})
        self.assertTrue(all(task['due_date'] for task in self.as_user(self.pgrc).get('/api/clearance-tasks').json()['results']))

        # The authority cannot decide while clearances are open; a stale clearance version is a conflict.
        self.assertFalse(self.case(pk, self.authority)['actions']['can_approve'])
        self.act(self.pgrc, f'/api/releases/{pk}/clearances/PGRC', {'version': 999, 'status': 'CLEARED',
                 'reason': 'Stale', 'evidence_ref': 'PGRC/2026/17'}, 409)
        self.act(self.pgrc, f'/api/releases/{pk}/clearances/PGRC', {'version': created['version'], 'status': 'CLEARED',
                 'reason': 'No grievance', 'evidence_ref': '!'}, 503)  # evidence reference must be a file number
        for user, unit in ((self.pgrc, 'PGRC'), (self.vigilance, 'VIGILANCE'), (self.grants, 'GRANTS')):
            version = self.case(pk, user)['version']
            self.act(user, f'/api/releases/{pk}/clearances/{unit}', {'version': version, 'status': 'CLEARED',
                     'reason': f'{unit} has no objection', 'evidence_ref': f'{unit}/2026/17'})
        self.assertFalse(self.case(pk, self.authority)['actions']['can_approve'])  # officer review still pending
        self.assertEqual(open_clearance_tasks(timezone.localdate()), [])
        version = self.case(pk, self.officer)['version']
        self.act(self.officer, f'/api/releases/{pk}/penalties', {'version': version, 'reason': 'Checklist reviewed; no penalty'})

        state = self.case(pk, self.authority)
        self.assertEqual(state['readiness']['outcome'], 'READY_FOR_AUTHORITY_REVIEW', state['readiness'])
        self.assertTrue(state['actions']['can_approve'])
        self.act(self.pgrc, f'/api/releases/{pk}/approve', {'version': state['version'],
                 'instrument_version': state['instrument_version'], 'reason': 'Clearance cannot decide'}, 403)
        approved = self.act(self.authority, f'/api/releases/{pk}/approve', {'version': state['version'],
                            'instrument_version': state['instrument_version'], 'reason': 'All conditions met'})
        self.assertEqual(approved['status'], 'APPROVED')
        with patch('casework.services.secrets.token_urlsafe', return_value='t' * 43):
            issued = self.act(self.authority, f'/api/releases/{pk}/issue', {'version': approved['version'], 'reason': 'Issue NOC'})
        self.assertEqual(issued['letter']['kind'], 'NOC')
        letter = IssuedLetter.objects.get(case_id=pk)
        self.assertTrue(bytes(letter.pdf).startswith(b'%PDF'))
        self.client.logout()
        public = self.client.get('/api/public/verify/' + 't' * 43).json()
        self.assertEqual((public['status'], public['kind']), ('ISSUED', 'NOC'))

        self.client.force_login(self.authority)
        response = self.client.post(f'/api/releases/{pk}/complete', {'version': issued['version'],
            'instrument_version': issued['instrument_version'], 'notes': 'Original FDR handed over',
            'document': SimpleUploadedFile('handover.pdf', sample_pdf(), content_type='application/pdf')})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], 'COMPLETED')
        self.record.refresh_from_db()
        self.assertTrue(self.record.is_released)
        self.assertEqual(verify_chain().status, 'ok')

    def test_release_documents_scope_kind_and_state(self):
        self.assertEqual(self.upload('FDR').status_code, 409)  # deposit documents only on editable records
        self.assertEqual(self.upload('REQUEST_LETTER', user=self.b).status_code, 404)
        self.record.refresh_from_db()
        response = self.as_user(self.a).post(f'/api/instruments/{self.record.pk}/documents/', {
            'version': self.record.version - 1, 'kind': 'REQUEST_LETTER',
            'document': SimpleUploadedFile('r.pdf', sample_pdf(), content_type='application/pdf')})
        self.assertEqual(response.status_code, 409)

    def test_requirements_allowed_denied_and_invalid(self):
        self.assertEqual(self.requirements().status_code, 200)
        self.assertEqual(self.requirements(user=self.b).status_code, 404)
        self.assertEqual(self.requirements(user=self.officer).status_code, 403)
        self.assertEqual(self.requirements(path='SIDEWAYS').status_code, 400)

    def test_missing_answers_or_documents_block_the_request(self):
        for kind in ('REQUEST_LETTER', 'AFFIDAVIT_6'):
            self.upload(kind)
        self.record.refresh_from_db()
        payload = {'instrument_id': self.record.pk, 'obligation_id': self.obligation.pk,
                   'instrument_version': self.record.version, 'path': 'TERM_COMPLETE', 'declarations': answers(),
                   'reason': 'Term complete', 'template_ref': AFFIDAVIT_6['version']}
        self.act(self.a, '/api/releases', payload, 409)  # LoA/EoA missing
        self.upload('APPROVAL_LETTER')
        self.record.refresh_from_db()
        payload |= {'instrument_version': self.record.version, 'declarations': answers() | {'no_trustee_dispute': False}}
        self.act(self.a, '/api/releases', payload, 409)  # a declared dispute is a hold
        self.assertFalse(Instrument.objects.get(pk=self.record.pk).has_active_release)


@override_settings(ROOT_URLCONF='config.urls')
class ConfirmationAndCoverage(StaffTestCase):
    def test_ps6_statement_match_confirms_and_dashboard_shows_draft_rule_shortfall(self):
        record = self.submitted()
        Instrument.objects.filter(pk=record.pk).update(mode='RTGS', utr='UTR-PS6')
        record.refresh_from_db()
        line = f'utr,amount,value_date\nUTR-PS6,{record.amount_paise / 100:.2f},{record.issue_date}\n'.encode()
        import_statement(self.officer, line, 'SIMULATED statement', {str(record.pk): record.version})
        record.refresh_from_db()
        self.assertEqual(record.verification_level, 'CONFIRMED')
        self.assertEqual(record.verification_evidence.get(method='SIMULATED_STATEMENT').result, 'SIMULATED_MATCH')

        rule = RuleSet.objects.create(code='ps3-draft', version=1, effective_from=date(2026, 1, 1), payload=draft_payload(),
                                      source_document='Synthetic', source_clause='Table 1.4')
        DepositObligation.objects.create(institution=self.institution_a, rule_version=rule, required_paise=150000000,
                                         term_start=date(2026, 1, 1), term_end=date(2036, 1, 1))
        self.client.force_login(self.officer)
        row = self.client.get('/api/dashboard/').json()['coverage'][0]
        self.assertTrue(row['known'])
        self.assertEqual((row['shortfall_paise'], row['policy_label']), (150000000, 'DRAFT_DEMO_NOT_APPROVED'))

    def test_record_download_and_export_write_explicit_access_rows(self):
        from access.models import AccessLog
        record = self.submitted()
        self.client.force_login(self.officer)
        document = record.documents.get()
        response = self.client.get(f'/api/documents/{document.pk}/download/')
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/instruments/export.csv').status_code, 200)
        self.assertTrue(AccessLog.objects.filter(action=AccessLog.DOCUMENT_DOWNLOAD, object_id=document.pk).exists())
        self.assertTrue(AccessLog.objects.filter(action=AccessLog.EXPORT, object_type='instrument_register').exists())


@override_settings(ROOT_URLCONF='config.urls')
class ProofReceiptReviews(StaffTestCase):
    """S2 PROOF_OVERDUE: an officer records receipt dates; with no review, receipt timing stays unknown."""

    def setUp(self):
        super().setUp()
        rule = RuleSet.objects.create(code='proof-draft', version=1, effective_from=date(2026, 1, 1), payload=draft_payload(),
                                      source_document='Synthetic', source_clause='2.25(f)')
        self.obligation = DepositObligation.objects.create(institution=self.institution_a, rule_version=rule,
            required_paise=150000000, term_start=date(2026, 1, 1), term_end=date(2036, 1, 1),
            intimation_date=timezone.localdate() - timedelta(days=40))

    def detail(self, user):
        self.client.force_login(user)
        return self.client.get(f'/api/obligations/{self.obligation.pk}').json()

    def record(self, user, **values):
        self.client.force_login(user)
        payload = {'version': self.obligation.version, 'payment_proof_on': None, 'affidavit_on': None,
                   'reason': 'Receipt register checked'} | values
        return self.client.post(f'/api/obligations/{self.obligation.pk}/proof-receipts', payload,
                                content_type='application/json')

    def test_review_makes_overdue_proof_visible_and_complete_proof_clears_it(self):
        before = self.detail(self.officer)
        self.assertEqual(before['assessment']['proof_assessment'], 'UNAVAILABLE')
        self.assertTrue(before['actions']['can_record_proof_receipts'])
        received = (timezone.localdate() - timedelta(days=30)).isoformat()
        response = self.record(self.officer, payment_proof_on=received)
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body['assessment']['proof_assessment'], 'AVAILABLE')
        overdue = next(f for f in body['assessment']['findings'] if f['code'] == 'PROOF_OVERDUE')
        self.assertEqual(overdue['values']['missing_documents'], ['AFFIDAVIT_3'])
        self.assertEqual(body['proof_review']['payment_proof_on'], received)
        self.obligation.refresh_from_db()
        response = self.record(self.officer, payment_proof_on=received, affidavit_on=received)
        codes = [f['code'] for f in response.json()['assessment']['findings']]
        self.assertNotIn('PROOF_OVERDUE', codes)
        self.assertEqual(self.obligation.proof_reviews.count(), 2)  # history kept
        self.assertFalse(self.detail(self.a)['actions']['can_record_proof_receipts'])

    def test_denied_stale_and_invalid(self):
        self.assertEqual(self.record(self.a).status_code, 403)
        self.assertEqual(self.record(self.b).status_code, 403)
        self.assertEqual(self.record(self.officer, version=99).status_code, 409)
        future = (timezone.localdate() + timedelta(days=1)).isoformat()
        for values in ({'payment_proof_on': future}, {'affidavit_on': '25-10-2026'}, {'reason': ''}, {'extra': 1}):
            with self.subTest(values=values):
                self.assertEqual(self.record(self.officer, **values).status_code, 400)
        self.assertFalse(self.obligation.proof_reviews.exists())


@override_settings(DEBUG=True)
class SeedV2Scenarios(TestCase):
    """A fresh install's seed data shows PS 3 (shortfall), PS 7 (release-ready record) and PS 9 (KPI figures)."""

    def setUp(self):
        self.temp = TemporaryDirectory(prefix='fdr-seed-v2-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        shutil.copytree(settings.BASE_DIR / 'fixtures', root / 'fixtures')
        (root / 'data').mkdir()
        override = override_settings(BASE_DIR=root, MEDIA_ROOT=root / 'data' / 'documents')
        override.enable()
        self.addCleanup(override.disable)
        out = StringIO()
        call_command('seed_demo', generate_password=True, stdout=out)
        call_command('seed_demo', authority_only=True, generate_password=True, stdout=out)
        call_command('seed_staff', generate_password=True, stdout=out)
        call_command('seed_review', stdout=out)
        self.output = out.getvalue()

    def test_seeded_obligation_release_record_kpis_and_idempotence(self):
        self.assertIn('PS 3/7/9 review data', self.output)
        officer = get_user_model().objects.get(username='officer')
        institution_a = get_user_model().objects.get(username='institution_a')
        self.client.force_login(officer)
        coverage = self.client.get('/api/dashboard/').json()['coverage']
        demo_a = next(row for row in coverage if row['required_paise'] == 1000000000)
        self.assertGreater(demo_a['shortfall_paise'], 0)  # (35 + 15) lakh x 2 for leased land, far above holdings

        release = Instrument.objects.get(reference='PS7-RELEASE-READY')
        self.client.force_login(institution_a)
        ready = self.client.get('/api/releases/requirements', {'instrument': release.pk,
                                'obligation': release.obligation_id}).json()
        self.assertTrue(ready['eligible'] and ready['documents_ready'] and ready['term_elapsed'])

        now = timezone.now()
        result = kpi_report(officer, window_start=now - timedelta(days=400), window_end=now, as_of=now)
        self.assertGreaterEqual(result['submission_to_acceptance']['sample_count'], 4)
        # The M6 scenario records are accepted at install time; the dated history gives the upper percentile.
        self.assertGreater(float(result['submission_to_acceptance']['p90_seconds']), 86400)
        dated = kpi_report(officer, window_start=now - timedelta(days=400),
                           window_end=timezone.make_aware(timezone.datetime(2026, 10, 1)))
        self.assertGreater(float(dated['submission_to_acceptance']['median_seconds']), 86400)
        renewal = result['renewed_on_time']['known_subset']
        self.assertGreaterEqual(renewal['denominator'], 2)
        self.assertGreaterEqual(renewal['numerator'], 1)
        confirmed = result['confirmed_share']
        self.assertGreaterEqual(confirmed['numerator'], 1)  # the statement-confirmed RTGS deposit
        self.assertIsNotNone(confirmed['percentage_bps'])
        self.assertEqual(Instrument.objects.get(reference='PS6-RTGS-CONFIRMED').verification_level, 'CONFIRMED')

        self.client.force_login(officer)
        proof = DepositObligation.objects.get(basis_reference='PS3-DEMO-A')
        assessment = self.client.get(f'/api/obligations/{proof.pk}').json()['assessment']
        self.assertEqual(assessment['proof_assessment'], 'AVAILABLE')
        self.assertIn('PROOF_OVERDUE', [f['code'] for f in assessment['findings']])
        self.assertEqual(verify_chain().status, 'ok')

        before = Instrument.objects.count()
        call_command('seed_review_ps_data', stdout=StringIO())
        self.assertEqual(Instrument.objects.count(), before)
