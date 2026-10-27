from django.core.exceptions import PermissionDenied

from .models import AuditEvent, Document, Instrument, ReleaseRequest, UserProfile

INSTITUTION_GROUP = 'Institution'
OFFICER_GROUP = 'Officer'
AUTHORITY_GROUP = 'Authority'
CLEARANCE_GROUP = 'Clearance'
AUDITOR_GROUP = 'Auditor'

ROLE_BY_GROUP = {
    INSTITUTION_GROUP: 'institution', OFFICER_GROUP: 'officer', AUTHORITY_GROUP: 'authority',
    CLEARANCE_GROUP: 'clearance', AUDITOR_GROUP: 'auditor',
}
# Roles that read across institutions but never create or change an institution's submission.
CROSS_INSTITUTION_ROLES = ('officer', 'authority', 'clearance', 'auditor')


def role(user):
    if not user.is_authenticated or not user.is_active:
        return None
    groups = set(user.groups.values_list('name', flat=True))
    # Ambiguous role membership fails closed.
    assigned = groups.intersection(ROLE_BY_GROUP)
    return ROLE_BY_GROUP[assigned.pop()] if len(assigned) == 1 else None


def institution_for(user):
    if role(user) != 'institution':
        raise PermissionDenied('An institution account is required.')
    try:
        return UserProfile.objects.select_related('institution').get(user=user).institution
    except UserProfile.DoesNotExist:
        raise PermissionDenied('No institution is assigned to this account.')


def clearance_unit(user):
    """The unit (PGRC, VIGILANCE or GRANTS) of a Clearance account; fails closed when none is assigned."""
    if role(user) != 'clearance':
        raise PermissionDenied('A clearance-unit account is required.')
    from access.models import UnitAssignment
    try:
        return user.unit_assignment.unit
    except UnitAssignment.DoesNotExist:
        raise PermissionDenied('No clearance unit is assigned to this account.') from None


def officer_regions(user):
    """The regions an officer is restricted to; an empty list means national scope."""
    from access.models import RegionAssignment
    return list(RegionAssignment.objects.filter(user=user).values_list('region', flat=True))


def region_q(regions, prefix='deposit_profile__region'):
    """Q matching institutions in any of `regions` (case-insensitive). `prefix` is the path to InstitutionProfile.region."""
    from django.db.models import Q
    query = Q(pk__in=[])
    for region in regions:
        query |= Q(**{f'{prefix}__iexact': region})
    return query


def scoped_instruments(user):
    current_role = role(user)
    if current_role == 'officer':
        regions = officer_regions(user)
        records = Instrument.objects.exclude(status=Instrument.Status.DRAFT)
        # A regional officer sees only institutions whose profile region matches theirs; none without a profile (fail closed).
        return records.filter(region_q(regions, 'institution__deposit_profile__region')) if regions else records
    if current_role in ('authority', 'auditor'):
        # Drafts are private until the first submission. Corrected records stay visible.
        return Instrument.objects.exclude(status=Instrument.Status.DRAFT)
    if current_role == 'clearance':
        # Clearance units only see instruments that have a release case. S5 narrows this to their own tasks.
        return Instrument.objects.exclude(status=Instrument.Status.DRAFT).filter(
            pk__in=ReleaseRequest.objects.values('instrument_id'))
    if current_role == 'institution':
        return Instrument.objects.filter(institution=institution_for(user))
    raise PermissionDenied('This account has no portal role.')


def scoped_documents(user):
    return Document.objects.filter(instrument__in=scoped_instruments(user))


def scoped_release_requests(user):
    return ReleaseRequest.objects.filter(instrument__in=scoped_instruments(user))


def scoped_audit_events(user):
    """Audit history for the records this user may see. The auditor sees all submitted history."""
    return AuditEvent.objects.filter(instrument__in=scoped_instruments(user))


def scoped_access_logs(user):
    """Who accessed what. Auditors only: nobody else may read the access log."""
    require_auditor(user)
    from access.models import AccessLog
    return AccessLog.objects.all()


def require_officer(user):
    if role(user) != 'officer':
        raise PermissionDenied('An officer account is required.')


def require_authority(user):
    if role(user) != 'authority':
        raise PermissionDenied('An authority account is required.')


def require_auditor(user):
    if role(user) != 'auditor':
        raise PermissionDenied('An auditor account is required.')


def require_clearance(user, unit=None):
    """A clearance-unit account, optionally of one specific unit (PGRC, VIGILANCE or GRANTS)."""
    assigned = clearance_unit(user)
    if unit is not None and assigned != unit:
        raise PermissionDenied('This task belongs to a different clearance unit.')
    return assigned
