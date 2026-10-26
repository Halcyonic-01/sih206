from datetime import datetime, timezone
from types import SimpleNamespace

from django.test import SimpleTestCase

from portal import services as records
from portal.tests.common import PortalTestCase
from verification.provenance import CONFIRMED, DECLARED, DOCUMENT_REVIEWED, FIELDS, MISMATCH, derive
from verification.services import field_provenance, import_statement

WHEN = datetime(2026, 10, 1, tzinfo=timezone.utc)


def item(**changes):
    values = dict(amount_paise=50000025, reference='FDR-1', ifsc='SBIN0001', bank='State Bank', holder_names='Trust and AICTE',
                  issue_date=datetime(2026, 1, 1).date(), maturity_date=datetime(2027, 1, 1).date(), utr='UTR1', lien_marked=True)
    return SimpleNamespace(**(values | changes))


def row(pk, method, result='CONFIRMED', **seen):
    return SimpleNamespace(pk=pk, method=method, result=result, fields_observed=seen, created_at=WHEN)


class DeriveTests(SimpleTestCase):
    def status(self, record, rows, corrections=()):
        return {name: value['status'] for name, value in derive(record, rows, corrections).items()}

    def test_nothing_but_the_institution_means_declared_everywhere(self):
        self.assertEqual(set(self.status(item(), []).values()), {DECLARED})
        self.assertEqual(set(self.status(item(), [])), set(FIELDS))

    def test_officer_review_marks_every_field_document_reviewed(self):
        self.assertEqual(set(self.status(item(), [row(1, 'OFFICER_REVIEW', 'REVIEWED')]).values()), {DOCUMENT_REVIEWED})

    def test_statement_confirms_only_the_fields_it_saw(self):
        evidence = row(2, 'SIMULATED_STATEMENT', 'SIMULATED_MATCH', utr='utr1', amount_paise=50000025, value_date='2026-01-01')
        status = self.status(item(), [evidence])
        self.assertEqual([status[n] for n in ('utr', 'amount', 'issue_date')], [CONFIRMED] * 3)
        self.assertEqual(status['maturity_date'], DECLARED)
        self.assertTrue(derive(item(), [evidence])['amount']['simulated'])
        self.assertIn('SIMULATED', derive(item(), [evidence])['amount']['source'])

    def test_a_field_the_statement_disagrees_with_is_a_mismatch_even_after_review(self):
        evidence = [row(1, 'OFFICER_REVIEW', 'REVIEWED'),
                    row(2, 'SIMULATED_STATEMENT', 'DISCREPANCY', utr='utr1', amount_paise=40000000, value_date='2026-01-01')]
        status = self.status(item(), evidence)
        self.assertEqual(status['amount'], MISMATCH)
        self.assertEqual(status['utr'], CONFIRMED)
        self.assertEqual(status['reference'], DOCUMENT_REVIEWED)

    def test_evidence_stops_confirming_once_the_declared_value_changes(self):
        evidence = row(2, 'SIMULATED_STATEMENT', 'SIMULATED_MATCH', amount_paise=50000025)
        self.assertEqual(self.status(item(amount_paise=60000000), [evidence])['amount'], MISMATCH)

    def test_bank_response_covers_holder_lien_and_ifsc_and_a_denial_confirms_nothing(self):
        seen = dict(authentic='yes', reference='FDR-1', amount='500000.25', issue_date='2026-01-01', maturity_date='2027-01-01',
                    ifsc='sbin0001', lien_marked='yes', holder_names='trust and aicte', loans_or_mortgage='no')
        status = self.status(item(), [row(3, 'SIMULATED_BANK', 'SIMULATED_MATCH', **seen)])
        self.assertEqual([status[n] for n in ('holder_names', 'lien_marked', 'ifsc', 'maturity_date')], [CONFIRMED] * 4)
        self.assertEqual(status['bank'], DECLARED)
        denied = self.status(item(), [row(4, 'BANK_CONFIRMATION', 'DISCREPANCY', **(seen | {'authentic': 'no'}))])
        self.assertEqual(denied['amount'], MISMATCH)

    def test_the_latest_evidence_for_a_field_decides(self):
        old = row(1, 'SIMULATED_STATEMENT', 'DISCREPANCY', amount_paise=40000000)
        new = row(2, 'SIMULATED_STATEMENT', 'SIMULATED_MATCH', amount_paise=50000025)
        self.assertEqual(self.status(item(), [old, new])['amount'], CONFIRMED)

    def test_a_field_an_officer_corrected_after_review_goes_back_to_declared(self):
        later = datetime(2026, 11, 1, tzinfo=timezone.utc)
        correction = SimpleNamespace(created_at=later, before={'holder_names': 'Trust'}, after={'holder_names': 'Trust and AICTE'})
        status = self.status(item(), [row(1, 'OFFICER_REVIEW', 'REVIEWED')], [correction])
        self.assertEqual(status['holder_names'], DECLARED)
        self.assertEqual(status['amount'], DOCUMENT_REVIEWED)


class ProvenanceOnRecordsTests(PortalTestCase):
    def rtgs(self):
        record = self.draft()
        record.mode, record.utr, record.status = 'RTGS', 'SYNTHETIC-UTR', 'SUBMITTED'
        record.save()
        return record

    def test_statement_confirmation_and_mismatch_show_up_on_the_record(self):
        record = self.rtgs()
        csv = b'utr,amount,value_date\nSYNTHETIC-UTR,500000.25,2026-01-01\n'
        import_statement(self.officer, csv, 'Synthetic', {str(record.pk): record.version})
        record.refresh_from_db()
        provenance = field_provenance(record)
        self.assertEqual(provenance['amount']['status'], CONFIRMED)
        self.assertTrue(provenance['amount']['simulated'])
        self.assertEqual(provenance['holder_names']['status'], DECLARED)

    def test_the_api_returns_provenance_with_the_detail_and_it_follows_acceptance(self):
        record = self.submitted()
        self.client.force_login(self.officer)
        body = self.client.get(f'/api/instruments/{record.pk}/').json()
        self.assertEqual({v['status'] for v in body['field_provenance'].values()}, {DECLARED})
        reviewed = records.review(self.officer, record.pk, record.version, 'accept', 'Synthetic review')
        body = self.client.get(f'/api/instruments/{reviewed.pk}/').json()
        self.assertEqual(body['field_provenance']['amount']['status'], DOCUMENT_REVIEWED)
        self.assertEqual(body['field_provenance']['amount']['source'], 'Officer review')
        self.client.force_login(self.a)
        owner_view = self.client.get(f'/api/instruments/{reviewed.pk}/').json()
        self.assertEqual(owner_view['field_provenance']['amount']['status'], DOCUMENT_REVIEWED)
