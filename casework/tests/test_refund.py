from io import BytesIO

from pypdf import PdfReader
from django.test import SimpleTestCase

from casework.letters import render_letter
from casework.refund import quote


class RefundQuoteTests(SimpleTestCase):
    def test_only_confirmed_penalties_are_deducted(self):
        penalties = [{'amount_paise': 100_00, 'status': 'CONFIRMED'}, {'amount_paise': 50_00, 'status': 'PROPOSED'},
                     {'amount_paise': 7_00, 'status': 'WAIVED'}]
        result = quote(1_000_00, penalties)
        self.assertEqual((result['confirmed_penalties_paise'], result['proposed_penalties_paise'], result['net_paise']),
                         (100_00, 50_00, 900_00))
        self.assertEqual(result['interest'], 'NOT_COMPUTED')

    def test_net_never_goes_negative_and_says_so(self):
        result = quote(100, [{'amount_paise': 500, 'status': 'CONFIRMED'}])
        self.assertEqual(result['net_paise'], 0)
        self.assertTrue(result['penalties_exceed_held'])

    def test_no_penalties_returns_everything(self):
        self.assertEqual(quote(12_345_67, [])['net_paise'], 12_345_67)

    def test_the_letter_states_held_penalties_and_net(self):
        pdf = render_letter(serial='SYNTH-1', kind='NOC', institution_name='Inst', issue_date='2026-10-27',
                            verification_url='https://demo.invalid/verify/x', refund=quote(1_000_000_00, [
                                {'amount_paise': 100_000_00, 'status': 'CONFIRMED'}]))
        text = ''.join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
        self.assertIn('Amount held: INR 1,000,000.00', text)
        self.assertIn('Penalties confirmed: INR 100,000.00', text)
        self.assertIn('Net amount to be returned (quote): INR 900,000.00', text)
        self.assertIn('Interest is not included', text)

    def test_a_letter_without_a_quote_is_unchanged(self):
        pdf = render_letter(serial='S', kind='NOC', institution_name='I', issue_date='2026-10-27',
                            verification_url='https://demo.invalid/verify/x')
        self.assertNotIn('Net amount', ''.join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages))
