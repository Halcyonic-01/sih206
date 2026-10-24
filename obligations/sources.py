"""Saksham's read-only adapters over actual Y1/Y2/Y3 records.

Uploaded/parsed document metadata is evidence for human inspection, not a reviewed
receipt date, bank authenticity or a statement that the document satisfies a rule.
"""
from django.shortcuts import get_object_or_404
from portal.models import Instrument, Document
from portal.permissions import scoped_instruments, scoped_documents
from .calculations import HoldingInput


def scoped_obligation(actor, obligation):
    from .services import scoped_obligations
    return get_object_or_404(scoped_obligations(actor), pk=obligation.pk)


def require_link():
    from .services import DependencyUnavailable
    field = next((field for field in Instrument._meta.fields if field.name == 'obligation'), None)
    if field is None or field.related_model._meta.label != 'obligations.DepositObligation':
        raise DependencyUnavailable('Y1_OBLIGATION_LINK_UNAVAILABLE')


def linked_holdings(actor, obligation):
    from .services import DependencyUnavailable
    obligation = scoped_obligation(actor, obligation)
    require_link()
    records = scoped_instruments(actor).filter(obligation_id=obligation.pk).order_by('pk')
    result = []
    for item in records:
        if item.institution_id != obligation.institution_id:
            raise DependencyUnavailable('INCONSISTENT_LINKED_HOLDING')
        result.append(HoldingInput(id=item.pk, institution_id=item.institution_id,
            obligation_id=item.obligation_id, amount_paise=item.amount_paise,
            issue_date=item.issue_date, maturity_date=item.maturity_date, status=str(item.status),
            superseded=item.superseded_at is not None, released=item.released_at is not None))
    # A complete scoped query returning no records is known empty, not a missing FK.
    return tuple(result)


def proof_evidence(actor, obligation):
    obligation = scoped_obligation(actor, obligation)
    require_link()
    records = scoped_documents(actor).filter(instrument__obligation_id=obligation.pk,
        instrument__institution_id=obligation.institution_id,
        kind__in=[Document.Kind.FDR, Document.Kind.PAYMENT_PROOF, Document.Kind.RPGF_PROOF,
                  Document.Kind.AFFIDAVIT_3]).order_by('pk')
    return [{
        'document_id': document.pk, 'instrument_id': document.instrument_id, 'kind': document.kind,
        'page_count': document.page_count, 'sha256': document.sha256,
        'uploaded_at': document.created_at.isoformat(), 'received_on': None,
        'download_path': f'/api/documents/{document.pk}/download/',
        'page_reference': 1 if document.page_count else None,
        'status': 'STORED_METADATA_ONLY',
    } for document in records]
