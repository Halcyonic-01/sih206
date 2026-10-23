from django.core.exceptions import PermissionDenied

from .models import Instrument, UserProfile

INSTITUTION_GROUP = 'Institution'
OFFICER_GROUP = 'Officer'
AUTHORITY_GROUP = 'Authority'


def role(user):
    if not user.is_authenticated or not user.is_active:
        return None
    groups = set(user.groups.values_list('name', flat=True))
    # Ambiguous role membership fails closed.
    roles = {INSTITUTION_GROUP: 'institution', OFFICER_GROUP: 'officer', AUTHORITY_GROUP: 'authority'}
    assigned = groups.intersection(roles)
    return roles[assigned.pop()] if len(assigned) == 1 else None


def institution_for(user):
    if role(user) != 'institution':
        raise PermissionDenied('An institution account is required.')
    try:
        return UserProfile.objects.select_related('institution').get(user=user).institution
    except UserProfile.DoesNotExist:
        raise PermissionDenied('No institution is assigned to this account.')


def scoped_instruments(user):
    current_role = role(user)
    if current_role in ('officer', 'authority'):
        # Drafts are private until the first submission. Corrected records stay visible.
        return Instrument.objects.exclude(status=Instrument.Status.DRAFT)
    if current_role == 'institution':
        return Instrument.objects.filter(institution=institution_for(user))
    raise PermissionDenied('This account has no portal role.')


def require_officer(user):
    if role(user) != 'officer':
        raise PermissionDenied('An officer account is required.')


def require_authority(user):
    if role(user) != 'authority':
        raise PermissionDenied('An authority account is required.')
