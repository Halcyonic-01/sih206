"""Y3 mutation services shared by REST endpoints and future callers."""
import hashlib

from django.core.exceptions import ValidationError
from django.db import transaction

from . import services
from .models import Document, Instrument
from .permissions import require_officer, scoped_instruments
from .scanning import scan_fields
from .uploads import validate_pdf_upload

# APH 6.46 application documents an institution adds to an accepted holding before it requests release.
RELEASE_APPLICATION_KINDS = (Document.Kind.REQUEST_LETTER, Document.Kind.AFFIDAVIT_6, Document.Kind.APPROVAL_LETTER,
                             Document.Kind.STUDENT_CLEARANCE, Document.Kind.EXTERNAL_NOC)


def release_documents_allowed(item):
    return item.is_current and not item.has_active_release


@transaction.atomic
def correct_record(actor, pk, version, changes, reason):
    require_officer(actor)
    item = scoped_instruments(actor).get(pk=pk)
    if actor.pk == item.created_by_id:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('You cannot correct your own submission.')
    if item.status != Instrument.Status.SUBMITTED:
        raise services.WorkflowError('Only submitted records can receive an officer correction.')
    if not reason.strip():
        raise ValidationError({'reason': 'A correction reason is required.'})
    before = services.snapshot(item)
    allowed = {'reference', 'bank', 'amount_paise', 'issue_date', 'maturity_date',
               'ifsc', 'branch', 'holder_names', 'utr', 'lien_marked', 'mode', 'obligation'}
    if not changes or set(changes) - allowed:
        raise ValidationError('No valid correction fields supplied.')
    for key, value in changes.items():
        setattr(item, key, value)
    changes['verification_level'] = Instrument.VerificationLevel.DECLARED
    item.full_clean()
    services._compare_and_update(item, version, **changes)
    services.event(item, actor, 'OFFICER_CORRECTION', before, reason.strip())
    return item


def upload_document(actor, pk, version, upload, kind):
    """Retain evidence; institutions upload only to their editable records."""
    from .permissions import institution_for
    institution = institution_for(actor)
    if kind not in Document.Kind.values or kind in (Document.Kind.NOC, Document.Kind.SANCTION_ORDER,
                                                   Document.Kind.RELEASE_EVIDENCE):
        raise ValidationError({'kind': 'This document category is not available for institution uploads.'})
    validate_pdf_upload(upload)
    stored_file = None
    try:
        with transaction.atomic():
            item = Instrument.objects.get(pk=pk, institution=institution)
            editable = item.status in (Instrument.Status.DRAFT, Instrument.Status.CHANGES_REQUESTED)
            if not editable and not (kind in RELEASE_APPLICATION_KINDS and release_documents_allowed(item)):
                raise services.WorkflowError('Documents can only be added to editable records, or release '
                                             'application documents to a current accepted record.')
            before = services.snapshot(item)
            # A release application document adds evidence; it does not change the deposit's declared facts.
            changes = {'verification_level': Instrument.VerificationLevel.DECLARED} if editable else {}
            services._compare_and_update(item, version, **changes)
            digest = hashlib.sha256()
            for chunk in upload.chunks():
                digest.update(chunk)
            upload.seek(0)
            document = Document(instrument=item, kind=kind, uploaded_by=actor,
                original_name=upload.name[:255], size_bytes=upload.size,
                sha256=digest.hexdigest(), page_count=upload.validated_page_count, **scan_fields(upload))
            document.file.save(upload.name, upload, save=False)
            stored_file = document.file
            document.save()
            services.event(item, actor, 'DOCUMENT_UPLOADED', before)
            return item
    except Exception:
        if stored_file:
            stored_file.delete(save=False)
        raise
