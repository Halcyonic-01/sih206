"""Write access-log rows. Call `log_access` from any endpoint that serves a document, export or report."""
from axes.helpers import get_client_ip_address

from .models import AccessLog


def _http_request(request):
    # DRF wraps the Django request; middleware only sees the original one.
    return getattr(request, '_request', request)


def log_access(request, action, obj=None, *, object_type='', object_id=None, detail=''):
    """Record one access. `obj` (a model instance) fills object_type and object_id.

    Fails closed: if the row cannot be written the request fails, so nothing leaves the system unlogged.
    """
    http = _http_request(request)
    if obj is not None:
        object_type = object_type or obj._meta.model_name
        object_id = obj.pk if object_id is None else object_id
    user = getattr(http, 'user', None)
    authenticated = bool(user and user.is_authenticated)
    row = AccessLog.objects.create(
        user=user if authenticated else None,
        username=user.get_username()[:150] if authenticated else '',
        action=action[:40], object_type=object_type[:40], object_id=object_id,
        detail=detail[:500], path=http.path[:300],
        ip_address=get_client_ip_address(http) or None,
        user_agent=http.META.get('HTTP_USER_AGENT', '')[:300],
        request_id=getattr(http, 'request_id', '')[:64],
    )
    http.access_logged = True
    return row
