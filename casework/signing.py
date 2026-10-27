"""Ed25519 signature over a letter's key facts, carried in the QR code (P2-5).

* The QR URL is `<base>/verify/<token>?p=<payload>&s=<signature>`: `p` is the canonical JSON of the key facts (URL-safe base64)
  and `s` an Ed25519 signature over those exact bytes. Anyone with the portal's **public** key
  (`GET /api/public/letter-key`) can check a printed letter offline; `/verify/<token>` also compares the facts with the server's record.
* The private key is `LETTER_SIGNING_KEY` (32 random bytes, URL-safe base64). Outside DEBUG, letters are **not issued** without it.
  In DEBUG (and under the test runner) only, a development key derived from the Django secret key is used and labelled DEVELOPMENT in every answer.
* This is not a DSC-signed PDF and not a regulatory signature; it binds the facts in the QR to this portal's key.
"""
import base64
import hashlib
import json

from django.conf import settings

from config.documentkey import parse_key


class SigningUnavailable(Exception):
    pass


def _b64(data):
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _unb64(text):
    return base64.urlsafe_b64decode(text.encode('ascii') + b'=' * (-len(text) % 4))


def _private():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    configured = getattr(settings, 'LETTER_SIGNING_KEY', '')
    if configured:
        return Ed25519PrivateKey.from_private_bytes(parse_key(configured)), 'CONFIGURED'
    if settings.DEBUG or getattr(settings, 'TESTING', False):
        seed = hashlib.sha256(('letter-development-key|' + settings.SECRET_KEY).encode()).digest()
        return Ed25519PrivateKey.from_private_bytes(seed), 'DEVELOPMENT'
    raise SigningUnavailable('LETTER_SIGNING_KEY is not set, so letters cannot be issued.')


def public_key_info():
    from cryptography.hazmat.primitives import serialization
    key, kind = _private()
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {'algorithm': 'Ed25519', 'public_key': _b64(raw), 'kid': hashlib.sha256(raw).hexdigest()[:8], 'key_kind': kind}


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def build_payload(*, serial, kind, case_id, institution, instrument_reference, amount_paise, issued):
    return {'v': 1, 'serial': serial, 'kind': kind, 'case': case_id, 'institution': institution,
            'instrument': instrument_reference, 'amount_paise': amount_paise, 'issued': issued,
            'kid': public_key_info()['kid']}


def sign(payload):
    """(payload_b64, signature_b64) for the QR."""
    key, _ = _private()
    data = canonical(payload)
    return _b64(data), _b64(key.sign(data))


def check(payload_b64, signature_b64, record_payload):
    """What the verify page shows: did our key sign this, and do the signed facts equal the server's record?"""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    info = public_key_info()
    result = {'checked': True, 'valid': False, 'matches_record': False, 'kid': info['kid'], 'key_kind': info['key_kind']}
    try:
        data, signature = _unb64(payload_b64), _unb64(signature_b64)
        key, _ = _private()
        key.public_key().verify(signature, data)
        result['valid'] = True
        result['matches_record'] = data == canonical(record_payload)
    except (InvalidSignature, ValueError, TypeError, UnicodeError):
        pass
    return result
