"""Read-only, bounded readiness snapshots from actual scoped portal records."""
from collections import defaultdict
import hashlib
import json

from django.shortcuts import get_object_or_404
from django.utils import timezone

from portal.api.records import actions as record_actions
from portal.models import AuditEvent, Document, Instrument
from portal.permissions import role, scoped_instruments, scoped_documents
from verification.models import VerificationEvidence
from verification.provenance import derive
from . import services
from .calculations import coverage, HoldingInput, ObligationInput
from .models import ProofReceiptReview
from .readiness import calculate, aggregate, ITEMS, ACTIONS, ReadinessInputError
from .rules import rule_snapshot, RuleInputError

MAX_OBLIGATIONS = 100
MAX_HOLDINGS = 1000
MAX_DETAILS = 10000
ISSUER_FIELDS = ('reference', 'amount', 'ifsc', 'holder_names', 'issue_date', 'maturity_date', 'lien_marked')


def bounded(query, maximum):
    rows = list(query[:maximum+1])
    if len(rows) > maximum:
        raise services.DependencyUnavailable('Readiness source exceeds the supported complete-snapshot limit.')
    return rows


def bank_status(item, rows, corrections):
    issuer = [row for row in rows if row.method in {'BANK_CONFIRMATION', 'SIMULATED_BANK'}]
    if not issuer:
        return 'MISSING'
    latest = max(issuer, key=lambda row: row.pk)
    if latest.result == 'DISCREPANCY':
        return 'DISCREPANCY'
    if type(latest.fields_observed) is not dict:
        return 'UNKNOWN'
    if any(key in latest.fields_observed and type(latest.fields_observed[key]) is not str
            for key in (*ISSUER_FIELDS, 'authentic')):
        return 'UNKNOWN'
    # A malformed/partial new response must not borrow the older response's
    # correct values and appear freshly confirmed.
    try:
        provenance = derive(item, [latest], corrections)
    except (TypeError, ValueError, ArithmeticError, KeyError, AttributeError):
        return 'UNKNOWN'
    if latest.method == 'SIMULATED_BANK':
        return 'SIMULATED'
    # Match actual present values, not workflow-only version numbers. Statements
    # and officer acceptance cannot supply missing issuer-confirmed fields.
    if (latest.result != 'CONFIRMED' or (latest.fields_observed or {}).get('authentic') != 'yes'
            or any(field not in (latest.fields_observed or {}) for field in ISSUER_FIELDS)
            or not item.reference.strip() or not item.ifsc.strip() or not item.holder_names.strip()
            or item.lien_marked is None):
        return 'STALE'
    if any(provenance[field]['status'] != 'CONFIRMED' or provenance[field]['simulated'] for field in ISSUER_FIELDS):
        return 'STALE'
    return 'CURRENT_CONFIRMED'


def assemble(actor, institution_id):
    institution = get_object_or_404(services.scoped_institutions(actor), pk=institution_id)
    obligations = bounded(services.scoped_obligations(actor).filter(institution_id=institution.pk)
        .select_related('rule_version').order_by('pk'), MAX_OBLIGATIONS)
    ids = [item.pk for item in obligations]
    current_role = role(actor)
    visible = scoped_instruments(actor)
    # Detect visible corrupt links without probing another institution's private draft.
    if visible.filter(institution_id=institution.pk, obligation__isnull=False).exclude(
            obligation__institution_id=institution.pk).exists():
        raise services.DependencyUnavailable('Inconsistent institution/obligation relationship.')
    holdings = bounded(visible.filter(obligation_id__in=ids).order_by('pk'), MAX_HOLDINGS)
    if any(item.institution_id != institution.pk for item in holdings):
        raise services.DependencyUnavailable('Inconsistent linked holding scope.')
    holding_ids = [item.pk for item in holdings]
    documents = bounded(scoped_documents(actor).filter(instrument_id__in=holding_ids).order_by('pk'), MAX_DETAILS)
    evidence = bounded(VerificationEvidence.objects.filter(instrument__in=visible,
        instrument_id__in=holding_ids).order_by('pk'), MAX_DETAILS)
    if len(documents) + len(evidence) > MAX_DETAILS:
        raise services.DependencyUnavailable('Readiness evidence exceeds the complete-snapshot limit.')
    corrections = bounded(AuditEvent.objects.filter(instrument__in=visible, instrument_id__in=holding_ids,
        action='OFFICER_CORRECTION').order_by('pk'), MAX_DETAILS)
    receipts = bounded(ProofReceiptReview.objects.filter(obligation__in=services.scoped_obligations(actor),
        obligation_id__in=ids).order_by('obligation_id', '-created_at', '-pk'), MAX_DETAILS)
    by_obligation, by_record_docs, by_record_evidence, by_record_corrections = [defaultdict(list) for _ in range(4)]
    for item in holdings:
        by_obligation[item.obligation_id].append(item)
    for document in documents:
        by_record_docs[document.instrument_id].append(document)
    for row in evidence:
        by_record_evidence[row.instrument_id].append(row)
    for row in corrections:
        by_record_corrections[row.instrument_id].append(row)
    latest_receipt = {}
    for receipt in receipts:
        latest_receipt.setdefault(receipt.obligation_id, receipt)
    when = timezone.localdate()
    snapshots, results, fingerprint = [], [], [institution.pk, when.isoformat()]
    editable_capabilities = {}
    for obligation in obligations:
        records = by_obligation[obligation.pk]
        current = [record for record in records if record.is_current]
        active = [record for record in records if not record.is_released and not record.is_superseded]
        modes = {record.mode for record in active}
        mode_known = len(modes) == 1
        mode = next(iter(modes)) if mode_known else 'FDR'
        rule, policy = None, 'RULE_CONTEXT_UNAVAILABLE'
        if obligation.rule_version is not None:
            try:
                rule = rule_snapshot(obligation.rule_version, when)
                policy = f'{rule.code} v{rule.version}: {rule.source_clause}; DRAFT_DEMO_NOT_APPROVED'
            except RuleInputError:
                policy = 'INVALID_OR_INEFFECTIVE_RULE_CONTEXT'
        exempt = (obligation.status == 'EXEMPT' and obligation.required_paise == 0 and obligation.exemption_approved_by_id is not None
            and all(value.strip() for value in (obligation.exemption_code, obligation.exemption_clause,
                                                obligation.exemption_reason)))
        applicability = dict.fromkeys(ITEMS, True)
        applicability['payment_proof'] = mode == 'RTGS' if mode_known else None
        applicability['affidavit_3'] = True if rule else None
        if obligation.status == 'EXEMPT' and not exempt:
            applicability = dict.fromkeys(ITEMS, None)
        if exempt:
            applicability = dict.fromkeys(ITEMS, False)
        holding_input = tuple(HoldingInput(id=record.pk, institution_id=record.institution_id,
            obligation_id=record.obligation_id, amount_paise=record.amount_paise,
            issue_date=record.issue_date, maturity_date=record.maturity_date, status=record.status,
            superseded=record.is_superseded, released=record.is_released) for record in records)
        required = obligation.required_paise if rule else None
        ob_input = ObligationInput(obligation.pk, institution.pk, required, obligation.term_start, obligation.term_end)
        try:
            amount_context = coverage(ob_input, when, holdings=holding_input)
        except RuleInputError as exc:
            raise services.DependencyUnavailable('Invalid scoped coverage context.') from exc
        # Uploaded metadata on current or currently editable records only. Old
        # superseded/released attachments cannot fulfill the current checklist.
        docs = [document for record in active for document in by_record_docs[record.pk]]
        payment = [d for d in docs if d.kind == Document.Kind.PAYMENT_PROOF]
        affidavits = [d for d in docs if d.kind == Document.Kind.AFFIDAVIT_3]
        receipt = latest_receipt.get(obligation.pk)
        statuses = [bank_status(record, by_record_evidence[record.pk], by_record_corrections[record.pk]) for record in current]
        bank = ('DISCREPANCY' if 'DISCREPANCY' in statuses else 'SIMULATED' if 'SIMULATED' in statuses
            else 'STALE' if 'STALE' in statuses else 'UNKNOWN' if 'UNKNOWN' in statuses
            else 'CURRENT_CONFIRMED' if statuses and all(
                value == 'CURRENT_CONFIRMED' for value in statuses) else 'MISSING')
        targets = defaultdict(list)
        for record in active:
            if current_role == 'institution' and record.status in {'DRAFT', 'CHANGES_REQUESTED'}:
                # These public capabilities depend only on own scope/status for
                # editable records; memoize two states to avoid renewal-query N+1s.
                cap = editable_capabilities.setdefault(record.status, None)
                if cap is None:
                    cap = record_actions(actor, record)
                    editable_capabilities[record.status] = cap
                if cap['can_upload']:
                    for key, kind in [('payment_proof', 'PAYMENT_PROOF'), ('affidavit_3', 'AFFIDAVIT_3')]:
                        targets[key].append({'label': 'Upload payment proof' if key == 'payment_proof' else 'Upload Affidavit-3',
                            'record_reference': record.reference,
                            'href': f'/records/{record.pk}?readiness=upload&kind={kind}', 'record_id': record.pk})
                if cap['can_submit']:
                    targets['accepted_deposit'].append({'label': 'Open deposit', 'record_reference': record.reference,
                        'href': f'/records/{record.pk}?readiness=submit', 'record_id': record.pk})
            if current_role in {'institution', 'officer', 'authority'}:
                targets['bank_confirmation'].append({'label': 'Review bank confirmation', 'record_reference': record.reference,
                    'href': f'/records/{record.pk}?readiness=verification', 'record_id': record.pk})
        if not active and current_role == 'institution' and not exempt:
            targets['accepted_deposit'].append({'label': 'New deposit',
                'href': f'/records?readiness=new&obligation={obligation.pk}'})
        if current_role == 'officer':
            targets['proof_receipt'].append({'label': 'Record receipt review',
                'href': f'/institutions/{institution.pk}?obligation={obligation.pk}&readiness=receipts'})
        targets['amount_coverage'].append({'label': 'View requirement',
            'href': f'/institutions/{institution.pk}?obligation={obligation.pk}&readiness=requirement'})
        snapshot = {'schema': 1, 'institution_id': institution.pk, 'obligation_id': obligation.pk,
            'as_of': when.isoformat(), 'mode': mode, 'applicability': applicability,
            'facts': {'accepted_current': bool(current), 'payment_proof_uploaded': bool(payment),
                'affidavit_3_uploaded': bool(affidavits), 'required_paise': required,
                'held_paise': amount_context['held_paise'], 'proof_reviewed': True if receipt else None,
                'payment_proof_on': receipt.payment_proof_on.isoformat() if receipt and receipt.payment_proof_on else None,
                'affidavit_on': receipt.affidavit_on.isoformat() if receipt and receipt.affidavit_on else None,
                'bank_status': bank},
            'deadline': {'intimation_date': obligation.intimation_date.isoformat() if obligation.intimation_date else None,
                         'proof_days': rule.payload['proof_days'] if rule else None},
            'allowed_actions': [ACTIONS[key] for key, values in targets.items() if values], 'policy_source': policy}
        result = calculate(snapshot, institution_id=institution.pk)
        result.update(version=obligation.version, mode_known=mode_known,
            required_paise=required, held_paise=amount_context['held_paise'],
            holding_choices=[{'id': record.pk, 'reference': record.reference, 'mode': record.mode,
                'status': record.status, 'version': record.version} for record in active],
            sources={'payment_proof_ids': [d.pk for d in payment], 'affidavit_3_ids': [d.pk for d in affidavits],
                'receipt_review_id': receipt.pk if receipt else None,
                'bank_evidence_ids': [row.pk for record in current for row in by_record_evidence[record.pk]
                    if row.method in {'BANK_CONFIRMATION', 'SIMULATED_BANK'}]})
        for item in result['items']:
            item['targets'] = targets[item['id']] if item['next_action'] else []
            item['helper'] = ('Upload metadata does not establish document authenticity.' if item['id'] in
                {'payment_proof', 'affidavit_3'} else 'Recorded tracking state; not a compliance determination.')
            if not item['targets'] and item['state'] not in {'COMPLETE', 'NOT_APPLICABLE'}:
                item['helper'] = 'A permitted reviewer or institution action is required; no authorized shortcut is available.'
        fingerprint.append([obligation.pk, obligation.version, snapshot, rule.sha256 if rule else None,
            receipt.pk if receipt else None,
            [(r.pk, r.version, r.status, r.amount_paise, r.mode, r.released_at.isoformat() if r.released_at else None,
              r.superseded_at.isoformat() if r.superseded_at else None) for r in records],
            [(d.pk, d.sha256, d.kind) for d in docs],
            [(row.pk, row.instrument_version, row.method, row.result, row.fields_observed)
             for record in records for row in by_record_evidence[record.pk]]])
        snapshots.append(snapshot); results.append(result)
    result = aggregate(snapshots, institution_id=institution.pk)
    result.update(obligations=results, as_of=when.isoformat(),
        unknown=sum(row['unknown'] for row in results), simulated=sum(row['simulated'] for row in results),
        label='Deposit readiness - recorded milestones, not regulatory compliance',
        source_fingerprint=hashlib.sha256(json.dumps(fingerprint, sort_keys=True, default=str,
            separators=(',', ':')).encode()).hexdigest())
    return services.wire_money(result)
