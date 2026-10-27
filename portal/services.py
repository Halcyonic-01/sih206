import hashlib

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import AuditEvent, Document, Instrument, ReleaseRequest, ReviewObservation
from .permissions import institution_for, require_officer
from .validation import checks_snapshot, run_checks, check_document_present
from .scanning import scan_fields
from .uploads import validate_pdf_upload


class WorkflowError(Exception):
    pass


def snapshot(instrument):
    return {
        'reference': instrument.reference, 'bank': instrument.bank,
        'obligation_id': instrument.obligation_id, 'mode': instrument.mode,
        'ifsc': instrument.ifsc, 'branch': instrument.branch,
        'holder_names': instrument.holder_names, 'utr': instrument.utr,
        'lien_marked': instrument.lien_marked,
        'verification_level': instrument.verification_level,
        'amount_paise': instrument.amount_paise,
        'issue_date': instrument.issue_date.isoformat(),
        'maturity_date': instrument.maturity_date.isoformat(),
        'status': instrument.status, 'version': instrument.version,
        'predecessor_id': instrument.predecessor_id,
        'superseded_at': instrument.superseded_at.isoformat() if instrument.superseded_at else None,
        'released_at': instrument.released_at.isoformat() if instrument.released_at else None,
        'document_ids': list(instrument.documents.order_by('pk').values_list('pk', flat=True)),
        'observations': [observation_snapshot(observation) for observation in instrument.observations.all()],
        'release_requests': [release_snapshot(release) for release in instrument.release_requests.order_by('pk')],
    }


def observation_snapshot(observation):
    return {
        'id': observation.pk, 'document_id': observation.document_id,
        'page_number': observation.page_number, 'severity': observation.severity,
        'comment': observation.comment, 'reviewer_id': observation.reviewer_id,
        'created_at': observation.created_at.isoformat(), 'resolution': observation.resolution,
        'resolved_by_id': observation.resolved_by_id,
        'resolved_at': observation.resolved_at.isoformat() if observation.resolved_at else None,
    }


def release_snapshot(release):
    return {
        'id': release.pk, 'status': release.status, 'reason': release.reason,
        'requested_by_id': release.requested_by_id, 'created_at': release.created_at.isoformat(),
        'decision_reason': release.decision_reason, 'decided_by_id': release.decided_by_id,
        'decided_at': release.decided_at.isoformat() if release.decided_at else None,
        'completion_notes': release.completion_notes, 'completed_by_id': release.completed_by_id,
        'completed_at': release.completed_at.isoformat() if release.completed_at else None,
        'completion_evidence_id': release.completion_evidence_id,
    }


def event(instrument, actor, action, before, reason='', after_extra=None):
    after = snapshot(instrument)
    if after_extra:
        after.update(after_extra)
    AuditEvent.objects.create(instrument=instrument, actor=actor, action=action,
                              reason=reason, before=before, after=after)
    template = {'SUBMITTED': 'record_submitted', 'ACCEPTED': 'record_reviewed',
                'CHANGES_REQUESTED': 'record_reviewed'}.get(action)
    if template:
        from .notification_hook import notify_record
        instrument._notification_queued = notify_record(instrument, template)


def _compare_and_update(instrument, expected_version, **changes):
    if instrument.version != expected_version:
        raise WorkflowError('This record changed. Reload it before trying again.')
    changed = Instrument.objects.filter(pk=instrument.pk, version=expected_version).update(
        **changes, version=F('version') + 1, updated_at=timezone.now())
    if not changed:
        raise WorkflowError('This record changed. Reload it before trying again.')
    instrument.refresh_from_db()


def _current_predecessor(instrument):
    try:
        instrument.validate_lineage()
    except ValidationError:
        raise WorkflowError('The renewal lineage is invalid. Contact the portal operator.') from None
    predecessor = Instrument.objects.get(pk=instrument.predecessor_id)
    if not predecessor.is_current:
        raise WorkflowError('The predecessor must still be an accepted current instrument.')
    if predecessor.has_active_release:
        raise WorkflowError('A pending or authorized release blocks this renewal.')
    return predecessor


def save_draft(actor, cleaned, instrument_id=None, predecessor_id=None):
    institution = institution_for(actor)
    stored_file = None
    try:
        with transaction.atomic():
            predecessor = None
            if predecessor_id is not None:
                if instrument_id is not None:
                    raise WorkflowError('Existing instruments cannot be reparented.')
                predecessor = Instrument.objects.get(pk=predecessor_id, institution=institution)
                if not predecessor.is_current:
                    raise WorkflowError('Only an accepted current instrument can start a renewal.')
                if predecessor.has_active_release:
                    raise WorkflowError('A pending or authorized release blocks this renewal.')
                if Instrument.objects.filter(predecessor_id=predecessor.pk).exists():
                    raise WorkflowError('A successor proposal already exists. Continue that record instead.')
                predecessor_before = snapshot(predecessor)
                # Serializes competing creation requests; the one-to-one DB constraint is a second guard.
                _compare_and_update(predecessor, cleaned['predecessor_version'])
            values = {key: cleaned[key] for key in ('reference', 'bank', 'issue_date', 'maturity_date')}
            values['amount_paise'] = int(cleaned['amount'] * 100)
            for key in ('obligation', 'mode', 'ifsc', 'branch', 'holder_names', 'utr', 'lien_marked'):
                if key in cleaned:
                    values[key] = cleaned[key]
            if instrument_id:
                values['verification_level'] = Instrument.VerificationLevel.DECLARED
            if instrument_id:
                instrument = Instrument.objects.get(pk=instrument_id, institution=institution)
                if instrument.status not in (Instrument.Status.DRAFT, Instrument.Status.CHANGES_REQUESTED):
                    raise WorkflowError('Only drafts and records awaiting correction can be edited.')
                if instrument.predecessor_id:
                    _current_predecessor(instrument)
                before = snapshot(instrument)
                candidate = Instrument.objects.get(pk=instrument.pk)
                for key, value in values.items():
                    setattr(candidate, key, value)
                candidate.full_clean()
                _compare_and_update(instrument, cleaned['version'], **values)
                action = 'DRAFT_UPDATED'
            else:
                instrument = Instrument(institution=institution, created_by=actor,
                                        predecessor=predecessor, **values)
                instrument.full_clean()
                instrument.save()
                before, action = {}, 'DRAFT_CREATED'
            upload = cleaned.get('document')
            if upload:
                validate_pdf_upload(upload)
                digest = hashlib.sha256()
                for chunk in upload.chunks():
                    digest.update(chunk)
                upload.seek(0)
                document = Document(instrument=instrument, uploaded_by=actor,
                                    original_name=upload.name[:255], size_bytes=upload.size,
                                    sha256=digest.hexdigest(), page_count=upload.validated_page_count,
                                    **scan_fields(upload),
                                    kind={'FDR': Document.Kind.FDR, 'RTGS': Document.Kind.PAYMENT_PROOF,
                                          'RPGF': Document.Kind.RPGF_PROOF}[instrument.mode])
                document.file.save(upload.name, upload, save=False)
                stored_file = document.file
                document.save()
            if predecessor:
                reason = cleaned.get('renewal_reason') or 'ROUTINE_RENEWAL'
                note = (cleaned.get('renewal_note') or '').strip()
                if reason == 'OTHER' and not note:
                    raise WorkflowError('Say why this deposit replaces the earlier one.')
                event(instrument, actor, action, before, reason=note,
                      after_extra={'renewal_link': {'predecessor_id': predecessor.pk, 'reason': reason, 'note': note}})
            else:
                event(instrument, actor, action, before)
            if predecessor:
                # Do not expose the private draft's reference/ID/document through the parent's audit.
                event(predecessor, actor, 'RENEWAL_STARTED', predecessor_before,
                      'A successor draft was opened. This instrument remains current pending acceptance.')
            return instrument
    except Exception:
        if stored_file:
            stored_file.delete(save=False)
        raise


@transaction.atomic
def submit(actor, instrument_id, expected_version):
    instrument = Instrument.objects.get(pk=instrument_id, institution=institution_for(actor))
    if instrument.status not in (Instrument.Status.DRAFT, Instrument.Status.CHANGES_REQUESTED):
        raise WorkflowError('Only a draft or corrected record can be submitted.')
    if check_document_present(instrument):
        raise WorkflowError('Upload an FDR PDF before submitting.' if instrument.mode == 'FDR'
                            else 'Upload the deposit-mode supporting PDF before submitting.')
    if instrument.predecessor_id:
        _current_predecessor(instrument)
    before = snapshot(instrument)
    _compare_and_update(instrument, expected_version, status=Instrument.Status.SUBMITTED)
    event(instrument, actor, 'SUBMITTED', before, after_extra=checks_snapshot(instrument))
    return instrument


@transaction.atomic
def review(actor, instrument_id, expected_version, decision, reason):
    require_officer(actor)
    instrument = Instrument.objects.get(pk=instrument_id)
    if actor.pk == instrument.created_by_id:
        raise PermissionDenied('You cannot review your own submission.')
    if instrument.status != Instrument.Status.SUBMITTED:
        raise WorkflowError('Only submitted records can be reviewed.')
    if decision not in ('accept', 'changes') or not reason.strip():
        raise WorkflowError('A valid decision and reason are required.')
    predecessor = None
    if decision == 'accept':
        if instrument.observations.filter(severity=ReviewObservation.Severity.BLOCKING,
                                           resolved_at__isnull=True).exists():
            raise WorkflowError('Resolve all blocking observations before accepting this record.')
        if any(finding.severity == 'blocking' for finding in run_checks(instrument)):
            raise WorkflowError('Resolve blocking technical findings before accepting this record.')
        if instrument.predecessor_id:
            predecessor = _current_predecessor(instrument)
            if predecessor.created_by_id == actor.pk:
                raise PermissionDenied('You cannot approve a renewal of your own original submission.')
            predecessor_before = snapshot(predecessor)
    before = snapshot(instrument)
    status = Instrument.Status.ACCEPTED if decision == 'accept' else Instrument.Status.CHANGES_REQUESTED
    _compare_and_update(instrument, expected_version, status=status)
    if decision == 'accept':
        from django.apps import apps
        if apps.is_installed('verification'):
            from verification.services import record_review
            record_review(actor, instrument, reason)
    if predecessor:
        _compare_and_update(predecessor, predecessor.version, superseded_at=timezone.now())
        event(predecessor, actor, 'SUPERSEDED', predecessor_before, reason,
              after_extra={'accepted_successor_id': instrument.pk})
    event(instrument, actor, 'ACCEPTED' if decision == 'accept' else 'CHANGES_REQUESTED', before, reason,
          after_extra=checks_snapshot(instrument))
    return instrument


def _scrutiny_instrument(actor, instrument_id):
    require_officer(actor)
    instrument = Instrument.objects.get(pk=instrument_id)
    if actor.pk == instrument.created_by_id:
        raise PermissionDenied('You cannot scrutinize your own submission.')
    if instrument.status != Instrument.Status.SUBMITTED:
        raise WorkflowError('Observations can only be added or resolved while the record is submitted.')
    return instrument


@transaction.atomic
def add_observation(actor, instrument_id, expected_version, document, page_number, severity, comment):
    instrument = _scrutiny_instrument(actor, instrument_id)
    if not instrument.documents.filter(pk=document.pk).exists():
        raise WorkflowError('Choose a document attached to this instrument.')
    if severity not in ReviewObservation.Severity.values or not comment.strip():
        raise WorkflowError('A valid severity and comment are required.')
    if page_number is not None and page_number < 1:
        raise WorkflowError('Page references start at 1.')
    document = instrument.documents.get(pk=document.pk)
    if page_number is not None and document.page_count is not None and page_number > document.page_count:
        raise WorkflowError('The page reference exceeds the document page count.')
    before = snapshot(instrument)
    _compare_and_update(instrument, expected_version)
    observation = ReviewObservation.objects.create(
        instrument=instrument, document=document, reviewer=actor, page_number=page_number,
        severity=severity, comment=comment.strip(),
    )
    event(instrument, actor, 'OBSERVATION_ADDED', before, comment.strip())
    return observation


@transaction.atomic
def resolve_observation(actor, instrument_id, observation_id, expected_version, resolution):
    instrument = _scrutiny_instrument(actor, instrument_id)
    try:
        observation = instrument.observations.get(pk=observation_id)
    except ReviewObservation.DoesNotExist:
        raise WorkflowError('This observation does not belong to the instrument.')
    if observation.is_resolved:
        raise WorkflowError('This observation has already been resolved.')
    if not resolution.strip():
        raise WorkflowError('A resolution explanation is required.')
    before = snapshot(instrument)
    _compare_and_update(instrument, expected_version)
    observation.resolution = resolution.strip()
    observation.resolved_by = actor
    observation.resolved_at = timezone.now()
    observation.save(update_fields=['resolution', 'resolved_by', 'resolved_at'])
    event(instrument, actor, 'OBSERVATION_RESOLVED', before, resolution.strip())
    return observation
