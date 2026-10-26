"""Encrypted document storage: AES-256-GCM per file, with the file key wrapped by a master key (P1-2).

File layout (all on disk, nothing else is stored elsewhere):

    MAGIC (8) | key id (4) | wrapped length (2, big endian) | wrapped data key | nonce (12) | ciphertext + tag

* Every file gets its own random 256-bit data key. The data key is wrapped (AES-256-GCM) by a master key from
  `DOCUMENT_ENCRYPTION_KEY`. The 4-byte key id is the start of SHA-256 of the master key, so older master keys listed in
  `DOCUMENT_ENCRYPTION_OLD_KEYS` can still open files until they are re-wrapped (`encrypt_documents`).
* The storage name is part of the authenticated data of the body, so an encrypted file copied over another record's file fails to open.
* `Document.sha256` stays the hash of the plaintext, so integrity checks and de-duplication are unchanged.
* Reads return the decrypted bytes in memory (uploads are limited to `MAX_UPLOAD_MB`). Files written before encryption
  was switched on are served as they are unless `DOCUMENT_ALLOW_PLAINTEXT=false`; `encrypt_documents` converts them.

This protects a copied disk, backup or volume snapshot. It does not protect against someone who can read both the files and
the master key (for example on the same server); put the key in a secret store or KMS, not next to the data.
"""
import os
import struct

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage

from config.documentkey import generate_key, key_id, parse_key  # noqa: F401 (generate_key is re-exported for operators)

MAGIC = b'PRMNENC1'
NONCE = 12


class DocumentDecryptionError(Exception):
    """The file is not readable with the configured keys, or was altered or moved."""


def _aead(key):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(key)


def keyring():
    """(current master key, {key id: master key}) from settings."""
    current = parse_key(settings.DOCUMENT_ENCRYPTION_KEY)
    ring = {key_id(current): current}
    for old in getattr(settings, 'DOCUMENT_ENCRYPTION_OLD_KEYS', ()):
        master = parse_key(old)
        ring.setdefault(key_id(master), master)
    return current, ring


def is_encrypted(blob):
    return blob.startswith(MAGIC)


def encrypt(name, plaintext, master=None):
    master = master or keyring()[0]
    kid = key_id(master)
    data_key, wrap_nonce, nonce = os.urandom(32), os.urandom(NONCE), os.urandom(NONCE)
    wrapped = wrap_nonce + _aead(master).encrypt(wrap_nonce, data_key, MAGIC + kid)
    header = MAGIC + kid + struct.pack('>H', len(wrapped)) + wrapped
    return header + nonce + _aead(data_key).encrypt(nonce, plaintext, MAGIC + name.encode('utf-8'))


def _open_header(blob, ring):
    try:
        kid = blob[8:12]
        (length,) = struct.unpack('>H', blob[12:14])
        wrapped = blob[14:14 + length]
        master = ring[kid]
        data_key = _aead(master).decrypt(wrapped[:NONCE], wrapped[NONCE:], MAGIC + kid)
    except Exception as exc:  # unknown key id, truncated header or a failed unwrap
        raise DocumentDecryptionError('The document key is unknown or the file header is damaged.') from exc
    return kid, data_key, 14 + length


def decrypt(name, blob, ring=None):
    ring = ring or keyring()[1]
    kid, data_key, start = _open_header(blob, ring)
    nonce, body = blob[start:start + NONCE], blob[start + NONCE:]
    try:
        return _aead(data_key).decrypt(nonce, body, MAGIC + name.encode('utf-8'))
    except Exception as exc:
        raise DocumentDecryptionError('The file was altered, truncated or belongs to a different storage name.') from exc


def rewrap(blob, name, ring=None, master=None):
    """Wrap the same data key under the current master key; the encrypted body is not touched.

    Returns the new bytes, or None when the file is already under the current key.
    """
    current, known = keyring()
    ring, master = ring or known, master or current
    kid, data_key, start = _open_header(blob, ring)
    if kid == key_id(master):
        return None
    new_kid, wrap_nonce = key_id(master), os.urandom(NONCE)
    wrapped = wrap_nonce + _aead(master).encrypt(wrap_nonce, data_key, MAGIC + new_kid)
    return MAGIC + new_kid + struct.pack('>H', len(wrapped)) + wrapped + blob[start:]


class EncryptedFileSystemStorage(FileSystemStorage):
    def _save(self, name, content):
        content.seek(0)
        plaintext = content.read()
        saved = super()._save(name, ContentFile(encrypt(name, plaintext)))
        if saved != name:  # a name collision was resolved by the parent: bind the bytes to the final name
            with open(self.path(saved), 'wb') as target:
                target.write(encrypt(saved, plaintext))
        return saved

    def _open(self, name, mode='rb'):
        if mode != 'rb':
            raise ValueError('Encrypted documents are read-only.')
        with super()._open(name, 'rb') as stored:
            blob = stored.read()
        if is_encrypted(blob):
            return ContentFile(decrypt(name, blob), name=name)
        if not getattr(settings, 'DOCUMENT_ALLOW_PLAINTEXT', True):
            raise DocumentDecryptionError('This document is not encrypted and plaintext files are not allowed.')
        return ContentFile(blob, name=name)

    def raw_bytes(self, name):
        with super()._open(name, 'rb') as stored:
            return stored.read()

    def replace_raw(self, name, blob):
        """Atomically replace the stored bytes of an existing file (used by encrypt_documents)."""
        path = self.path(name)
        temporary = f'{path}.tmp-{os.getpid()}'
        with open(temporary, 'wb') as target:
            target.write(blob)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
