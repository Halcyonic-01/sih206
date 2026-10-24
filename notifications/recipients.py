"""Who to tell. Return users (inbox + email when they have an address) and outside addresses (email only)."""
from django.contrib.auth import get_user_model

from portal.models import UserProfile
from portal.permissions import (AUDITOR_GROUP, AUTHORITY_GROUP, CLEARANCE_GROUP, OFFICER_GROUP)


def _in_group(name):
    return list(get_user_model().objects.filter(groups__name=name, is_active=True).order_by('pk'))


def officers():
    return _in_group(OFFICER_GROUP)


def authorities():
    return _in_group(AUTHORITY_GROUP)


def auditors():
    return _in_group(AUDITOR_GROUP)


def clearance_users(unit=None):
    users = get_user_model().objects.filter(groups__name=CLEARANCE_GROUP, is_active=True)
    if unit:
        users = users.filter(unit_assignment__unit=unit)
    return list(users.order_by('pk'))


def institution_users(institution):
    return [profile.user for profile in UserProfile.objects.filter(
        institution=institution, user__is_active=True).select_related('user').order_by('pk')]


def institution_contacts(institution):
    """The institution's own users plus the contact address on its AICTE profile (when one exists)."""
    recipients = institution_users(institution)
    profile = getattr(institution, 'deposit_profile', None)
    if profile is not None and profile.contact_email:
        recipients.append(profile.contact_email)
    return recipients
