"""Shared bounded PDF checks; not malware scanning or authenticity verification."""
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError


def validate_pdf_upload(upload):
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
