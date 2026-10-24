"""Minimal Yash workspace mount; K2 may replace this with the shared shell."""
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

from .permissions import role


@login_required
@never_cache
@ensure_csrf_cookie
def workspace(request):
    current_role = role(request.user)
    if current_role is None:
        raise PermissionDenied('This account has no portal role.')
    index = settings.BASE_DIR / 'frontend' / 'dist' / 'records' / 'index.html'
    if not index.exists():
        return HttpResponse('Build the records frontend first: cd frontend && npm ci && npm run build', status=503,
                            content_type='text/plain')
    return HttpResponse(index.read_text(encoding='utf-8').replace('__PORTAL_ROLE__', current_role))
