"""Document master keys: 32 random bytes as URL-safe base64. Kept apart from portal/ so settings can validate them."""
import base64
import binascii
import hashlib
import os

from django.core.exceptions import ImproperlyConfigured


def parse_key(value):
    text = value.strip()
    try:
        raw = base64.urlsafe_b64decode(text.encode('ascii') + b'=' * (-len(text) % 4))
    except (binascii.Error, UnicodeError, ValueError):
        raw = b''
    if len(raw) != 32:
        raise ImproperlyConfigured('A document encryption key must be 32 random bytes as URL-safe base64.')
    return raw


def generate_key():
    return base64.urlsafe_b64encode(os.urandom(32)).decode('ascii').rstrip('=')


def key_id(master):
    return hashlib.sha256(master).digest()[:4]
