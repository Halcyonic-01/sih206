from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from portal.tests.common import PortalTestCase
from verification.services import import_statement, plan_matches
from verification.statement_formats import detect, parse

FIXTURES = Path(settings.BASE_DIR) / 'fixtures'


def fixture(name):
    return (FIXTURES / name).read_bytes()


class ParserTests(SimpleTestCase):
    def test_formats_are_detected(self):
        self.assertEqual(detect('utr,amount,value_date\n'), 'CSV')
        self.assertEqual(detect(':20:X\n:61:261024C1,00NTRFREF'), 'MT940')
        self.assertEqual(detect('﻿<?xml version="1.0"?><Document/>'), 'CAMT053')

    def test_csv_is_unchanged(self):
        parsed = parse(fixture('synthetic-statement.csv'))
        self.assertEqual(parsed.format, 'CSV')
        self.assertEqual([(r['utr'], r['amount_paise']) for r in parsed.rows],
                         [('YASH-SYNTHETIC-MATCH', 50000025), ('YASH-SYNTHETIC-MISMATCH', 40000000)])
        with self.assertRaises(ValidationError):
            parse(b'utr,amount,value_date\nA,5,00,2026-01-01\n')
        with self.assertRaises(ValidationError):
            parse(b'utr,amount,value_date\nA,500000,25,2026-10-24\n')   # a comma is not a decimal point in our CSV

    def test_mt940_reads_credits_and_quarantines_bad_lines(self):
        parsed = parse(fixture('synthetic-statement.mt940'))
        self.assertEqual(parsed.format, 'MT940')
        self.assertEqual([(r['utr'], r['amount_paise'], str(r['value_date'])) for r in parsed.rows],
                         [('YASH-SYNTHETIC-MATCH', 50000025, '2026-10-24'), ('YASH-SYNTHETIC-MISMATCH', 40000000, '2026-10-24')])
        self.assertEqual(parsed.rows[0]['alt_utrs'], ['BANKREF0001'])
        self.assertEqual([i['reason'] for i in parsed.ignored], ['debit or reversal, not a receipt'])
        self.assertEqual(len(parsed.rejected), 1)
        self.assertIn('date', parsed.rejected[0]['reason'])

    def test_mt940_uses_a_utr_found_in_the_narrative_when_the_reference_is_nonref(self):
        text = ':20:X\n:61:261024C2500,50NTRFNONREF//B1\n:86:/UTR/SBINR52026102400123 payment\n'
        row = parse(text.encode()).rows[0]
        self.assertEqual((row['utr'], row['amount_paise']), ('B1', 250050))
        self.assertIn('SBINR52026102400123', row['alt_utrs'])

    def test_camt053_reads_credits_references_and_quarantines(self):
        parsed = parse(fixture('synthetic-statement.camt053.xml'))
        self.assertEqual(parsed.format, 'CAMT053')
        self.assertEqual([(r['utr'], r['amount_paise']) for r in parsed.rows],
                         [('YASH-SYNTHETIC-MATCH', 50000025), ('YASH-SYNTHETIC-MISMATCH', 40000000)])
        self.assertEqual([i['reason'] for i in parsed.ignored], ['debit or reversal, not a receipt'])
        self.assertEqual([i['reason'] for i in parsed.rejected], ['currency is not INR'])

    def test_xml_with_entities_or_the_wrong_document_is_refused(self):
        bomb = b'<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaa">]><Document><BkToCstmrStmt/></Document>'
        for content in (bomb, b'<Document><Other/></Document>', b'<Document'):
            with self.assertRaises(ValidationError):
                parse(content)

    def test_a_file_with_no_credit_is_refused(self):
        with self.assertRaisesMessage(ValidationError, 'No credit entries'):
            parse(b':20:X\n:61:261024D1,00NTRFREF\n')
        with self.assertRaises(ValidationError):
            parse(b'\xff\xfe')


class MatchingAcrossFormatsTests(PortalTestCase):
    def rtgs(self, utr):
        item = self.draft()
        item.mode, item.utr, item.status = 'RTGS', utr, 'SUBMITTED'
        item.save()
        return item

    def test_mt940_and_camt_match_like_csv_and_stay_simulated(self):
        from datetime import date
        item = self.rtgs('YASH-SYNTHETIC-MATCH')
        item.issue_date = date(2026, 10, 24)
        item.save()
        for name in ('synthetic-statement.mt940', 'synthetic-statement.camt053.xml'):
            plan = plan_matches(self.officer, fixture(name))
            first = next(r for r in plan if r['utr'] == 'YASH-SYNTHETIC-MATCH')
            self.assertEqual((first['result'], first['instrument_id']), ('SIMULATED_MATCH', item.pk))
            self.assertNotIn('alt_utrs', first)
            second = next(r for r in plan if r['utr'] == 'YASH-SYNTHETIC-MISMATCH')
            self.assertEqual(second['result'], 'UNMATCHED')

    def test_a_line_matches_on_its_other_reference(self):
        item = self.rtgs('BANKREF0001')
        plan = plan_matches(self.officer, fixture('synthetic-statement.mt940'))
        row = next(r for r in plan if r['instrument_id'] == item.pk)
        self.assertEqual(row['utr'], 'BANKREF0001')

    def test_committing_an_mt940_records_a_simulated_batch(self):
        item = self.rtgs('YASH-SYNTHETIC-MATCH')
        batch, _ = import_statement(self.officer, fixture('synthetic-statement.mt940'), 'SIMULATED MT940 test', {str(item.pk): item.version})
        self.assertTrue(batch.simulated)
        self.assertEqual(batch.lines.count(), 2)
