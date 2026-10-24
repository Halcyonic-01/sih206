"""Shared bounded PDF checks; not malware scanning or authenticity verification."""
from pathlib import Path
import json
import subprocess
import sys
from tempfile import TemporaryDirectory

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
    return upload
