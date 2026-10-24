"""Same-origin session endpoints; standard Django CSRF and password authentication."""
import hashlib
import json
from time import time
from django.contrib.auth import authenticate, login as session_login, logout as session_logout
from django.core.cache import cache
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from django.urls import path
from portal.permissions import institution_for, role


@never_cache
@ensure_csrf_cookie
@require_GET
def csrf(request):
    return JsonResponse({'csrfToken': get_token(request)})


@never_cache
@require_GET
def me(request):
    return session_response(request)


def session_response(request):
    current = role(request.user)
    if not current:
        return JsonResponse({'detail': 'Sign in with an active portal account.'}, status=401)
    return JsonResponse({'id': request.user.pk, 'username': request.user.username, 'role': current,
        'institution_id': institution_for(request.user).pk if current == 'institution' else None})


@never_cache
@csrf_protect
@require_POST
def login(request):
    # Fixed windows, atomic counters. Configure a shared cache for multiple production workers.
    remote = hashlib.sha256(request.META.get('REMOTE_ADDR', '').encode()).hexdigest()
    key = f'portal-login:{remote}:{int(time()//60)}'
    cache.add(key, 0, timeout=120)
    if cache.incr(key) > 5:
        response = JsonResponse({'detail': 'Too many attempts. Try again in one minute.'}, status=429)
        response['Retry-After'] = '60'
        return response
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {'username', 'password'} or any(
            not isinstance(data[key], str) or len(data[key]) > 1024 for key in data):
            raise ValueError()
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'detail': 'Provide username and password.'}, status=400)
    user = authenticate(request, username=data['username'], password=data['password'])
    if not user or not role(user):
        return JsonResponse({'detail': 'Invalid account credentials.'}, status=401)
    session_login(request, user)
    return session_response(request)


@never_cache
@csrf_protect
@require_POST
def logout(request):
    session_logout(request)
    return JsonResponse({'logged_out': True})


urlpatterns = [path('auth/csrf/', csrf), path('auth/me/', me), path('auth/login/', login), path('auth/logout/', logout)]
