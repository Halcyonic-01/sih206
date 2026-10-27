"""Owned audited master services; actual holding/proof sources remain separate."""
import json
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import F
from django.forms.models import model_to_dict
from django.shortcuts import get_object_or_404
from django.utils import timezone

from portal.models import Institution, Instrument
from portal.permissions import institution_for, require_officer, role
from portal.services import WorkflowError
from .calculations import ApprovalInput, HoldingInput, ObligationInput, coverage, required_amount
from .checks import obligation_findings
from .models import (DepositObligation, InstitutionProfile, MasterAudit, ProgrammeApproval, ProofReceiptReview,
                     RuleSet)
from .rules import RuleInputError


class DependencyUnavailable(WorkflowError):
    pass


def scoped_institutions(actor):
    # K4 has no geographic master helper. Preserve conservative existing access:
    # own institution; officer/authority reads; clearance/auditor denied. Instrument
    # history access does not grant access to unsubmitted institution master data.
    current = role(actor)
    if current == 'institution':
        return Institution.objects.filter(pk=institution_for(actor).pk)
    if current == 'officer':
        from portal.permissions import officer_regions, region_q
        regions = officer_regions(actor)
        return Institution.objects.filter(region_q(regions)) if regions else Institution.objects.all()
    if current == 'authority':
        return Institution.objects.all()
    raise PermissionDenied('An active unambiguous portal role is required.')


def institution(actor, identity):
    return get_object_or_404(scoped_institutions(actor), pk=identity)


def scoped_obligations(actor):
    return DepositObligation.objects.filter(institution__in=scoped_institutions(actor))


def reason_text(reason):
    if type(reason) is not str or not reason.strip() or len(reason) > 2000:
        raise ValidationError({'reason': 'A reason of 1–2000 characters is required.'})
    return reason.strip()


def expected_version(value):
    if type(value) is not int or value < 1:
        raise ValidationError({'version': 'Supply the positive integer record version.'})
    return value


def strict_fields(values, allowed):
    if type(values) is not dict or set(values) - set(allowed):
        raise ValidationError({'fields': 'Unexpected or protected field.'})
    return values


def text_values(values, fields):
    result = dict(values)
    for key in set(fields) & result.keys():
        if type(result[key]) is not str:
            raise ValidationError({key: 'Supply text, not a coerced number or boolean.'})
        result[key] = result[key].strip()
    return result


def snapshot(record):
    return wire_money(json.loads(json.dumps(model_to_dict(record), cls=DjangoJSONEncoder)))


def wire_money(value):
    """Preserve larger legacy paise values losslessly; never emit unsafe JSON money."""
    if type(value) is dict:
        return {key: str(child) if key.endswith('_paise') and type(child) is int and abs(child) > 2**53-1
                else wire_money(child) for key, child in value.items()}
    if type(value) is list:
        return [wire_money(child) for child in value]
    return value


def audit(actor, record, action, reason, before):
    after = snapshot(record)
    if isinstance(record, InstitutionProfile):
        after.update(name=record.institution.name, code=record.institution.code)
    MasterAudit.objects.create(institution_id=record.institution_id, actor=actor,
        entity=record._meta.model_name, entity_id=record.pk, action=action,
        reason=reason, before=before, after=after)


def revise(record, version, values):
    expected_version(version)
    if record.version != version:
        raise WorkflowError('STALE_VERSION')
    for field, value in values.items():
        setattr(record, field, value)
    record.full_clean()
    if not type(record).objects.filter(pk=record.pk, version=version).update(
            **values, version=F('version') + 1):
        raise WorkflowError('STALE_VERSION')
    record.refresh_from_db()


PROFILE_FIELDS = {'aicte_id', 'trust_name', 'institution_type', 'region', 'state', 'contact_email', 'status'}
APPROVAL_FIELDS = {'programme', 'level', 'approved_on', 'loa_ref', 'land_tenure', 'building_tenure'}
OBLIGATION_FIELDS = {'basis', 'basis_reference', 'rule_version_id', 'required_paise',
                     'term_start', 'term_end', 'intimation_date'}


@transaction.atomic
def create_institution(actor, values, reason):
    require_officer(actor)
    reason = reason_text(reason)
    strict_fields(values, PROFILE_FIELDS | {'code', 'name'})
    values = text_values(values, PROFILE_FIELDS | {'code','name'})
    item = Institution(code=values.get('code'), name=values.get('name'))
    item.full_clean()
    item.save()
    profile = InstitutionProfile(institution=item, **{k: v for k, v in values.items() if k in PROFILE_FIELDS})
    profile.full_clean()
    profile.save()
    audit(actor, profile, 'INSTITUTION_CREATED', reason, {})
    return profile


@transaction.atomic
def update_institution(actor, identity, version, values, reason):
    item = institution(actor, identity)
    require_officer(actor)
    reason = reason_text(reason)
    strict_fields(values, PROFILE_FIELDS | {'name', 'code'})
    values = text_values(values, PROFILE_FIELDS | {'name','code'})
    profile = get_object_or_404(InstitutionProfile, institution=item)
    before = snapshot(profile) | {'name': item.name, 'code': item.code}
    revise(profile, version, {k: v for k, v in values.items() if k in PROFILE_FIELDS})
    for key in {'name', 'code'} & values.keys():
        setattr(item, key, values[key])
    item.full_clean()
    item.save(update_fields=['name', 'code'])
    audit(actor, profile, 'INSTITUTION_UPDATED', reason, before)
    return profile


def validate_obligation_values(values):
    for key in ['required_paise', 'rule_version_id']:
        if key in values and values[key] is not None and (
                type(values[key]) is not int or not 0 < values[key] <= 2**53 - 1):
            raise ValidationError({key: 'Use a positive safe integer or null; exemptions require separate approval.'})


@transaction.atomic
def save_child(actor, model, institution_id, values, reason, identity=None, version=None):
    item = institution(actor, institution_id)
    require_officer(actor)
    reason = reason_text(reason)
    allowed = APPROVAL_FIELDS if model is ProgrammeApproval else OBLIGATION_FIELDS
    if model not in {ProgrammeApproval, DepositObligation}:
        raise ValidationError('Unsupported owned entity.')
    strict_fields(values, allowed)
    values = text_values(values, allowed - {'approved_on','rule_version_id','required_paise',
                                         'term_start','term_end','intimation_date'})
    if model is DepositObligation:
        validate_obligation_values(values)
    # Explicit parsing prevents Django model coercion accepting malformed wire dates.
    values = dict(values)
    for key in ['approved_on', 'term_start', 'term_end', 'intimation_date']:
        if key in values and values[key] is not None:
            value = values[key]
            if type(value) is str:
                try:
                    parsed = date.fromisoformat(value)
                    if parsed.isoformat() != value:
                        raise ValueError
                    values[key] = parsed
                except ValueError:
                    raise ValidationError({key: 'Use YYYY-MM-DD.'}) from None
            elif type(value) is not date:
                raise ValidationError({key: 'Use a calendar date or null.'})
    if identity is None:
        record = model(institution=item, **values)
        record.full_clean()
        record.save()
        before, action = {}, 'CREATED'
    else:
        record = get_object_or_404(model, pk=identity, institution=item)
        if model is DepositObligation and record.status in {'EXEMPT', 'RELEASED', 'FORFEITED', 'EXTENDED'}:
            raise WorkflowError('Protected lifecycle state requires its own reviewed service.')
        before, action = snapshot(record), 'UPDATED'
        revise(record, version, values)
    audit(actor, record, action, reason, before)
    return record


def holding_snapshot(actor, obligation):
    """Actual scoped Y1 snapshot; retained boundary for callers/tests."""
    from .sources import linked_holdings
    return linked_holdings(actor, obligation)


def _receipt_date(value, field):
    if value in (None, ''):
        return None
    try:
        parsed = date.fromisoformat(value) if type(value) is str else None
    except ValueError:
        parsed = None
    if parsed is None or parsed.isoformat() != value:
        raise ValidationError({field: 'Use YYYY-MM-DD, or leave empty when the document has not been received.'})
    if parsed > timezone.localdate():
        raise ValidationError({field: 'A receipt date cannot be in the future.'})
    return parsed


@transaction.atomic
def record_proof_receipts(actor, identity, version, payment_proof_on, affidavit_on, reason):
    """Officer review of deposit-proof and Affidavit-3 receipt dates; empty means reviewed as not received."""
    require_officer(actor)
    record = get_object_or_404(scoped_obligations(actor), pk=identity)
    reason = reason_text(reason)
    values = {'payment_proof_on': _receipt_date(payment_proof_on, 'payment_proof_on'),
              'affidavit_on': _receipt_date(affidavit_on, 'affidavit_on')}
    before = snapshot(record)
    revise(record, version, {})
    review = ProofReceiptReview.objects.create(obligation=record, reviewed_by=actor, reason=reason, **values)
    MasterAudit.objects.create(institution_id=record.institution_id, actor=actor, entity='depositobligation',
        entity_id=record.pk, action='PROOF_RECEIPTS_REVIEWED', reason=reason, before=before,
        after=snapshot(record) | {key: value.isoformat() if value else None for key, value in values.items()})
    return review


def reviewed_proof_receipts(actor, obligation):
    """SAKSHAM_PROOF_RECEIPTS provider: the latest officer review, or unknown when nobody has reviewed yet."""
    visible = scoped_obligations(actor).filter(pk=obligation.pk).exists()
    review = ProofReceiptReview.objects.filter(obligation_id=obligation.pk).first() if visible else None
    if review is None:
        raise DependencyUnavailable('No officer review of proof receipt dates yet.')
    return {'payment_proof_on': review.payment_proof_on, 'affidavit_on': review.affidavit_on}


def proof_review_json(record):
    review = record.proof_reviews.select_related('reviewed_by').first()
    return None if review is None else {
        'payment_proof_on': review.payment_proof_on.isoformat() if review.payment_proof_on else None,
        'affidavit_on': review.affidavit_on.isoformat() if review.affidavit_on else None,
        'reviewed_by': review.reviewed_by.get_username(), 'reviewed_at': review.created_at.isoformat(),
        'reason': review.reason}


def obligation_detail(actor, identity, *, as_of=None):
    record = get_object_or_404(scoped_obligations(actor).select_related('rule_version'), pk=identity)
    when = as_of or timezone.localdate()
    ob = ObligationInput(record.pk, record.institution_id, record.required_paise,
                         record.term_start, record.term_end)
    data = snapshot(record)
    data['actions'] = {'can_edit': role(actor) == 'officer' and record.status not in
                       {'EXEMPT', 'RELEASED', 'FORFEITED', 'EXTENDED'},
                       'can_record_proof_receipts': role(actor) == 'officer'}
    data['proof_review'] = proof_review_json(record)
    data['assessment'] = {'status': 'UNAVAILABLE', 'coverage': None, 'findings': None,
                          'holdings': None, 'open_actions': None,
                          'as_of': when.isoformat(), 'reason': 'RULE_CONTEXT_UNAVAILABLE'}
    if record.rule_version is None:
        return data
    try:
        holdings = holding_snapshot(actor, record)
        # Holdings and receipt timing are independent sources. Incomplete proof
        # context must not discard otherwise valid coverage or invent overdue proof.
        findings = obligation_findings(ob, record.rule_version, as_of=when, holdings=holdings)
        from .sources import proof_evidence
        documents = proof_evidence(actor, record)
        proof_status, proof_reason = 'UNAVAILABLE', 'REVIEWED_RECEIPT_DATE_CONTRACT_UNAVAILABLE'
        provider = getattr(settings, 'SAKSHAM_PROOF_RECEIPTS', None)
        if callable(provider):
            try:
                receipts = provider(actor, record)
                if type(receipts) is not dict or set(receipts) != {'payment_proof_on','affidavit_on'} or any(
                        value is not None and type(value) is not date for value in receipts.values()):
                    raise DependencyUnavailable('Invalid scoped proof receipt context.')
                checked = obligation_findings(ob, record.rule_version, as_of=when, holdings=holdings,
                    intimation_date=record.intimation_date, **receipts)
                findings = checked
                if record.intimation_date:
                    proof_status, proof_reason = 'AVAILABLE', None
                else:
                    proof_reason = 'INTIMATION_DATE_UNAVAILABLE'
            except (DependencyUnavailable, RuleInputError):
                proof_reason = 'REVIEWED_RECEIPT_CONTEXT_UNAVAILABLE'
        data['assessment'] = {'status': 'AVAILABLE', 'as_of': when.isoformat(),
            'coverage': coverage(ob, when, holdings=holdings),
            'holdings': [{'id': h.id, 'amount_paise': h.amount_paise, 'issue_date': h.issue_date.isoformat(),
                'maturity_date': h.maturity_date.isoformat(), 'status': h.status,
                'superseded': h.superseded, 'released': h.released} for h in holdings],
            'open_actions': [{'description': f.explanation, 'responsible_party': 'Institution and reviewing officer',
                'suggested_only': True} for f in findings],
            'findings': [f.as_dict() for f in findings],
            'proof_assessment': proof_status, 'proof_reason': proof_reason,
            'proof_evidence': documents, 'simulation_label': 'SIMULATED',
            'policy_label': 'DRAFT_DEMO_NOT_APPROVED'}
    except (DependencyUnavailable, RuleInputError) as exc:
        data['assessment']['reason'] = 'HOLDINGS_OR_RULE_CONTEXT_UNAVAILABLE'
    return wire_money(data)


def calculator(actor, identity, rule_id, approvals):
    item = institution(actor, identity)
    profile = get_object_or_404(InstitutionProfile, institution=item)
    rules = get_object_or_404(RuleSet, pk=rule_id)
    if type(approvals) is not list or len(approvals) > 100:
        raise ValidationError({'approvals': 'Supply at most 100 explicit programme snapshots.'})
    inputs = []
    for values in approvals:
        strict_fields(values, {'programme', 'level', 'land_tenure', 'building_tenure'})
        if len(values) != 4:
            raise ValidationError({'approvals': 'Every programme snapshot requires all four fields.'})
        inputs.append(ApprovalInput(**values))
    return required_amount(inputs, rules, as_of=timezone.localdate(), institution_type=profile.institution_type)
