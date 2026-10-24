"""Audited owned release workflow; missing trusted integration ports fail closed."""
from copy import deepcopy
import hashlib
import secrets
from urllib.parse import urlparse
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone

from portal import releases as legacy
from portal.models import Instrument
from portal.permissions import institution_for, require_authority, require_officer, role, scoped_instruments
from portal.services import WorkflowError
from portal.services import _compare_and_update, event, snapshot as instrument_snapshot
from obligations.calculations import penalty_proposal
from obligations.models import ClearanceTask, DepositObligation, IssuedLetter, MasterAudit, PenaltyAssessment, ReleaseCase
from obligations.release_prerequisites import evaluate_prerequisites, PrerequisiteInputError, SECTIONS, TOP
from obligations.rules import rule_snapshot
from obligations.services import DependencyUnavailable, expected_version, reason_text
from .letters import render_letter

PATHS = {'TERM_COMPLETE', 'PROGRESSIVE_CLOSURE', 'MERGER', 'CONVERSION_TO_UNIVERSITY', 'CLOSURE_BY_AICTE'}


def scoped_cases(actor):
    return ReleaseCase.objects.filter(release__instrument__in=scoped_instruments(actor))


def get_case(actor, pk):
    return get_object_or_404(scoped_cases(actor).select_related('release__instrument', 'obligation', 'rule_version'), pk=pk)


def record(case, actor, action, reason):
    MasterAudit.objects.create(institution_id=case.institution_id, actor=actor,
        entity='releasecase', entity_id=case.pk, action=action, reason=reason,
        before=getattr(case, '_audit_before', {}), after=case_snapshot(case))
    # TODO(K5): configured adapter MUST enqueue in the same DB transaction,
    # never send external mail inline. Missing hook is not simulated delivery.
    enqueue = getattr(settings, 'SAKSHAM_NOTIFY', None)
    if callable(enqueue):
        enqueue(recipients=[case.release.requested_by_id], template=action,
            context={'case_id': case.pk, 'version': case.version},
            key=f'S5:{case.pk}:{case.version}:{action}')


def case_snapshot(case):
    return {'case_version': case.version, 'release_status': str(case.release.status),
        'rule_sha256': case.rule_sha256, 'penalty_review_complete': case.penalty_review_complete,
        'clearances': list(case.clearances.order_by('unit').values('unit','status','decided_by_id','reason','evidence_ref')),
        'penalties': list(case.penalties.order_by('pk').values('id','kind','base_paise','amount_paise','status','decided_by_id','reason')),
        'letters': [{'serial': l.serial, 'sha256': l.sha256,
            'revoked_at': l.revoked_at.isoformat() if l.revoked_at else None}
            for l in IssuedLetter.objects.filter(case=case)]}


def check_version(case, version):
    expected_version(version)
    if case.version != version:
        raise WorkflowError('STALE_VERSION')


def bump(case, version):
    check_version(case, version)
    case._audit_before = case_snapshot(case)
    if not ReleaseCase.objects.filter(pk=case.pk, version=version).update(version=F('version') + 1):
        raise WorkflowError('STALE_VERSION')
    case.refresh_from_db()


def source(actor, instrument, obligation, path, declarations):
    # TODO(Y1/Y2/Y3/S5-D04): callable must build facts from scoped server data and
    # the canonical questionnaire. Never install a provider returning fixture data.
    provider = getattr(settings, 'SAKSHAM_RELEASE_FACTS', None)
    if not callable(provider):
        raise DependencyUnavailable('Trusted document/questionnaire adapter unavailable.')
    facts = deepcopy(provider(actor=actor, instrument=instrument, obligation=obligation,
                              path=path, declarations=deepcopy(declarations)))
    if type(facts) is not dict:
        raise DependencyUnavailable('Invalid trusted release context.')
    if set(facts) != TOP or any(type(facts.get(section)) is not dict for section in SECTIONS):
        raise DependencyUnavailable('Invalid trusted release context sections.')
    return facts


def assessment(actor, case, operation='ASSESS', *, reason=None, completion=None):
    instrument = case.release.instrument
    facts = source(actor, instrument, case.obligation, case.path, case.declarations)
    if not case.template_ref or facts['affidavit_review'].get('template_ref') != case.template_ref:
        raise DependencyUnavailable('Declaration template changed or is unavailable; review the current version.')
    rule = rule_snapshot(case.rule_version, timezone.localdate())
    if rule.sha256 != case.rule_sha256:
        raise WorkflowError('Stored rule content changed; human reassessment is required.')
    # Authoritative identities/status overwrite provider data; provider still owns
    # validated source facts, applicable additional units and child/evidence scope.
    from obligations.services import scoped_institutions
    facts['actor'] = {'id': actor.pk, 'role_label': (role(actor) or '').upper(),
                     'scope_institution_ids': list(scoped_institutions(actor).values_list('pk', flat=True))}
    facts['case'] = {'id': case.pk, 'institution_id': case.institution_id, 'instrument_id': instrument.pk,
        'requester_id': case.release.requested_by_id, 'version': case.version,
        'expected_version': case.version, 'assessment_version': case.version,
        'status': str(case.release.status), 'path': str(case.path), 'mode': str(case.mode),
        'other_active_release': instrument.release_requests.exclude(pk=case.release_id).filter(status__in=['PENDING','APPROVED']).exists()}
    facts['instrument'] = {'id': instrument.pk, 'institution_id': instrument.institution_id,
        'status': str(instrument.status), 'superseded': instrument.is_superseded, 'released': instrument.is_released,
        'maturity_date': instrument.maturity_date.isoformat(), 'successor_proposal_exists': Instrument.objects.filter(predecessor=instrument).exists()}
    facts['obligation']['id'] = case.obligation_id
    facts['obligation']['institution_id'] = case.institution_id
    facts['obligation']['term_end'] = case.obligation.term_end.isoformat() if case.obligation.term_end else None
    facts['clearances'] = {t.unit: {'status': t.status, 'actor_id': t.decided_by_id,
        'reason': t.reason or None, 'evidence_ref': t.evidence_ref or None} for t in case.clearances.all()}
    facts['penalty_review'] = {'status': 'COMPLETE' if case.penalty_review_complete else None,
        'assessments': [{'kind': p.kind, 'base_paise': p.base_paise, 'rate_bps': p.rate_bps,
        'amount_paise': p.amount_paise, 'status': p.status, 'actor_id': p.decided_by_id,
        'reason': p.reason} for p in case.penalties.all()]}
    if case.penalty_review_complete and not facts['penalty_review']['assessments']:
        facts['penalty_review']['status'] = 'COMPLETE_NO_PENALTY'
    letter = IssuedLetter.objects.filter(case=case).first()
    facts['letter'] = {'state': 'NOT_ISSUED' if letter is None else 'REVOKED' if letter.revoked_at else 'ISSUED',
        'kind': letter.kind if letter else None, 'ref': letter.serial if letter else None, 'digitally_signed': False}
    facts['monitoring_active'] = instrument.is_current
    facts['decision_reason'] = reason if reason is not None else case.release.reason
    if completion is not None:
        facts['completion'] = completion
    try:
        return evaluate_prerequisites(facts, operation=operation, rules=rule,
                                      as_of=timezone.localdate(), simulation_label='SIMULATED')
    except PrerequisiteInputError:
        raise DependencyUnavailable('Trusted release facts failed schema validation.') from None


def require_gate(result, outcome):
    if result['outcome'] != outcome:
        if result['outcome'] == 'DENIED':
            raise PermissionDenied('Independent authorized actor required.')
        if result['outcome'] == 'INVALID_INPUT':
            raise ValidationError('Invalid release context.')
        if result['outcome'] == 'CONTEXT_UNAVAILABLE':
            raise DependencyUnavailable('Release assessment context unavailable.')
        raise WorkflowError('Prerequisites do not permit this action: ' + result['outcome'])


@transaction.atomic
def request_case(actor, *, instrument_id, obligation_id, instrument_version, path, declarations, reason, template_ref):
    owner = institution_for(actor)
    instrument = get_object_or_404(Instrument, pk=instrument_id, institution=owner)
    obligation = get_object_or_404(DepositObligation.objects.select_related('rule_version'), pk=obligation_id, institution=owner)
    expected_version(instrument_version)
    reason = reason_text(reason)
    if type(path) is not str or path not in PATHS or type(declarations) is not dict or len(declarations) > 11 or any(
            type(k) is not str or len(k) > 80 or type(v) not in {bool, type(None)} for k, v in declarations.items()):
        raise ValidationError('Supply a supported path and explicit canonical declaration answers.')
    if not obligation.rule_version:
        raise DependencyUnavailable('Select an explicit reviewed rule context.')
    facts = source(actor, instrument, obligation, path, declarations)
    if type(template_ref) is not str or not template_ref.strip() or len(template_ref) > 200:
        raise ValidationError('An explicit reviewed declaration template reference is required.')
    if facts['affidavit_review'].get('template_ref') != template_ref:
        raise DependencyUnavailable('Declaration template changed; review the current version.')
    mode = facts.get('case', {}).get('mode')
    if mode not in {'FDR', 'RTGS', 'RPGF'}:
        raise DependencyUnavailable('Validated holding mode unavailable.')
    if hasattr(instrument, 'obligation_id') and instrument.obligation_id != obligation.pk:
        raise PermissionDenied('Holding does not belong to the selected obligation.')
    if hasattr(instrument, 'mode') and instrument.mode != mode:
        raise DependencyUnavailable('Holding mode conflicts with validated source context.')
    rule = rule_snapshot(obligation.rule_version, timezone.localdate())
    # Existing request is inside this transaction; gate failure rolls it and its
    # instrument version/audit back. Its active state also blocks legacy renewal.
    release = legacy.request_release(actor, instrument.pk, instrument_version, reason)
    case = ReleaseCase.objects.create(release=release, institution=owner, obligation=obligation,
        rule_version=obligation.rule_version, rule_sha256=rule.sha256,
        path=path, mode=mode, declarations=declarations, template_ref=template_ref)
    units = facts.get('required_units')
    if type(units) is not list or not all(type(u) is str for u in units) or not {'PGRC','VIGILANCE','GRANTS'} <= set(units) or len(units) != len(set(units)):
        raise DependencyUnavailable('Complete applicable clearance units unavailable.')
    for unit in units:
        if type(unit) is not str or not unit.strip() or len(unit) > 40:
            raise ValidationError('Invalid clearance unit.')
        ClearanceTask.objects.create(case=case, unit=unit)
    result = assessment(actor, case, 'REQUEST', reason=reason)
    require_gate(result, 'REQUEST_PREREQUISITES_MET_IN_DEMO')
    record(case, actor, 'RELEASE_CASE_REQUESTED', reason)
    return case


def clearance_allowed(actor, task):
    # TODO(K4): use the agreed real membership/scope helper; deny by default.
    permission = getattr(settings, 'SAKSHAM_CLEARANCE_PERMISSION', None)
    return bool(actor.is_authenticated and actor.is_active and callable(permission) and permission(actor, task) is True)


@transaction.atomic
def decide_clearance(actor, case_id, unit, version, status, reason, evidence_ref):
    case = get_case(actor, case_id)
    check_version(case, version)
    task = get_object_or_404(ClearanceTask, case=case, unit=unit)
    if not clearance_allowed(actor, task):
        raise PermissionDenied('Clearance-unit permission required.')
    if case.release.status != 'PENDING' or task.status != 'OPEN':
        raise WorkflowError('Only an open task on a pending case can be decided.')
    if type(status) is not str or status not in {'CLEARED','OBJECTION','HOLD'} or type(evidence_ref) is not str or not evidence_ref.strip() or len(evidence_ref) > 200:
        raise ValidationError('A decision and scoped reviewed evidence reference are required.')
    # Evidence ownership/review must be verified by the same trusted source adapter.
    verifier = getattr(settings, 'SAKSHAM_CLEARANCE_EVIDENCE', None)
    if not callable(verifier) or not verifier(actor, task, evidence_ref):
        raise DependencyUnavailable('Scoped clearance evidence validation unavailable.')
    reason = reason_text(reason)
    bump(case, version)
    task.status, task.decided_by, task.reason, task.evidence_ref = status, actor, reason, evidence_ref
    task.full_clean(); task.save()
    record(case, actor, 'CLEARANCE_' + status, reason)
    return case


@transaction.atomic
def review_penalties(actor, case_id, version, reason, *, kind=None, base_paise=None, confirm_id=None):
    case = get_case(actor, case_id)
    require_officer(actor)
    check_version(case, version)
    reason = reason_text(reason)
    if case.release.status != 'PENDING':
        raise WorkflowError('Penalty review requires a pending case.')
    bump(case, version)
    if kind is not None:
        result = penalty_proposal(kind, base_paise, case.rule_version, as_of=timezone.localdate())
        if result['status'] != 'PROPOSED':
            raise WorkflowError('Penalty applicability requires further human policy review.')
        PenaltyAssessment.objects.create(case=case, kind=kind, clause=result['source_clause'],
            base_paise=base_paise, rate_bps=result['rate_bps'], amount_paise=result['amount_paise'], reason=reason)
        case.penalty_review_complete = False
    elif confirm_id is not None:
        item = get_object_or_404(PenaltyAssessment, pk=confirm_id, case=case, status='PROPOSED')
        item.status, item.decided_by, item.reason = 'CONFIRMED', actor, reason
        item.save(update_fields=['status','decided_by','reason'])
        case.penalty_review_complete = False
    else:
        if case.penalties.exclude(status='CONFIRMED').exists():
            raise WorkflowError('Every proposed penalty needs human disposition first.')
        case.penalty_review_complete = True
    case.save(update_fields=['penalty_review_complete'])
    record(case, actor, 'PENALTY_REVIEW', reason)
    return case


@transaction.atomic
def decide(actor, case_id, version, instrument_version, decision, reason):
    case = get_case(actor, case_id)
    require_authority(actor)
    check_version(case, version)
    expected_version(instrument_version)
    reason = reason_text(reason)
    if decision not in {'approve', 'reject'}:
        raise ValidationError('Choose approve or reject.')
    if instrument_version != case.release.instrument.version:
        raise WorkflowError('STALE_INSTRUMENT_VERSION')
    result = assessment(actor, case, 'APPROVE' if decision == 'approve' else 'REJECT', reason=reason)
    require_gate(result, 'AUTHORIZATION_RECORDABLE_IN_DEMO' if decision == 'approve' else 'REJECTION_RECORDABLE_IN_DEMO')
    bump(case, version)
    legacy.decide_release(actor, case.release.instrument_id, case.release_id, instrument_version, decision, reason,
                          _casework_token=legacy._OWNED_CASE_TOKEN)
    case.release.refresh_from_db()
    record(case, actor, 'CASE_' + decision.upper(), reason)
    return case


@transaction.atomic
def issue(actor, case_id, version, reason):
    case = get_case(actor, case_id)
    require_authority(actor)
    check_version(case, version)
    reason = reason_text(reason)
    result = assessment(actor, case, 'ISSUE_LETTER', reason=reason)
    require_gate(result, 'LETTER_PREREQUISITES_MET_IN_DEMO')
    base = getattr(settings, 'SAKSHAM_PUBLIC_BASE_URL', '')
    parsed = urlparse(base)
    if parsed.scheme not in {'https','http'} or not parsed.netloc or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise DependencyUnavailable('Public verification base URL is not configured.')
    bump(case, version)
    instrument = case.release.instrument
    before = instrument_snapshot(instrument)
    _compare_and_update(instrument, instrument.version)
    token = secrets.token_urlsafe(32)
    serial = 'SYNTH-' + uuid4().hex.upper()
    kind = result['proposed_letter_kind']
    pdf = render_letter(serial=serial, kind=kind, institution_name=case.institution.name,
        issue_date=timezone.localdate().isoformat(), verification_url=base.rstrip('/') + '/verify/' + token)
    letter = IssuedLetter.objects.create(case=case, serial=serial, kind=kind, issued_by=actor,
        institution_name=case.institution.name,
        pdf=pdf, sha256=hashlib.sha256(pdf).hexdigest(), token_sha256=hashlib.sha256(token.encode()).hexdigest())
    record(case, actor, 'LETTER_ISSUED', reason)
    event(instrument, actor, 'CASE_LETTER_ISSUED', before, reason)
    return letter


def _complete(actor, case_id, version, instrument_version, notes, document, refund_reference=''):
    case = get_case(actor, case_id)
    require_authority(actor)
    check_version(case, version)
    expected_version(instrument_version)
    notes = reason_text(notes)
    if type(refund_reference) is not str or len(refund_reference) > 200:
        raise ValidationError('Invalid recorded refund reference.')
    if instrument_version != case.release.instrument.version:
        raise WorkflowError('STALE_INSTRUMENT_VERSION')
    # TODO(Y2): parse a NEW upload using Yash's real bounded validator first.
    validator = getattr(settings, 'SAKSHAM_COMPLETION_VALIDATOR', None)
    if document is None or not callable(validator):
        raise DependencyUnavailable('New completion PDF parser unavailable.')
    if validator(document) is not True:
        raise ValidationError('Completion PDF rejected.')
    document.seek(0)
    result = assessment(actor, case, 'COMPLETE', reason=notes, completion={
        'new_evidence_ref': 'new-upload-' + uuid4().hex, 'evidence_is_new': True,
        'parse_status': 'VALID_SYNTHETIC_METADATA', 'notes': notes,
        'refund_reference': refund_reference or None})
    require_gate(result, 'COMPLETION_RECORDABLE_IN_DEMO')
    bump(case, version)
    # All own writes precede legacy's file write; after legacy success only this
    # transaction commits. Its known-failure cleanup remains inside legacy service.
    case.completion_reference = refund_reference
    case.save(update_fields=['completion_reference'])
    record(case, actor, 'CASE_COMPLETION_REQUESTED', notes)
    finished = legacy.complete_release(actor, case.release.instrument_id, case.release_id,
                            instrument_version, notes, document, _casework_token=legacy._OWNED_CASE_TOKEN)
    case.release = finished
    return case, finished.completion_evidence.file


def complete(*args, **kwargs):
    stored = None
    try:
        with transaction.atomic():
            case, stored = _complete(*args, **kwargs)
        return case
    except Exception:
        if stored is not None:
            stored.delete(save=False)
        raise


@transaction.atomic
def revoke(actor, case_id, version, reason):
    case = get_case(actor, case_id)
    require_authority(actor)
    check_version(case, version)
    if case.release.requested_by_id == actor.pk:
        raise PermissionDenied('Requester cannot revoke their own case letter.')
    reason = reason_text(reason)
    letter = get_object_or_404(IssuedLetter, case=case, revoked_at__isnull=True)
    bump(case, version)
    letter.revoked_at, letter.revocation_reason = timezone.now(), reason
    letter.save(update_fields=['revoked_at','revocation_reason'])
    record(case, actor, 'LETTER_REVOKED', reason)
    return case


def public_record(token):
    if type(token) is not str or not 20 <= len(token) <= 100 or not all(c.isascii() and (c.isalnum() or c in '-_') for c in token):
        return None
    letter = IssuedLetter.objects.select_related('case__institution').filter(
        token_sha256=hashlib.sha256(token.encode()).hexdigest()).first()
    if letter is None:
        return None
    return {'serial': letter.serial, 'issue_date': timezone.localtime(letter.issued_at).date().isoformat(),
        'institution_name': letter.institution_name, 'kind': letter.kind,
        'status': 'REVOKED' if letter.revoked_at else 'ISSUED'}
