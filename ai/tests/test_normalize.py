import os
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from ai import normalize
from ai.comparison import build_findings
from ai.services import FIELD_NAMES, extract, validate_output
from portal.tests.common import PortalTestCase


def output(words=None, **values):
    body = {'fields': {name: {'value': values.get(name), 'page': 1 if name in values else None} for name in FIELD_NAMES}}
    if words is not None:
        body['amount_in_words'] = words
    return body


class AmountTests(SimpleTestCase):
    def test_formatting_alone_is_never_a_difference(self):
        for text in ('500000.25', '5,00,000.25', '₹ 5,00,000.25', 'Rs. 500,000.25', 'INR 500000.25/-', '  ₹5,00,000.25 '):
            self.assertEqual(normalize.normalize_amount(text), Decimal('500000.25'), text)

    def test_unreadable_figures_are_unknown_not_different(self):
        for text in ('five lakh', '5.0.0', '', None, '12 34'):
            self.assertIsNone(normalize.normalize_amount(text), text)
        self.assertEqual(normalize.compare('amount', 'five lakh', '500000.00')[0], 'unknown')
        self.assertEqual(normalize.compare('amount', '500000', '500000.00')[0], 'same')
        self.assertEqual(normalize.compare('amount', '400000', '500000.00')[0], 'different')


class WordsTests(SimpleTestCase):
    def test_indian_numbering_words(self):
        cases = {
            'Rupees Five Lakh Only': 50_000_000,
            'Rupees Five Lakh Twenty Five Thousand and Twenty Five Paise Only': 52_500_025,
            'Rupees One Crore Fifty Lakh and Fifty Paise only': 1_500_000_050,
            'Five Hundred Thousand': 50_000_000,
            'Rupees Twenty-One Thousand Four Hundred Only': 2_140_000,
            'Rupees Ten Lakhs Only': 100_000_000,
            'Rupees Nineteen Only': 1_900,
        }
        for text, paise in cases.items():
            self.assertEqual(normalize.words_to_paise(text), paise, text)

    def test_what_is_not_understood_is_unknown(self):
        for text in ('', None, 'gibberish', 'Rupees Five Lakh Only (approx)', 'Five Lakh and Paise Only'):
            self.assertIsNone(normalize.words_to_paise(text), text)

    def test_finding_only_when_words_and_figures_disagree(self):
        self.assertIsNone(normalize.amount_words_finding('Rupees Five Lakh Only', '500000.00', '500000.00'))
        finding = normalize.amount_words_finding('Rupees Four Lakh Only', '500000.00', '500000.00')
        self.assertEqual((finding['code'], finding['suggested']), ('AMOUNT_WORDS_MISMATCH', '400000.00'))
        self.assertIn('figures on the document', finding['detail'])
        fallback = normalize.amount_words_finding('Rupees Four Lakh Only', None, '500000.00')
        self.assertIn('declared on the record', fallback['detail'])
        self.assertIsNone(normalize.amount_words_finding('unreadable words', '500000.00', '500000.00'))


class BankAndDateTests(SimpleTestCase):
    def test_bank_names(self):
        same = [('SBI', 'State Bank of India'), ('State Bank Of India Ltd.', 'state bank of india'), ('Canara Bank', 'CANARA BANK LIMITED'),
                ('Punjab National Bank', 'PNB')]
        for a, b in same:
            self.assertTrue(normalize.banks_equal(a, b), (a, b))
        self.assertFalse(normalize.banks_equal('Canara Bank', 'Union Bank of India'))
        self.assertIsNone(normalize.banks_equal('Bank', 'Canara Bank'))

    def test_date_layouts(self):
        for text in ('2026-10-24', '24/10/2026', '24-10-2026', '24.10.2026', '24 Oct 2026', '24th October 2026', 'October 24, 2026'):
            self.assertEqual(normalize.normalize_date(text)[0], date(2026, 10, 24), text)
        self.assertEqual(normalize.normalize_date('31/02/2026'), (None, False))
        self.assertEqual(normalize.normalize_date('soon'), (None, False))

    def test_ambiguous_dates_are_flagged_not_guessed(self):
        self.assertEqual(normalize.normalize_date('03/04/2026'), (date(2026, 4, 3), True))
        self.assertEqual(normalize.normalize_date('13/04/2026'), (date(2026, 4, 13), False))
        verdict, note = normalize.compare('issue_date', '03/04/2026', '2026-04-03')
        self.assertEqual(verdict, 'same')
        self.assertIn('DD/MM', note)
        verdict, note = normalize.compare('issue_date', '03/04/2026', '2026-03-04')
        self.assertEqual(verdict, 'different')
        self.assertIn('month/day', note)

    def test_reference_and_ifsc_ignore_case_and_spacing_only(self):
        self.assertEqual(normalize.compare('reference', 'fdr / 123', 'FDR/123')[0], 'same')
        self.assertEqual(normalize.compare('ifsc', 'sbin 0000691', 'SBIN0000691')[0], 'same')
        self.assertEqual(normalize.compare('reference', 'FDR/124', 'FDR/123')[0], 'different')


class FindingsTests(SimpleTestCase):
    record = SimpleNamespace(reference='FDR/123', bank='State Bank of India', amount=Decimal('500000.25'),
                             issue_date=date(2026, 4, 3), maturity_date=date(2027, 4, 3), ifsc='SBIN0000691')

    def test_formatting_differences_raise_nothing(self):
        found = build_findings(self.record, output(reference='fdr/123', bank='SBI Ltd', amount='500000.25',
                                                    issue_date='2026-04-03', ifsc='SBIN0000691'))
        self.assertEqual(found, [])

    def test_real_differences_and_words_are_reported(self):
        found = build_findings(self.record, output(words='Rupees Three Lakh Only', amount='400000.00', bank='Canara Bank'))
        self.assertEqual({(f['code'], f['field']) for f in found},
                         {('AI_MISMATCH', 'amount'), ('AI_MISMATCH', 'bank'), ('AMOUNT_WORDS_MISMATCH', 'amount')})


class IntegrationTests(PortalTestCase):
    @override_settings(AI_ENABLED=True)
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-test-key'})
    def test_extraction_uses_the_normaliser_and_accepts_amount_in_words(self):
        item = self.draft()
        raw = output(words='Rupees Five Lakh and Twenty Five Paise Only', amount='500000.25', bank='FICTIONAL BANK LTD.')
        with patch('ai.services.call_model', return_value=raw):
            result = extract(self.a, item.documents.get(), consent=True, synthetic=True)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['findings'], [])
        self.assertEqual(result['amount_in_words'], 'Rupees Five Lakh and Twenty Five Paise Only')

    def test_the_words_field_is_optional_and_checked(self):
        validate_output(output(), None)
        validate_output(output(words=None), None)
        with self.assertRaises(ValueError):
            validate_output(output(words='x' * 301), None)
        with self.assertRaises(ValueError):
            validate_output({**output(), 'unexpected': 1}, None)
