from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from portal import services as records
from portal.models import Instrument
from portal.tests.common import PortalTestCase
from verification.models import StatementImport, VerificationEvidence
from verification.services import checks, import_statement, plan_matches


class ReconciliationTests(PortalTestCase):
    def rtgs(self):
        item = self.draft()
        item.mode = 'RTGS'
        item.utr = 'SYNTHETIC-UTR'
        item.status = 'SUBMITTED'
        item.save()
        return item

    def csv(self, amount='500000.25'):
        return f'utr,amount,value_date\nSYNTHETIC-UTR,{amount},2026-01-01\n'.encode()

    def test_preview_commit_replay_and_simulation_never_promote_confirmation(self):
        item = self.rtgs()
        content = self.csv()
        preview = plan_matches(self.officer, content)
        self.assertEqual(preview[0]['result'], 'SIMULATED_MATCH')
        self.assertFalse(StatementImport.objects.exists())
        batch, replay = import_statement(self.officer, content, 'Synthetic bank fixture', {str(item.pk): item.version})
        self.assertFalse(replay)
        item.refresh_from_db()
        self.assertEqual(item.verification_level, 'DECLARED')
        self.assertTrue(batch.simulated)
        self.assertEqual(item.verification_evidence.get().method, 'SIMULATED_STATEMENT')
        _, replay = import_statement(self.officer, content, 'Synthetic bank fixture', {})
        self.assertTrue(replay)
        self.assertEqual(item.verification_evidence.count(), 1)

    def test_stale_version_rolls_back_batch_lines_evidence_and_audit(self):
        item = self.rtgs()
        before = item.audit_events.count()
        with self.assertRaises(records.WorkflowError):
            import_statement(self.officer, self.csv(), 'Synthetic', {str(item.pk): 999})
        self.assertFalse(StatementImport.objects.exists())
        self.assertFalse(VerificationEvidence.objects.exists())
        self.assertEqual(item.audit_events.count(), before)

    def test_mismatch_creates_blocking_observation_and_evidence(self):
        item = self.rtgs()
        batch, _ = import_statement(self.officer, self.csv('400000.00'), 'Synthetic', {str(item.pk): item.version})
        item.refresh_from_db()
        self.assertEqual(item.verification_level, 'DISCREPANCY')
        self.assertEqual(batch.lines.get().result, 'DISCREPANCY')
        self.assertTrue(item.observations.filter(severity='BLOCKING', resolved_at__isnull=True).exists())
        with self.assertRaises(records.WorkflowError):
            records.review(self.officer, item.pk, item.version, 'accept', 'Synthetic review')

    def test_duplicate_statement_lines_and_multiple_candidates_never_auto_match(self):
        item = self.rtgs()
        content = self.csv() + b'SYNTHETIC-UTR,500000.25,2026-01-01\n'
        self.assertTrue(all(r['result'] == 'AMBIGUOUS' for r in plan_matches(self.officer, content)))
        clone = Instrument.objects.get(pk=item.pk)
        clone.pk = None
        clone.save()
        self.assertEqual(plan_matches(self.officer, self.csv())[0]['result'], 'AMBIGUOUS')

    def test_unauthorized_institution_and_malformed_csv_rejected(self):
        for operation in [lambda: plan_matches(self.a, self.csv()),
                          lambda: import_statement(self.a, self.csv(), 'Synthetic', {})]:
            with self.assertRaises(PermissionDenied):
                operation()
        for content in [b'wrong,headers\n', self.csv('NaN'), self.csv('1.001'), b'utr,amount,value_date\n']:
            with self.subTest(content=content), self.assertRaises(ValidationError):
                plan_matches(self.officer, content)

    def test_evidence_is_append_only_and_obsolete_evidence_does_not_promote_edits(self):
        item = self.rtgs()
        import_statement(self.officer, self.csv(), 'Synthetic', {str(item.pk): item.version})
        evidence = item.verification_evidence.get()
        for operation in [lambda: evidence.save(), lambda: evidence.delete(),
                          lambda: VerificationEvidence.objects.filter(pk=evidence.pk).update(source='changed'),
                          lambda: VerificationEvidence.objects.all().delete()]:
            with self.assertRaises(ValidationError):
                operation()

    def test_officer_acceptance_records_reviewed_evidence(self):
        item = self.submitted()
        item = records.review(self.officer, item.pk, item.version, 'accept', 'Synthetic document review')
        self.assertEqual(item.verification_level, 'REVIEWED')
        self.assertEqual(item.verification_evidence.get().result, 'REVIEWED')

    @override_settings(ROOT_URLCONF='config.urls')
    def test_evidence_and_statement_api_scope(self):
        item = self.rtgs()
        self.client.force_login(self.a)
        self.assertEqual(self.client.get(f'/api/instruments/{item.pk}/verification/').status_code, 200)
        self.assertEqual(self.client.get('/api/verification/statements/').status_code, 403)
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(f'/api/instruments/{item.pk}/verification/').status_code, 404)
        self.client.force_login(self.officer)
        response = self.client.post('/api/verification/statements/', {
            'document': SimpleUploadedFile('synthetic.csv', self.csv(), content_type='text/csv')})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['simulated'])

    def test_cross_institution_duplicate_warning_visible_only_to_officer(self):
        item = self.rtgs()
        other = self.draft(user=self.b)
        other.status = 'SUBMITTED'
        other.save()
        self.assertIn('CROSS_INSTITUTION_POSSIBLE_DUPLICATE', {f['code'] for f in checks(self.officer, item)})
        self.assertNotIn('CROSS_INSTITUTION_POSSIBLE_DUPLICATE', {f['code'] for f in checks(self.a, item)})
