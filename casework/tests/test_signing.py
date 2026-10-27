import base64

from django.test import TestCase, override_settings
from django.urls import reverse

from casework import signing
from config.documentkey import generate_key

FACTS = dict(serial='SYNTH-1', kind='NOC', case_id=7, institution='Institute A', instrument_reference='FDR-9',
             amount_paise=123456, issued='2026-10-27')


class SigningTests(TestCase):
    @override_settings(LETTER_SIGNING_KEY=generate_key())
    def test_a_signed_payload_verifies_and_matches_its_record(self):
        payload = signing.build_payload(**FACTS)
        p, s = signing.sign(payload)
        result = signing.check(p, s, payload)
        self.assertEqual((result['valid'], result['matches_record'], result['key_kind']), (True, True, 'CONFIGURED'))

    @override_settings(LETTER_SIGNING_KEY=generate_key())
    def test_any_change_to_the_facts_or_the_signature_is_caught(self):
        payload = signing.build_payload(**FACTS)
        p, s = signing.sign(payload)
        other = dict(payload, amount_paise=999)
        self.assertEqual(signing.check(p, s, other), signing.check(p, s, other) | {'valid': True, 'matches_record': False})
        forged_p, _ = signing.sign(other)
        result = signing.check(forged_p, s, payload)          # new facts under the old signature
        self.assertFalse(result['valid'])
        self.assertFalse(signing.check(p, 'AAAA', payload)['valid'])
        self.assertFalse(signing.check('!!', s, payload)['valid'])
        flipped = base64.urlsafe_b64encode(bytes([b ^ 1 for b in base64.urlsafe_b64decode(s + '==')])).decode().rstrip('=')
        self.assertFalse(signing.check(p, flipped, payload)['valid'])

    def test_another_key_does_not_verify(self):
        with override_settings(LETTER_SIGNING_KEY=generate_key()):
            payload = signing.build_payload(**FACTS)
            p, s = signing.sign(payload)
        with override_settings(LETTER_SIGNING_KEY=generate_key()):
            self.assertFalse(signing.check(p, s, payload)['valid'])

    @override_settings(LETTER_SIGNING_KEY='', DEBUG=False, TESTING=False)
    def test_outside_debug_there_is_no_fallback_key(self):
        with self.assertRaises(signing.SigningUnavailable):
            signing.public_key_info()
        self.assertEqual(self.client.get('/api/public/letter-key').status_code, 404)

    @override_settings(LETTER_SIGNING_KEY='', DEBUG=True)
    def test_in_debug_a_labelled_development_key_is_used(self):
        self.assertEqual(signing.public_key_info()['key_kind'], 'DEVELOPMENT')

    @override_settings(LETTER_SIGNING_KEY=generate_key())
    def test_the_public_key_is_published_without_signing_in(self):
        body = self.client.get('/api/public/letter-key').json()
        self.assertEqual((body['algorithm'], body['key_kind']), ('Ed25519', 'CONFIGURED'))
        self.assertEqual(len(base64.urlsafe_b64decode(body['public_key'] + '==')), 32)
