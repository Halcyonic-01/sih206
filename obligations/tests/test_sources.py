"""P4 actual-model source scenarios. All records/files are synthetic and isolated."""
from datetime import date, timedelta
from unittest.mock import patch
from django.db import OperationalError
from django.http import Http404
from django.test import override_settings
from django.utils import timezone

from obligations import services, sources
from obligations.catalogue import draft_payload
from obligations.models import DepositObligation, RuleSet
from portal.models import Document, Instrument
from portal.record_operations import upload_document
from portal.tests.common import PortalTestCase


@override_settings(ROOT_URLCONF='config.urls', NOTIFY_SEND_ON_COMMIT=False,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SourceTests(PortalTestCase):
    when = date(2026, 10, 25)

    def setUp(self):
        self.rule = RuleSet.objects.create(code='synthetic-p4', version=1,
            effective_from=date(2026,1,1), payload=draft_payload(),
            source_document='Synthetic rule context', source_clause='Synthetic')
        self.obligation = DepositObligation.objects.create(institution=self.institution_a,
            required_paise=20000, rule_version=self.rule, term_start=date(2026,1,1),
            term_end=date(2030,1,1), intimation_date=date(2026,1,1))

    def item(self, **values):
        return Instrument.objects.create(**(dict(institution=self.institution_a,created_by=self.a,
            obligation=self.obligation,reference='SYNTHETIC-P4',bank='Synthetic',amount_paise=10000,
            issue_date=date(2026,1,1),maturity_date=date(2030,1,1),status='ACCEPTED')|values))

    def assessment(self, actor=None):
        return services.obligation_detail(actor or self.officer,self.obligation.pk,as_of=self.when)['assessment']

    def test_known_empty_ledger_is_zero_but_receipt_timing_is_unknown(self):
        result=self.assessment()
        self.assertEqual(result['status'],'AVAILABLE')
        self.assertEqual(result['coverage']['held_paise'],0)
        self.assertEqual(result['coverage']['shortfall_paise'],20000)
        self.assertEqual(result['proof_assessment'],'UNAVAILABLE')
        self.assertEqual(result['proof_evidence'],[])
        self.assertNotIn('PROOF_OVERDUE',[f['code'] for f in result['findings']])

    def test_only_eligible_current_explicit_links_contribute(self):
        eligible=self.item()
        self.item(status='SUBMITTED',amount_paise=22222)
        self.item(status='DRAFT',amount_paise=33333)
        self.item(superseded_at=timezone.now(),amount_paise=44444)
        self.item(released_at=timezone.now(),amount_paise=55555)
        self.item(maturity_date=self.when-timedelta(days=1),amount_paise=66666)
        self.item(issue_date=self.when+timedelta(days=1),amount_paise=77777)
        self.item(obligation=None,amount_paise=88888)
        result=self.assessment()
        self.assertEqual(result['coverage']['held_paise'],10000)
        self.assertEqual(result['coverage']['shortfall_paise'],10000)
        self.assertEqual(result['coverage']['holding_ids'],[eligible.pk])
        self.assertIn('AMOUNT_SHORTFALL',[f['code'] for f in result['findings']])
        self.assertEqual(result['policy_label'],'DRAFT_DEMO_NOT_APPROVED')

    def test_accepted_successor_keeps_original_obligation_term(self):
        predecessor=self.item(maturity_date=self.when-timedelta(days=1),superseded_at=timezone.now())
        successor=self.item(predecessor=predecessor,issue_date=self.when,amount_paise=20000)
        result=self.assessment()
        self.assertEqual(result['coverage']['holding_ids'],[successor.pk])
        self.assertEqual(result['coverage']['held_paise'],20000)
        self.assertEqual(result['coverage']['coverage_end'],'2030-01-01')
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.term_start,date(2026,1,1))
        self.assertEqual(self.obligation.term_end,date(2030,1,1))

    def test_foreign_scope_and_corrupt_cross_institution_link_fail_closed(self):
        with self.assertRaises(Http404): sources.linked_holdings(self.b,self.obligation)
        with self.assertRaises(Http404): sources.proof_evidence(self.b,self.obligation)
        self.item(institution=self.institution_b,created_by=self.b)
        result=self.assessment()
        self.assertEqual(result['status'],'UNAVAILABLE')
        self.assertIsNone(result['coverage'])

    def test_real_y2_y3_pdf_metadata_is_not_a_reviewed_receipt(self):
        item=self.draft()
        item.obligation=self.obligation
        item.save(update_fields=['obligation'])
        upload_document(self.a,item.pk,item.version,self.pdf('synthetic-affidavit.pdf'),Document.Kind.AFFIDAVIT_3)
        item.refresh_from_db()
        self.client.force_login(self.a)
        response=self.client.post(f'/api/instruments/{item.pk}/submit/',{'version':item.version},content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        documents=sources.proof_evidence(self.officer,self.obligation)
        self.assertEqual({d['kind'] for d in documents},{'FDR','AFFIDAVIT_3'})
        self.assertTrue(all(d['page_count']>=1 and d['page_reference']==1 for d in documents))
        self.assertTrue(all(d['received_on'] is None for d in documents))
        self.assertTrue(all(d['status']=='STORED_METADATA_ONLY' for d in documents))
        result=self.assessment()
        self.assertEqual(result['proof_assessment'],'UNAVAILABLE')
        self.assertNotIn('PROOF_OVERDUE',[f['code'] for f in result['findings']])
        self.client.force_login(self.b)
        for d in documents:
            self.assertEqual(self.client.get(d['download_path']).status_code,404)

    def test_bad_receipt_provider_preserves_valid_holdings_assessment(self):
        self.item(amount_paise=20000)
        for receipts in [{'payment_proof_on':True,'affidavit_on':None},
                         {'payment_proof_on':self.when+timedelta(days=1),'affidavit_on':None}]:
            with override_settings(SAKSHAM_PROOF_RECEIPTS=lambda *args:receipts):
                result=self.assessment()
            self.assertEqual(result['status'],'AVAILABLE')
            self.assertEqual(result['coverage']['held_paise'],20000)
            self.assertEqual(result['proof_assessment'],'UNAVAILABLE')
            self.assertNotIn('PROOF_OVERDUE',[f['code'] for f in result['findings']])

    def test_explicit_complete_reviewed_provider_can_report_known_missing_proof(self):
        # Test-only trusted contract; no default runtime provider is configured.
        self.item()
        with override_settings(SAKSHAM_PROOF_RECEIPTS=lambda *args:{'payment_proof_on':None,'affidavit_on':None}):
            result=self.assessment()
        self.assertEqual(result['proof_assessment'],'AVAILABLE')
        self.assertIn('PROOF_OVERDUE',[f['code'] for f in result['findings']])

    def test_document_database_failure_uses_safe_shared_503(self):
        self.client.force_login(self.officer)
        with patch('obligations.sources.scoped_documents',side_effect=OperationalError('private database')):
            response=self.client.get(f'/api/obligations/{self.obligation.pk}')
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['code'],'unavailable')
        self.assertNotIn(b'private database',response.content)
