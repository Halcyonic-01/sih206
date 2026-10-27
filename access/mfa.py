"""Two-factor sign-in for staff and step-up before consequential actions (P1-3).

* Officer, authority, clearance and auditor accounts may enrol an authenticator app (TOTP). Once enrolled, sign-in needs the
  password and a code (portal.api.auth_views), and the actions below need a code entered in the last
  `MFA_STEP_UP_SECONDS` (default 10 minutes): release authorisation, letter issue, release completion and officer correction.
* `MFA_REQUIRED=true` makes enrolment compulsory for those roles: until a staff user has enrolled, the API only lets them reach
  /api/auth/*. Off (the default), staff who have not enrolled are not asked for a code.
* Institution accounts do not use this feature.
"""
import time
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from portal.permissions import role

from . import totp
from .models import MfaDevice

MFA_ROLES = frozenset({'officer', 'authority', 'clearance', 'auditor'})
MAX_FAILURES = 5
LOCK_MINUTES = 15
PENDING = 'mfa_pending'
VERIFIED_AT = 'mfa_verified_at'


class MfaStepUpRequired(PermissionDenied):
    code = 'mfa_step_up_required'


class MfaEnrolmentRequired(PermissionDenied):
    code = 'mfa_enrolment_required'


class MfaLocked(PermissionDenied):
    code = 'mfa_locked'


def in_scope(user):
    return user.is_authenticated and role(user) in MFA_ROLES


def required(user):
    return bool(getattr(settings, 'MFA_REQUIRED', False)) and in_scope(user)


def device_for(user):
    """The confirmed device, or None."""
    return MfaDevice.objects.filter(user=user, confirmed_at__isnull=False).first()


def has_device(user):
    return in_scope(user) and device_for(user) is not None


def check_code(user, code):
    """Verify a code against the user's confirmed device, enforcing replay protection and the failure lock."""
    from django.db import transaction
    with transaction.atomic():
        device = (MfaDevice.objects.select_for_update().filter(user=user, confirmed_at__isnull=False).first())
        if device is None:
            return False
        return _check_device(device, code)


def _check_device(device, code):
    now = timezone.now()
    if device.locked_until and device.locked_until > now:
        raise MfaLocked('Too many wrong codes. Try again in a few minutes.')
    step = totp.verify(device.secret, code, last_step=device.last_step)
    if step is None:
        device.failures += 1
        device.locked_until = now + timedelta(minutes=LOCK_MINUTES) if device.failures >= MAX_FAILURES else None
        if device.failures >= MAX_FAILURES:
            device.failures = 0
        device.save(update_fields=['failures', 'locked_until'])
        return False
    device.last_step, device.failures, device.locked_until = step, 0, None
    device.save(update_fields=['last_step', 'failures', 'locked_until'])
    return True


def mark_verified(request):
    request.session[VERIFIED_AT] = int(time.time())


def verified_recently(request):
    stamp = request.session.get(VERIFIED_AT)
    return type(stamp) is int and 0 <= time.time() - stamp <= int(getattr(settings, 'MFA_STEP_UP_SECONDS', 600))


def status(request, user=None):
    user = user or request.user
    return {'in_scope': in_scope(user), 'enrolled': has_device(user), 'required': required(user),
            'verified_recently': verified_recently(request) if has_device(user) else False}


def require_recent_mfa(request):
    """Raise unless the user has no second factor to ask for, or has used it recently."""
    user = request.user
    if not in_scope(user):
        return
    if device_for(user) is None:
        if required(user):
            raise MfaEnrolmentRequired('Set up two-factor sign-in before using this action.')
        return
    if not verified_recently(request):
        raise MfaStepUpRequired('Enter a code from your authenticator app to continue.')
