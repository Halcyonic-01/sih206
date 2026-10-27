"""Shared bounded PDF checks; not malware scanning or authenticity verification."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from tempfile import SpooledTemporaryFile, TemporaryDirectory

from django.conf import settings
from django.core.exceptions import ValidationError


def validate_pdf_envelope(upload):
    if not upload:
        return None
    if upload.size > settings.MAX_UPLOAD_BYTES:
        raise ValidationError('PDF exceeds the configured upload size limit.')
    if Path(upload.name).suffix.lower() != '.pdf':
        raise ValidationError('Only PDF documents are supported.')
    if upload.content_type not in ('application/pdf', 'application/octet-stream'):
        raise ValidationError('The file type must be PDF.')
    header = upload.read(8)
    upload.seek(max(0, upload.size - 1024))
    trailer = upload.read()
    upload.seek(0)
    if not header.startswith(b'%PDF-') or b'%%EOF' not in trailer:
        raise ValidationError('This file does not have a supported PDF signature.')
    return upload


def validate_pdf_upload(upload):
    """Inspect in a killable process; parsing is not malware/authenticity proof."""
    if not upload:
        return None
    validate_pdf_envelope(upload)
    try:
        with TemporaryDirectory(prefix='fdr-pdf-') as directory:
            path = Path(directory) / 'upload.pdf'
            with path.open('wb') as target:
                for chunk in upload.chunks():
                    target.write(chunk)
            result = subprocess.run(
                [sys.executable, '-I', str(Path(__file__).with_name('pdf_inspect.py')), str(path)],
                capture_output=True, text=True, timeout=10, check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            if result.returncode:
                raise ValidationError('PDF is encrypted, malformed, unsupported or contains active content.')
            count = json.loads(result.stdout)['page_count']
            if type(count) is not int or not 1 <= count <= 1000:
                raise ValueError('Invalid page count')
            upload.validated_page_count = count
    except subprocess.TimeoutExpired:
        raise ValidationError('PDF inspection timed out. Try a simpler document.') from None
    except (OSError, ValueError, KeyError):
        raise ValidationError('PDF inspection is unavailable or returned an invalid result.') from None
    finally:
        upload.seek(0)
    from .scanning import scan_upload
    return scan_upload(upload)  # malware scan after the structure checks; records upload.scan_status


class DocumentIntegrityError(Exception):
    """The stored bytes no longer match the SHA-256 recorded when the document was uploaded."""

    def __init__(self, document, actual_sha256):
        super().__init__(f'Document {document.pk} no longer matches its recorded SHA-256.')
        self.document = document
        self.actual_sha256 = actual_sha256


def open_verified(document):
    """Return the stored file as a seekable file object, after checking it against `document.sha256`.

    The bytes are hashed while they are copied into a temporary file that is then served, so what is checked is
    exactly what is sent (a file swapped on disk between the check and the response cannot slip through).
    Raises FileNotFoundError when the file is missing and DocumentIntegrityError on a mismatch.
    """
    digest = hashlib.sha256()
    copy = SpooledTemporaryFile(max_size=settings.MAX_UPLOAD_BYTES)
    try:
        with document.file.open('rb') as stored:
            for chunk in iter(lambda: stored.read(1024 * 1024), b''):
                digest.update(chunk)
                copy.write(chunk)
    except BaseException:
        copy.close()
        raise
    actual = digest.hexdigest()
    if actual != document.sha256:
        copy.close()
        raise DocumentIntegrityError(document, actual)
    copy.seek(0)
    return copy


def record_integrity_failure(error, actor):
    """Audit and announce a failed check. Call it where the transaction will commit (not before raising)."""
    from notifications.recipients import officers
    from notifications.service import notify
    from . import services
    document = error.document
    item = document.instrument
    services.event(item, actor, 'DOCUMENT_INTEGRITY_FAILED', services.snapshot(item),
                   reason='Stored file does not match the SHA-256 recorded at upload; the download was refused.',
                   after_extra={'document_id': document.pk, 'document_name': document.original_name,
                                'expected_sha256': document.sha256, 'actual_sha256': error.actual_sha256})
    notify(officers(item.institution), 'document_integrity_failed',
           {'reference': item.reference, 'document': document.original_name, 'url': f'/records/{item.pk}'},
           key=f'document:{document.pk}:integrity:{error.actual_sha256[:16]}')
