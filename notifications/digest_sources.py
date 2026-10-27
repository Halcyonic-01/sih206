"""Bounded server-scoped activity snapshots; no document text or personal details."""
import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import DatabaseError
from django.db.models import OuterRef, Subquery

from portal.models import AuditEvent, ReviewObservation
from portal.permissions import role, institution_for, clearance_unit, scoped_instruments
from .digest import build_digest, business_window, SOURCES
from .models import DigestPreference

LIMIT = 5000


def bounded(rows, limit=LIMIT):
    result = list(rows[:limit + 1])
    return None if len(result) > limit else result


def recipient_snapshot(user):
    current_role = role(user)
    if not current_role:
        raise PermissionDenied('A single active portal role is required.')
    try:
        validate_email(user.email)
    except ValidationError:
        email_available = False
    else:
        email_available = True
    preference = DigestPreference.objects.filter(user=user).first()
    records = scoped_instruments(user)
    scope = bounded(records.order_by('institution_id').values_list('institution_id', flat=True).distinct())
    if scope is None:
        raise PermissionDenied('Digest scope exceeds its safe bound.')
    if current_role == 'institution':
        scope = [institution_for(user).pk]
    snapshot = {'id': user.pk, 'roles': [current_role], 'active': user.is_active,
        'email_available': email_available, 'digest_enabled': preference.enabled if preference else True,
        'scope_institution_ids': scope,
        'unit': clearance_unit(user) if current_role == 'clearance' else None}
    identity = {**snapshot, 'email': user.email.strip(), 'preference_version': preference.version if preference else 0,
        'scope_policy': 'portal-permissions-v1'}
    # Staff scope is role/unit-based in the shared platform, not a mutable list of institutions with records.
    # A newly submitted institution must not cancel an otherwise authorized frozen digest.
    if current_role != 'institution':
        identity.pop('scope_institution_ids')
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return snapshot, fingerprint


def facts_for(user, recipient, as_of):
    current_role = recipient['roles'][0]
    facts = {'simulation_label': 'RECORDED', **{name: None for name in SOURCES[current_role]}}
    records = scoped_instruments(user)
    if current_role == 'institution':
        rows = bounded(records.order_by('pk').values('id', 'institution_id', 'maturity_date', 'status',
                                                     'released_at', 'superseded_at'))
        if rows is not None:
            facts['deposits'] = [dict(id=r['id'], institution_id=r['institution_id'], maturity_date=r['maturity_date'],
                status=r['status'], released=r['released_at'] is not None, superseded=r['superseded_at'] is not None) for r in rows]
        rows = bounded(ReviewObservation.objects.filter(instrument__in=records,
            instrument__status='CHANGES_REQUESTED', instrument__released_at__isnull=True,
            instrument__superseded_at__isnull=True).order_by('pk').values('id', 'instrument__institution_id', 'resolved_at'))
        if rows is not None:
            facts['observations'] = [dict(id=r['id'], institution_id=r['instrument__institution_id'],
                resolved=r['resolved_at'] is not None, requires_institution_action=True) for r in rows]
    elif current_role == 'officer':
        rows = bounded(records.order_by('pk').values('id', 'institution_id', 'status'))
        facts['submissions'] = rows
        from verification.models import VerificationEvidence
        latest = VerificationEvidence.objects.filter(instrument_id=OuterRef('pk')).order_by('-created_at', '-pk')
        rows = bounded(records.filter(verification_level='DISCREPANCY').annotate(
            latest_method=Subquery(latest.values('method')[:1]), latest_result=Subquery(latest.values('result')[:1]))
            .filter(latest_method='SIMULATED_STATEMENT', latest_result='DISCREPANCY')
            .order_by('pk').values('id', 'institution_id'))
        if rows is not None:
            facts['discrepancies'] = [dict(**r, unresolved=True, simulated=True) for r in rows]
        window = business_window(as_of)
        accepted = bounded(AuditEvent.objects.filter(instrument__in=records, action='ACCEPTED',
            created_at__gte=window['previous_start'], created_at__lt=window['previous_end']).order_by('pk')
            .values('id', 'instrument_id', 'instrument__institution_id', 'created_at'))
        if accepted is not None:
            # One bounded history query, then pair each acceptance with its immediately preceding submission.
            histories = bounded(AuditEvent.objects.filter(instrument_id__in=[r['instrument_id'] for r in accepted],
                action__in=['SUBMITTED', 'ACCEPTED', 'CHANGES_REQUESTED'], created_at__lte=as_of)
                .order_by('created_at', 'pk').values('id', 'instrument_id', 'action', 'created_at'))
            if histories is not None:
                pending, pairs = {}, {}
                for event in histories:
                    identity = event['instrument_id']
                    if event['action'] == 'SUBMITTED':
                        pending[identity] = event['created_at']
                    elif event['action'] == 'ACCEPTED':
                        pairs[event['id']] = pending.pop(identity, None)
                    else:
                        pending.pop(identity, None)
                facts['reviews'] = [dict(id=r['id'], institution_id=r['instrument__institution_id'],
                    submitted_at=pairs.get(r['id']) or r['created_at'], accepted_at=r['created_at'],
                    history_complete=pairs.get(r['id']) is not None) for r in accepted]
    elif current_role == 'authority':
        from casework.services import scoped_cases
        from casework.api import case_json
        rows = bounded(scoped_cases(user).filter(release__status='PENDING').select_related('release__instrument', 'rule_version', 'obligation').order_by('pk'), limit=50)
        if rows is not None:
            facts['releases'] = [dict(id=c.pk, institution_id=c.institution_id, status=c.release.status,
                ready_for_authority=bool(case_json(user, c)['actions']['can_approve'])) for c in rows]
        # There is no canonical unresolved escalation register. Unavailable is deliberate.
    elif current_role == 'clearance':
        from casework.services import scoped_cases
        from obligations.models import ClearanceTask
        rows = bounded(ClearanceTask.objects.filter(case__in=scoped_cases(user), unit=recipient['unit'],
            case__release__status='PENDING').order_by('pk').values('id', 'case__institution_id', 'unit', 'status'))
        if rows is not None:
            facts['clearances'] = [dict(id=r['id'], institution_id=r['case__institution_id'], unit=r['unit'], status=r['status']) for r in rows]
    return facts


def prepare_digest(user, *, as_of, portal_base_url):
    recipient, fingerprint = recipient_snapshot(user)
    facts = facts_for(user, recipient, as_of)
    result = build_digest(recipient, facts, as_of=as_of, portal_base_url=portal_base_url, recorded=True)
    result['scope_fingerprint'] = fingerprint
    return result


def delivery_allowed(row):
    """Re-evaluate recipients at send time; never redirect a frozen digest to a new address."""
    from django.conf import settings
    from django.contrib.auth import get_user_model
    if not getattr(settings, 'WEEKLY_DIGEST_ENABLED', False) or not row.recipient_id:
        return False
    try:
        user = get_user_model().objects.get(pk=row.recipient_id)
        recipient, fingerprint = recipient_snapshot(user)
        return (recipient['active'] and recipient['email_available'] and recipient['digest_enabled']
            and user.email.strip() == row.recipient_email
            and fingerprint == row.context.get('scope_fingerprint'))
    except (PermissionDenied, get_user_model().DoesNotExist):
        return False
