"""Trusted release adapters (K8 integration of S5).

The release service fails closed until these ports are configured (casework/facts.py). They build the facts only
from server-held records: the holding and its typed documents, which the PDF validator (Y2) already parsed;
the obligation; and the Affidavit-6 answers the institution records with its request. Nothing is inferred
from bank data. The rule payload stays a draft (DRAFT_DEMO_NOT_APPROVED) and every outcome still needs a person.
"""
import re

from django.core.exceptions import ValidationError
from django.utils import timezone

# Versioned so a stored case can tell which questions were answered (template_ref on ReleaseCase).
AFFIDAVIT_6 = {
    'version': 'APH-AFFIDAVIT-6-DEMO-v1',
    'questions': [
        {'id': 'no_trustee_dispute', 'label': 'There is no dispute among the trustees or members of the society, trust or company.'},
        {'id': 'no_financial_embezzlement', 'label': 'No case of financial embezzlement is pending against the institution or its trust.'},
        {'id': 'no_pending_complaints', 'label': 'No complaint against the institution is pending with AICTE or any other authority.'},
        {'id': 'no_pending_proceedings', 'label': 'No disciplinary or legal proceedings are pending against the institution.'},
        {'id': 'student_dues_settled', 'label': 'All dues of students and staff are settled and fees of students who left are refunded.'},
        {'id': 'information_true', 'label': 'The information and documents submitted with this request are true and complete.'},
    ],
}
QUESTION_IDS = [question['id'] for question in AFFIDAVIT_6['questions']]

# Release checklist names (rule payload) -> typed document kinds held on the record.
DOCUMENT_KINDS = {
    'REQUEST_LETTER': 'REQUEST_LETTER', 'AFFIDAVIT_6': 'AFFIDAVIT_6', 'LATEST_LOA_EOA': 'APPROVAL_LETTER',
    'FDR': 'FDR', 'PAYMENT_PROOF': 'PAYMENT_PROOF', 'RPGF_PROOF': 'RPGF_PROOF',
    'NO_STUDENTS_CERTIFICATE': 'STUDENT_CLEARANCE', 'EXTERNAL_NOC': 'EXTERNAL_NOC',
}
EVIDENCE_REFERENCE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9 /_.:#-]{2,199}$')


def release_payload(obligation):
    return obligation.rule_version.payload['release']


def required_documents(obligation, mode, path):
    """Checklist names for this path and deposit mode, in display order."""
    payload = release_payload(obligation)
    names = list(payload['common_documents']) + [payload['mode_documents'][mode]]
    conditional = payload.get('conditional_documents', {}).get(path)
    if conditional:
        names.append(conditional['document'])
    return names


def _answer(declarations, key):
    value = declarations.get(key)
    return value if type(value) is bool else None


def _active_case(instrument):
    from obligations.models import ReleaseCase
    return (ReleaseCase.objects.filter(release__instrument=instrument, release__status__in=['PENDING', 'APPROVED'])
            .order_by('-pk').first())


def document_facts(instrument, obligation, path):
    """Latest typed document per checklist entry.

    Documents that were part of the accepted record were reviewed by the officer at acceptance. Documents added
    for the release application are reviewed in the officer's checklist and penalty review of the case.
    """
    case = _active_case(instrument)
    officer_checked = bool(case and case.penalty_review_complete)
    accepted_at = (instrument.audit_events.filter(action='ACCEPTED').order_by('-created_at')
                   .values_list('created_at', flat=True).first())
    wanted = set(required_documents(obligation, instrument.mode, path)) | {'NO_STUDENTS_CERTIFICATE', 'EXTERNAL_NOC'}
    facts = {}
    for name in sorted(wanted):
        document = instrument.documents.filter(kind=DOCUMENT_KINDS[name]).order_by('-created_at', '-pk').first()
        if document is None:
            continue
        reviewed = officer_checked or (accepted_at is not None and document.created_at <= accepted_at)
        facts[name] = {'ref': f'DOC-{document.pk}', 'institution_id': instrument.institution_id,
            'instrument_id': instrument.pk,
            'review_status': 'REVIEWED_SYNTHETIC_METADATA' if reviewed else 'SUBMITTED_FOR_REVIEW',
            'parse_status': 'VALID_SYNTHETIC_METADATA' if document.page_count else 'UNPARSED'}
    return facts


def release_facts(*, actor, instrument, obligation, path, declarations):
    today = timezone.localdate()
    answers = {key: _answer(declarations, key) for key in QUESTION_IDS}
    documents = document_facts(instrument, obligation, path)
    embezzlement = None if answers['no_financial_embezzlement'] is None else not answers['no_financial_embezzlement']
    consistency = (None if answers['information_true'] is None or 'AFFIDAVIT_6' not in documents
                   else 'MATCHES_SYNTHETIC_REVIEW' if answers['information_true'] else 'CONTRADICTS_DECLARATION')
    negate = lambda key: None if answers[key] is None else not answers[key]  # noqa: E731
    return {
        # actor, case identities, instrument, clearances, penalties, letter and monitoring are overwritten by the
        # release service from its own records; they are listed so the snapshot shape is complete.
        'actor': {'id': actor.pk, 'role_label': '', 'scope_institution_ids': []},
        'case': {'id': 1, 'institution_id': instrument.institution_id, 'instrument_id': instrument.pk,
                 'requester_id': actor.pk, 'version': 1, 'expected_version': 1, 'assessment_version': 1,
                 'status': 'PENDING', 'path': path, 'mode': instrument.mode, 'other_active_release': False},
        'instrument': {'id': instrument.pk, 'institution_id': instrument.institution_id, 'status': instrument.status,
                       'superseded': instrument.is_superseded, 'released': instrument.is_released,
                       'maturity_date': instrument.maturity_date.isoformat(), 'successor_proposal_exists': False},
        'obligation': {'id': obligation.pk, 'institution_id': obligation.institution_id,
                       'term_end': obligation.term_end.isoformat() if obligation.term_end else None,
                       'term_elapsed_reviewed': bool(obligation.term_end and obligation.term_end < today)},
        'basis': {'closure_order_ref': None, 'merger_order_ref': None, 'conversion_order_ref': None,
                  'deposit_matured_for_exception': instrument.maturity_date <= today,
                  'certificate_exception_reviewed': False, 'child_institution_ids': [],
                  'child_scope_complete': path != 'MERGER', 'child_certificates': {}},
        'document_context_complete': True,
        'documents': documents,
        'affidavit_review': {'template_ref': AFFIDAVIT_6['version'],
            'all_required_answers_recorded': all(value is not None for value in answers.values()),
            'signed_pdf_consistency': consistency, 'reviewed': 'AFFIDAVIT_6' in documents},
        'clearance_context_complete': True,
        'required_units': list(release_payload(obligation)['clearance_units']),
        'clearances': {},
        'holds': {'trustee_dispute': negate('no_trustee_dispute'), 'financial_embezzlement': embezzlement,
                  'pending_complaints': negate('no_pending_complaints'),
                  'pending_disciplinary_proceedings': negate('no_pending_proceedings'),
                  'external_noc_status': ('NOT_REQUIRED' if not embezzlement else
                                          'REVIEWED_SYNTHETIC_NOC' if 'EXTERNAL_NOC' in documents else 'REQUIRED')},
        'penalty_review': {'status': None, 'assessments': []},
        'letter': {'state': 'NOT_ISSUED', 'kind': None, 'ref': None, 'digitally_signed': False},
        'completion': {'new_evidence_ref': None, 'evidence_is_new': False, 'parse_status': None, 'notes': None,
                       'refund_reference': None},
        'decision_reason': None,
        'monitoring_active': instrument.is_current,
    }


def clearance_evidence(actor, task, evidence_ref):
    """A clearance unit cites its own file or note number; the service has already checked the unit assignment."""
    return type(evidence_ref) is str and bool(EVIDENCE_REFERENCE.match(evidence_ref.strip()))


def completion_validator(upload):
    """The same bounded PDF parser as every other upload (Y2). Raises ValidationError for a bad file."""
    from portal.uploads import validate_pdf_upload
    validate_pdf_upload(upload)
    if not getattr(upload, 'validated_page_count', None):
        raise ValidationError('Completion PDF could not be parsed.')
    return True


def requirements(actor, instrument, obligation, path):
    """What the request wizard shows: questionnaire, document checklist and whether a request can be made."""
    documents = document_facts(instrument, obligation, path)
    checklist = [{'name': name, 'kind': DOCUMENT_KINDS[name], 'present': name in documents,
                  'parsed': name in documents and documents[name]['parse_status'] == 'VALID_SYNTHETIC_METADATA'}
                 for name in required_documents(obligation, instrument.mode, path)]
    eligible = (instrument.status == 'ACCEPTED' and instrument.is_current and not instrument.has_active_release
                and instrument.obligation_id == obligation.pk)
    return {'questionnaire': AFFIDAVIT_6, 'paths': list(release_payload(obligation)['paths']), 'path': path,
            'mode': instrument.mode, 'documents': checklist, 'documents_ready': all(d['parsed'] for d in checklist),
            'eligible': eligible, 'instrument_version': instrument.version,
            'term_end': obligation.term_end, 'term_elapsed': bool(obligation.term_end and obligation.term_end < timezone.localdate()),
            'simulation_label': 'SIMULATED', 'policy_label': 'DRAFT_DEMO_NOT_APPROVED'}
