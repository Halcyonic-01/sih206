"""An auditor reads document metadata and hashes freely, but a file only with a recorded reason (P2-10)."""
from django.conf import settings
from django.core.exceptions import PermissionDenied

from .permissions import role

MIN_REASON, MAX_REASON = 10, 300


class DownloadReasonRequired(PermissionDenied):
    code = 'download_reason_required'


def reason_for(request):
    """The auditor's stated reason for this download (None for every other role). Raises when an auditor gives none."""
    if role(request.user) != 'auditor':
        return None
    http = getattr(request, '_request', request)
    reason = ' '.join((http.GET.get('reason') or http.headers.get('X-Download-Reason') or '').split())
    if not MIN_REASON <= len(reason) <= MAX_REASON:
        raise DownloadReasonRequired(f'Say why you need the file ({MIN_REASON} to {MAX_REASON} characters), for example '
                                     '?reason=Annual audit sample 12. The reason is written to the access log.')
    return reason


def log_detail(document, reason):
    detail = f'instrument={document.instrument_id}'
    return f'{detail}; auditor reason: {reason}' if reason else detail


def announce(document, user, reason):
    """Optional notice to the dealing officers (AUDITOR_DOWNLOAD_NOTIFY); idempotent per document, auditor and reason."""
    if not reason or not getattr(settings, 'AUDITOR_DOWNLOAD_NOTIFY', False):
        return
    import hashlib
    from notifications.recipients import officers
    from notifications.service import notify
    item = document.instrument
    notify(officers(item.institution), 'auditor_document_download',
           {'reference': item.reference, 'auditor': user.get_username(), 'reason': reason, 'url': f'/records/{item.pk}'},
           key=f'auditor-download:{document.pk}:{user.pk}:{hashlib.sha256(reason.encode()).hexdigest()[:12]}')
