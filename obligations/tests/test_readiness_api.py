"""Real scoped records, current bank evidence and read-only checklist actions."""
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import OperationalError
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection

from access.models import AccessLog
from obligations import readiness_sources
from obligations.catalogue import draft_payload
from obligations.models import DepositObligation, RuleSet, ProofReceiptReview, MasterAudit
from portal.models import Document, Instrument, AuditEvent
from portal.tests.common import PortalTestCase
from verification.models import VerificationEvidence


@override_settings(ROOT_URLCONF='config.urls', NOTIFY_SEND_ON_COMMIT=False,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ReadinessApiTests(PortalTestCase):
    when = date(2026, 10, 27)

    def setUp(self):
        self.clock = patch('obligations.readiness_sources.timezone.localdate', return_value=self.when)
        self.clock.start(); self.addCleanup(self.clock.stop)
        self.authority = get_user_model().objects.create_user(username='readiness-authority')
        self.authority.groups.add(Group.objects.get_or_create(name='Authority')[0])
        self.auditor = get_user_model().objects.create_user(username='readiness-auditor')
        self.auditor.groups.add(Group.objects.get_or_create(name='Auditor')[0])
        self.rule = RuleSet.objects.create(code='readiness-demo', version=1, effective_from=date(2026,1,1),
            payload=draft_payload(), source_document='Synthetic APH context', source_clause='2.25(f)')
        self.obligation = DepositObligation.objects.create(institution=self.institution_a,
            rule_version=self.rule, required_paise=50000025, term_start=date(2026,1,1), term_end=date(2036,1,1),
            intimation_date=self.when-timedelta(days=7))
        self.record = self.draft()
        Instrument.objects.filter(pk=self.record.pk).update(obligation=self.obligation,
            ifsc='DEMO0123456', holder_names='Fictional Trust; AICTE', lien_marked=True)
        self.record.refresh_from_db()
        self.url = f'/api/institutions/{self.institution_a.pk}/readiness'

    def data(self, actor=None):
        self.client.force_login(actor or self.a)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn('no-store', response['Cache-Control'])
        return response.json()

    def items(self, data):
        return {row['id']: row for row in data['obligations'][0]['items']}

    def accept(self):
        Instrument.objects.filter(pk=self.record.pk).update(status='ACCEPTED')
        self.record.refresh_from_db()

    def evidence(self, method='BANK_CONFIRMATION', result='CONFIRMED', **overrides):
        seen = {'reference': self.record.reference, 'amount': str(self.record.amount),
            'ifsc': self.record.ifsc, 'holder_names': self.record.holder_names,
            'issue_date': self.record.issue_date.isoformat(), 'maturity_date': self.record.maturity_date.isoformat(),
            'lien_marked': 'yes' if self.record.lien_marked else 'no', 'authentic': 'yes'}
        seen.update(overrides)
        return VerificationEvidence.objects.create(instrument=self.record, actor=self.officer,
            instrument_version=self.record.version, method=method, result=result,
            source='SYNTHETIC test source', fields_observed=seen)

    def test_own_access_and_denied_roles_foreign_anonymous(self):
        self.data()
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.force_login(self.auditor)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_actual_uploads_receipts_and_dynamic_progress(self):
        self.accept()
        Document.objects.create(instrument=self.record, kind='AFFIDAVIT_3', original_name='synthetic-affidavit.pdf',
            file=self.record.documents.first().file.name, size_bytes=100, sha256='a'*64, page_count=1, uploaded_by=self.a)
        receipt = ProofReceiptReview.objects.create(obligation=self.obligation, reviewed_by=self.officer,
            payment_proof_on=self.when, affidavit_on=self.when, reason='Synthetic receipt review')
        items = self.items(self.data())
        self.assertEqual(items['accepted_deposit']['state'], 'COMPLETE')
        self.assertEqual(items['affidavit_3']['state'], 'COMPLETE')
        self.assertEqual(items['amount_coverage']['state'], 'COMPLETE')
        self.assertEqual(items['proof_receipt']['state'], 'COMPLETE')
        self.assertEqual(items['payment_proof']['state'], 'NOT_APPLICABLE')
        self.assertEqual(self.data()['obligations'][0]['sources']['receipt_review_id'], receipt.pk)

    def test_draft_only_upload_targets_and_accepted_missing_affidavit_has_no_shortcut(self):
        items = self.items(self.data())
        self.assertIn('kind=AFFIDAVIT_3', items['affidavit_3']['targets'][0]['href'])
        self.assertIn('readiness=submit', items['accepted_deposit']['targets'][0]['href'])
        self.accept()
        items = self.items(self.data())
        self.assertEqual(items['affidavit_3']['targets'], [])
        self.assertEqual(items['proof_receipt']['targets'], [])
        self.assertEqual(self.items(self.data(self.officer))['proof_receipt']['targets'][0]['href'],
            f'/institutions/{self.institution_a.pk}?obligation={self.obligation.pk}&readiness=receipts')

    def test_real_bank_confirmation_uses_current_fields_not_workflow_version(self):
        self.accept(); self.evidence()
        self.assertEqual(self.items(self.data())['bank_confirmation']['state'], 'COMPLETE')
        Instrument.objects.filter(pk=self.record.pk).update(version=self.record.version+1)
        self.assertEqual(self.items(self.data())['bank_confirmation']['state'], 'COMPLETE')
        Instrument.objects.filter(pk=self.record.pk).update(amount_paise=self.record.amount_paise-1)
        self.assertEqual(self.items(self.data())['bank_confirmation']['state'], 'UNKNOWN')

    def test_simulated_statement_never_confirms_issuer_and_discrepancy_wins(self):
        self.accept(); self.evidence(method='SIMULATED_STATEMENT', result='SIMULATED_MATCH')
        self.assertEqual(self.items(self.data())['bank_confirmation']['state'], 'INCOMPLETE')
        self.evidence(method='SIMULATED_BANK', result='SIMULATED_MATCH')
        self.assertEqual(self.items(self.data())['bank_confirmation']['state'], 'SIMULATED')
        self.evidence()
        self.assertEqual(self.items(self.data())['bank_confirmation']['state'], 'COMPLETE')
        self.evidence(result='DISCREPANCY', authentic='no')
        self.assertEqual(self.items(self.data())['bank_confirmation']['state'], 'BLOCKED')

    def test_amount_one_paisa_shortfall_and_missing_rule_context(self):
        self.accept()
        Instrument.objects.filter(pk=self.record.pk).update(amount_paise=50000024,
            issue_date=date(2026,1,1), maturity_date=date(2036,1,1))
        self.assertEqual(self.items(self.data())['amount_coverage']['state'], 'INCOMPLETE')
        Instrument.objects.filter(pk=self.record.pk).update(amount_paise=50000025)
        self.assertEqual(self.items(self.data())['amount_coverage']['state'], 'COMPLETE')
        DepositObligation.objects.filter(pk=self.obligation.pk).update(rule_version=None)
        items = self.items(self.data())
        self.assertEqual(items['amount_coverage']['state'], 'UNKNOWN')
        self.assertEqual(items['affidavit_3']['state'], 'UNKNOWN')

    def test_malformed_new_issuer_response_cannot_borrow_older_match(self):
        self.accept(); self.evidence()
        self.evidence(amount='not-a-number')
        self.assertEqual(self.items(self.data())['bank_confirmation']['state'], 'UNKNOWN')

    def test_nested_malformed_lien_source_stays_unknown(self):
        self.accept(); self.evidence(lien_marked=[])
        self.assertEqual(self.items(self.data())['bank_confirmation']['state'], 'UNKNOWN')

    def test_nonfinite_issuer_amount_stays_unknown(self):
        self.accept(); self.evidence(amount='Infinity')
        self.assertEqual(self.items(self.data())['bank_confirmation']['state'], 'UNKNOWN')
        VerificationEvidence.objects.create(instrument=self.record, actor=self.officer,
            instrument_version=self.record.version, method='BANK_CONFIRMATION', result='CONFIRMED',
            source='SYNTHETIC malformed source', fields_observed=[])
        self.assertEqual(self.items(self.data())['bank_confirmation']['state'], 'UNKNOWN')

    def test_snapshot_fingerprints_change_and_normal_reads_never_write_workflow(self):
        before = (Instrument.objects.count(), Document.objects.count(), AuditEvent.objects.count(), MasterAudit.objects.count())
        first = self.data(); self.assertIn('DRAFT_DEMO_NOT_APPROVED', first['obligations'][0]['policy_source'])
        Instrument.objects.filter(pk=self.record.pk).update(version=self.record.version+1)
        second = self.data()
        self.assertNotEqual(first['source_fingerprint'], second['source_fingerprint'])
        self.assertEqual(before, (Instrument.objects.count(), Document.objects.count(), AuditEvent.objects.count(), MasterAudit.objects.count()))
        self.data(self.authority)
        self.assertTrue(AccessLog.objects.filter(action='SEARCH', user=self.authority, object_id=self.institution_a.pk).exists())

    def test_source_and_access_logging_failures_are_safe(self):
        self.client.force_login(self.a)
        with patch('obligations.readiness_sources.coverage', side_effect=OperationalError('PRIVATE_DATABASE_DETAIL')):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'PRIVATE_DATABASE_DETAIL', response.content)
        self.client.force_login(self.officer)
        with patch('obligations.api.readiness_views.log_access', side_effect=OperationalError('PRIVATE_LOG_DETAIL')):
            self.assertEqual(self.client.get(self.url).status_code, 503)

    def test_query_overrides_and_post_not_allowed(self):
        self.client.force_login(self.a)
        self.assertEqual(self.client.get(self.url+'?as_of=2036-01-01').status_code, 400)
        self.assertEqual(self.client.post(self.url, {}).status_code, 405)

    def test_empty_and_evidenced_exemption_are_not_false_100_percent(self):
        self.client.force_login(self.b)
        empty = self.client.get(f'/api/institutions/{self.institution_b.pk}/readiness').json()
        self.assertEqual((empty['percent'], empty['status']), (None, 'NO_OBLIGATIONS'))
        DepositObligation.objects.filter(pk=self.obligation.pk).update(status='EXEMPT', required_paise=0, exemption_approved_by=self.authority,
            exemption_code='SYNTHETIC', exemption_clause='Synthetic exemption', exemption_reason='Synthetic review')
        self.assertEqual((self.data()['percent'], self.data()['status']), (None, 'NOT_APPLICABLE'))

    def test_bounds_and_cross_link_corruption_fail_closed(self):
        self.client.force_login(self.a)
        with patch('obligations.readiness_sources.MAX_OBLIGATIONS', 0):
            self.assertEqual(self.client.get(self.url).status_code, 503)
        foreign = DepositObligation.objects.create(institution=self.institution_b, required_paise=1)
        Instrument.objects.filter(pk=self.record.pk).update(obligation=foreign)
        self.assertEqual(self.client.get(self.url).status_code, 503)

    def test_query_count_is_bounded_for_many_holdings(self):
        for number in range(6):
            Instrument.objects.create(institution=self.institution_a, created_by=self.a, obligation=self.obligation,
                reference=f'SYNTHETIC-QUERY-{number}', bank='Synthetic', amount_paise=1,
                issue_date=date(2026,1,1), maturity_date=date(2036,1,1))
        self.client.force_login(self.a)
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertLessEqual(len(captured), 45)
