"""RFC 6238 time-based one-time passwords (HMAC-SHA1, 6 digits, 30 s), standard library only.

Compatible with Google Authenticator, Microsoft Authenticator, Authy, 1Password and similar apps.
"""
import base64
import hmac
import hashlib
import os
import struct
import time
from urllib.parse import quote

STEP_SECONDS = 30
DIGITS = 6


def new_secret():
    return base64.b32encode(os.urandom(20)).decode('ascii').rstrip('=')


def _key(secret):
    return base64.b32decode(secret + '=' * (-len(secret) % 8), casefold=True)


def code_for(secret, step):
    digest = hmac.new(_key(secret), struct.pack('>Q', step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = (struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 10 ** DIGITS
    return f'{number:0{DIGITS}d}'


def verify(secret, code, now=None, last_step=0, window=1):
    """The matching time step, or None. A step at or before `last_step` is refused, so a code cannot be reused."""
    code = ''.join(str(code).split())
    if len(code) != DIGITS or not code.isdigit():
        return None
    current = int((time.time() if now is None else now) // STEP_SECONDS)
    for step in range(current - window, current + window + 1):
        if step > last_step and hmac.compare_digest(code_for(secret, step), code):
            return step
    return None


def provisioning_uri(secret, account, issuer):
    return (f'otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret}&issuer={quote(issuer)}'
            f'&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}')
