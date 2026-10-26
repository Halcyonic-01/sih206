from django.urls import reverse

from portal.models import Instrument
from portal.validation import CHECKS_VERSION, run_checks
from .common import PortalTestCase


class ValidationTests(PortalTestCase):
    def test_clean_record_has_no_flags_and_explicit_bank_verification_disclaimer(self):
        record = self.draft()
        self.assertEqual(run_checks(record), [])
        response = self.client.get(reverse('instrument_detail', args=[record.pk]))
        self.assertContains(response, 'No flags from the configured technical checks')
        self.assertContains(response, 'Not independently bank-verified')
        self.assertContains(response, 'do not read or compare PDF contents')

    def test_missing_document_has_explainable_blocking_finding(self):
        record = self.draft(with_document=False)
        finding, = run_checks(record)
        self.assertEqual(finding.code, 'FDR_DOCUMENT_REQUIRED')
        self.assertEqual(finding.severity, 'blocking')
        self.assertEqual(finding.values, {'attached_document_count': 0})

    def test_same_institution_duplicate_ignores_case_surrounding_spaces_and_self(self):
        record = self.draft()
        self.assertEqual(run_checks(record), [])
        duplicate = self.draft(with_document=False)
        Instrument.objects.filter(pk=duplicate.pk).update(bank='  fictional bank ', reference=' demo-fdr-001  ')
        finding, = run_checks(record)
        self.assertEqual(finding.code, 'POSSIBLE_DUPLICATE')
        self.assertEqual(finding.severity, 'warning')
        self.assertEqual(finding.values, {'bank': record.bank, 'reference': record.reference})
        self.assertTrue(finding.explanation)

    def test_different_bank_or_reference_does_not_match(self):
        record = self.draft()
        duplicate = self.draft()
        Instrument.objects.filter(pk=duplicate.pk).update(bank='Other Bank')
        self.assertEqual(run_checks(record), [])
        Instrument.objects.filter(pk=duplicate.pk).update(bank=record.bank, reference='Other reference')
        self.assertEqual(run_checks(record), [])

    def test_other_institution_duplicate_does_not_leak_to_institution_or_officer(self):
        self.institution_b.name = 'Private Other Institute'
        self.institution_b.save(update_fields=['name'])
        record = self.submitted()
        other = self.draft(user=self.b)
        self.assertEqual(other.reference, record.reference)
        self.assertEqual(run_checks(record), [])
        for user in (self.a, self.officer):
            self.client.force_login(user)
            page = self.client.get(reverse('instrument_detail', args=[record.pk]))
            self.assertNotContains(page, 'POSSIBLE_DUPLICATE')
            self.assertNotContains(page, self.institution_b.name)
            self.assertEqual(page.context['findings'], [])

    def test_current_findings_do_not_write_and_submission_preserves_check_snapshot(self):
        record = self.draft()
        self.draft(with_document=False)
        before_events = record.audit_events.count()
        url = reverse('instrument_detail', args=[record.pk])
        self.client.get(url)
        self.client.get(url)
        self.assertEqual(record.audit_events.count(), before_events)
        self.client.post(reverse('instrument_submit', args=[record.pk]), {'version': record.version})
        recorded = record.audit_events.get(action='SUBMITTED').after
        self.assertEqual(recorded['checks_version'], CHECKS_VERSION)
        self.assertEqual(recorded['technical_findings'][0]['code'], 'POSSIBLE_DUPLICATE')
        Instrument.objects.exclude(pk=record.pk).update(reference='No longer a duplicate')
        self.assertEqual(run_checks(record), [])
        self.assertEqual(record.audit_events.get(action='SUBMITTED').after, recorded)

    def test_duplicate_warning_does_not_block_human_acceptance_or_verify_bank(self):
        record = self.submitted()
        self.draft()
        self.client.force_login(self.officer)
        response = self.client.post(reverse('instrument_review', args=[record.pk]), {
            'version': record.version, 'decision': 'accept', 'reason': 'Possible duplication manually reviewed.',
            'bank_verification_status': 'CONFIRMED',
        })
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.status, Instrument.Status.ACCEPTED)
        self.assertContains(self.client.get(response.url), 'Not independently bank-verified')
        self.assertEqual(record.audit_events.get(action='ACCEPTED').after['technical_findings'][0]['code'],
                         'POSSIBLE_DUPLICATE')


class AicteHolderAndLienChecksTests(PortalTestCase):
    def codes(self, record):
        return [finding.code for finding in run_checks(record)]

    def test_recorded_holder_without_aicte_is_flagged_and_blank_is_not(self):
        record = self.draft()
        self.assertNotIn('HOLDER_NOT_AICTE', self.codes(record))
        Instrument.objects.filter(pk=record.pk).update(holder_names='Secretary, Fictional Trust')
        record.refresh_from_db()
        finding = next(f for f in run_checks(record) if f.code == 'HOLDER_NOT_AICTE')
        self.assertEqual(finding.severity, 'warning')
        self.assertEqual(finding.values['status'], 'DRAFT_DEMO_NOT_APPROVED')
        self.assertIn('APH 1.12', finding.values['clause'])

    def test_aicte_in_any_form_satisfies_the_holder_check(self):
        record = self.draft()
        for names in ('Secretary of Fictional Trust and Member Secretary, AICTE', 'secretary trust & aicte',
                      'The All India Council for Technical Education'):
            Instrument.objects.filter(pk=record.pk).update(holder_names=names)
            record.refresh_from_db()
            self.assertNotIn('HOLDER_NOT_AICTE', self.codes(record), names)

    def test_a_word_that_merely_contains_aicte_does_not_count(self):
        record = self.draft()
        Instrument.objects.filter(pk=record.pk).update(holder_names='Caicteam Trust')
        record.refresh_from_db()
        self.assertIn('HOLDER_NOT_AICTE', self.codes(record))

    def test_only_an_explicit_no_lien_is_flagged_and_is_advisory_by_default(self):
        record = self.draft()
        for value, expected in ((None, False), (True, False), (False, True)):
            Instrument.objects.filter(pk=record.pk).update(lien_marked=value)
            record.refresh_from_db()
            self.assertEqual('LIEN_NOT_MARKED' in self.codes(record), expected, value)
        finding = next(f for f in run_checks(record) if f.code == 'LIEN_NOT_MARKED')
        self.assertEqual(finding.severity, 'warning')
        self.assertFalse(finding.values['blocks_acceptance'])

    def test_lien_check_blocks_acceptance_only_when_enabled(self):
        from django.test import override_settings
        from portal import services
        record = self.submitted()
        Instrument.objects.filter(pk=record.pk).update(lien_marked=False)
        record.refresh_from_db()
        with override_settings(FDR_LIEN_CHECK_BLOCKING=True):
            self.assertEqual(next(f for f in run_checks(record) if f.code == 'LIEN_NOT_MARKED').severity, 'blocking')
            with self.assertRaisesMessage(services.WorkflowError, 'blocking technical findings'):
                services.review(self.officer, record.pk, record.version, 'accept', 'Reviewed')
        accepted = services.review(self.officer, record.pk, record.version, 'accept', 'Reviewed with a warning only')
        self.assertEqual(accepted.status, 'ACCEPTED')

    def test_other_deposit_modes_are_not_judged(self):
        record = self.draft()
        Instrument.objects.filter(pk=record.pk).update(mode='RTGS', holder_names='Trust only', lien_marked=False)
        record.refresh_from_db()
        codes = self.codes(record)
        self.assertNotIn('HOLDER_NOT_AICTE', codes)
        self.assertNotIn('LIEN_NOT_MARKED', codes)
