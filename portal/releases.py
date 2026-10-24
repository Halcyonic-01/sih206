"""Release workflow only: no bank, payment, regulatory eligibility or recommendation stages."""
import hashlib

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .models import Document, Instrument, ReleaseRequest
from .permissions import institution_for, require_authority
from .services import WorkflowError, _compare_and_update, event, snapshot
from .uploads import validate_pdf_upload

# S5-owned extension guard. Existing requests without casework are unchanged.
_OWNED_CASE_TOKEN = object()


def _case_guard(release, token):
    if token is not _OWNED_CASE_TOKEN and hasattr(release, 'casework'):
        raise WorkflowError('Use the casework service so clearance and evidence gates are rechecked.')


def _eligible(instrument):
    if not instrument.is_current:
        raise WorkflowError('Release requires an accepted current instrument.')
    if Instrument.objects.filter(predecessor=instrument).exists():
        raise WorkflowError('An existing renewal proposal blocks release. Continue that renewal instead.')


@transaction.atomic
def request_release(actor, instrument_id, expected_version, reason):
    instrument = Instrument.objects.get(pk=instrument_id, institution=institution_for(actor))
    _eligible(instrument)
    if instrument.has_active_release:
        raise WorkflowError('A pending or authorized release request already exists.')
    if not reason.strip() or len(reason) > 2000:
        raise WorkflowError('A release reason of up to 2000 characters is required.')
    before = snapshot(instrument)
    _compare_and_update(instrument, expected_version)
    release = ReleaseRequest.objects.create(instrument=instrument, requested_by=actor, reason=reason.strip())
    event(instrument, actor, 'RELEASE_REQUESTED', before, reason.strip())
    return release


def _authority_request(actor, instrument_id, release_id):
    require_authority(actor)
    instrument = Instrument.objects.get(pk=instrument_id)
    try:
        release = instrument.release_requests.get(pk=release_id)
    except ReleaseRequest.DoesNotExist:
        raise WorkflowError('This release request does not belong to the instrument.') from None
    if release.requested_by_id == actor.pk:
        raise PermissionDenied('You cannot decide or complete your own release request.')
    _eligible(instrument)
    return instrument, release


@transaction.atomic
def decide_release(actor, instrument_id, release_id, expected_version, decision, reason, *, _casework_token=None):
    instrument, release = _authority_request(actor, instrument_id, release_id)
    _case_guard(release, _casework_token)
    if release.status != ReleaseRequest.Status.PENDING:
        raise WorkflowError('Only a pending request can receive an authority decision.')
    if decision not in ('approve', 'reject') or not reason.strip() or len(reason) > 2000:
        raise WorkflowError('A valid decision and a reason of up to 2000 characters are required.')
    before = snapshot(instrument)
    _compare_and_update(instrument, expected_version)
    release.status = ReleaseRequest.Status.APPROVED if decision == 'approve' else ReleaseRequest.Status.REJECTED
    release.decision_reason = reason.strip()
    release.decided_by = actor
    release.decided_at = timezone.now()
    release.save(update_fields=['status', 'decision_reason', 'decided_by', 'decided_at'])
    event(instrument, actor, 'RELEASE_APPROVED' if decision == 'approve' else 'RELEASE_REJECTED', before, reason.strip())
    return release


def complete_release(actor, instrument_id, release_id, expected_version, notes, document, *, _casework_token=None):
    stored_file = None
    try:
        with transaction.atomic():
            instrument, release = _authority_request(actor, instrument_id, release_id)
            _case_guard(release, _casework_token)
            if release.status != ReleaseRequest.Status.APPROVED:
                raise WorkflowError('Only an authorized release can be completed.')
            if not notes.strip() or len(notes) > 2000 or document is None:
                raise WorkflowError('A completion explanation and a new evidence PDF are required.')
            validate_pdf_upload(document)
            before = snapshot(instrument)
            now = timezone.now()
            _compare_and_update(instrument, expected_version, released_at=now)
            digest = hashlib.sha256()
            for chunk in document.chunks():
                digest.update(chunk)
            document.seek(0)
            evidence = Document(instrument=instrument, kind=Document.Kind.RELEASE_EVIDENCE,
                                original_name=document.name[:255], size_bytes=document.size,
                                sha256=digest.hexdigest(), uploaded_by=actor)
            evidence.file.save(document.name, document, save=False)
            stored_file = evidence.file
            evidence.save()
            release.status = ReleaseRequest.Status.COMPLETED
            release.completion_notes = notes.strip()
            release.completed_by = actor
            release.completed_at = now
            release.completion_evidence = evidence
            release.save(update_fields=['status', 'completion_notes', 'completed_by', 'completed_at', 'completion_evidence'])
            event(instrument, actor, 'RELEASE_COMPLETED', before, notes.strip())
            return release
    except Exception:
        if stored_file:
            stored_file.delete(save=False)
        raise
