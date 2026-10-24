from axes.helpers import get_client_ip_address
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import AccessLog


def _write(request, action, user=None, username=''):
    if request is None:
        return
    http = getattr(request, '_request', request)
    AccessLog.objects.create(
        user=user if user is not None and user.pk else None,
        username=(username or (user.get_username() if user is not None else ''))[:150],
        action=action, path=http.path[:300],
        ip_address=get_client_ip_address(http) or None,
        user_agent=http.META.get('HTTP_USER_AGENT', '')[:300],
        request_id=getattr(http, 'request_id', '')[:64],
    )


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    _write(request, AccessLog.LOGIN, user)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    _write(request, AccessLog.LOGOUT, user)


@receiver(user_login_failed)
def on_failed_login(sender, credentials, request=None, **kwargs):
    # Only the attempted username is kept; the password in `credentials` is never read.
    _write(request, AccessLog.LOGIN_FAILED, username=str(credentials.get('username', '')))
