"""Malware scan of uploaded PDFs through ClamAV's clamd (INSTREAM over TCP), with a fail-closed switch (P2-1).

* `CLAMAV_HOST` set: every upload is streamed to clamd. Infected: the upload is refused and nothing is stored.
  Clean: the document is stored with `scan_status=CLEAN`.
* Scanner unreachable: with `SCAN_REQUIRED=true` the upload is refused ("try again"); with it off the document is stored
  as `PENDING` (not scanned) and stays downloadable. A required deployment never passes a file through unscanned.
* `PENDING` documents are not downloadable, and not sent to OCR or AI, when `SCAN_REQUIRED=true`; `scan_documents` scans them later.

The PDF parser in uploads.py already rejects active content; this adds detection of known malware. It does not prove a
document is genuine.
"""
import socket
import struct

from django.conf import settings
from django.core.exceptions import ValidationError

CHUNK = 64 * 1024


class ScannerUnavailable(Exception):
    pass


def configured():
    return bool(getattr(settings, 'CLAMAV_HOST', ''))


def required():
    return bool(getattr(settings, 'SCAN_REQUIRED', False))


def scan_chunks(chunks):
    """Returns (True, '') when clean or (False, signature) when infected. Raises ScannerUnavailable on any failure."""
    host, port, timeout = settings.CLAMAV_HOST, int(settings.CLAMAV_PORT), float(settings.CLAMAV_TIMEOUT)
    try:
        with socket.create_connection((host, port), timeout=timeout) as connection:
            connection.settimeout(timeout)
            connection.sendall(b'zINSTREAM\0')
            for chunk in chunks:
                for start in range(0, len(chunk), CHUNK):
                    part = chunk[start:start + CHUNK]
                    connection.sendall(struct.pack('>I', len(part)) + part)
            connection.sendall(struct.pack('>I', 0))
            reply = b''
            while not reply.endswith(b'\0') and len(reply) < 4096:
                data = connection.recv(1024)
                if not data:
                    break
                reply += data
    except (OSError, socket.timeout) as exc:
        raise ScannerUnavailable('The malware scanner could not be reached.') from exc
    text = reply.rstrip(b'\0').decode('utf-8', 'replace').strip()
    if text.endswith('OK'):
        return True, ''
    if text.endswith('FOUND'):
        return False, text.removeprefix('stream:').removesuffix('FOUND').strip()[:200]
    raise ScannerUnavailable('The malware scanner returned an unexpected answer.')


def scan_upload(upload):
    """Scan an upload and record the outcome on it (`scan_status`, `scan_detail`). Raises ValidationError to refuse it."""
    upload.scan_status, upload.scan_detail = 'PENDING', ''
    if not configured():
        if required():
            raise ValidationError('Malware scanning is required but no scanner is configured. Contact the portal operator.')
        return upload
    try:
        clean, signature = scan_chunks(upload.chunks())
    except ScannerUnavailable:
        if required():
            raise ValidationError('The malware scanner is not available, so this file cannot be accepted right now. '
                                  'Try again shortly.') from None
        return upload
    finally:
        upload.seek(0)
    if not clean:
        raise ValidationError('This file was rejected by the malware scan. It was not stored.')
    upload.scan_status = 'CLEAN'
    return upload


def scan_fields(upload):
    """Document(...) keyword arguments for the outcome recorded by scan_upload()."""
    from django.utils import timezone
    status = getattr(upload, 'scan_status', 'PENDING')
    return {'scan_status': status, 'scan_detail': getattr(upload, 'scan_detail', ''),
            'scanned_at': timezone.now() if status == 'CLEAN' else None}


def downloadable(document):
    """Whether a stored document may be served, sent to OCR or AI."""
    if document.scan_status == 'REJECTED':
        return False
    return document.scan_status == 'CLEAN' or not required()
