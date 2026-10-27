"""Idempotency-Key for API writes that create things (P2-4).

A client sends `Idempotency-Key: <uuid>` with a POST/PUT/PATCH/DELETE under /api/. For the same signed-in user and key:

* the first request runs; while it runs a duplicate gets 409 `request_in_progress` (a double click),
* once it succeeded (2xx) the same request again gets the stored response back and nothing runs a second time,
* the same key with a different request (path, method or body) gets 409 `idempotency_key_reused`,
* anything else (4xx, 5xx, a crash) is not stored, so a retry simply runs again.

Responses are kept 24 hours (`manage.py cleanup_idempotency`). Requests without the header are untouched. For multipart
uploads the body is not read into memory; its fingerprint is the content type, length and the key, which is enough to catch
a reused key on a different upload but not two different files of identical size.
"""
import hashlib
import re
from datetime import timedelta

from django.db import IntegrityError
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

from .models import IdempotentRequest

HEADER = 'HTTP_IDEMPOTENCY_KEY'
KEY = re.compile(r'^[A-Za-z0-9_-]{8,100}$')
WRITES = {'POST', 'PUT', 'PATCH', 'DELETE'}
KEEP = timedelta(hours=24)
MAX_STORED = 1024 * 1024
SKIP_PREFIXES = ('/api/auth/',)


def fingerprint(request):
    parts = [request.method, request.path, request.META.get('QUERY_STRING', '')]
    content_type = request.META.get('CONTENT_TYPE', '')
    if content_type.startswith('multipart/'):
        parts += ['multipart', request.META.get('CONTENT_LENGTH', '')]
    else:
        parts += [content_type.split(';')[0], hashlib.sha256(request.body).hexdigest()]
    return hashlib.sha256('\0'.join(parts).encode()).hexdigest()


def problem(status, detail, code):
    return JsonResponse({'detail': detail, 'code': code}, status=status)


class IdempotencyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        key = request.META.get(HEADER)
        if (key is None or request.method not in WRITES or not request.path.startswith('/api/')
                or request.path.startswith(SKIP_PREFIXES)):
            return self.get_response(request)
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return self.get_response(request)  # the view answers 401
        if not KEY.match(key):
            return problem(400, 'Idempotency-Key must be 8 to 100 letters, digits, - or _.', 'invalid_idempotency_key')
        digest = fingerprint(request)
        existing = IdempotentRequest.objects.filter(user=user, key=key).first()
        if existing is not None and existing.created_at < timezone.now() - KEEP:
            existing.delete()
            existing = None
        if existing is None:
            try:
                existing = IdempotentRequest.objects.create(user=user, key=key, fingerprint=digest, path=request.path[:300])
            except IntegrityError:  # a duplicate arrived at the same moment
                existing = IdempotentRequest.objects.get(user=user, key=key)
            else:
                return self.run(request, existing)
        if existing.fingerprint != digest:
            return problem(409, 'This Idempotency-Key was already used for a different request.', 'idempotency_key_reused')
        if existing.status_code is None:
            return problem(409, 'The same request is still being processed. Wait a moment and reload before trying again.',
                           'request_in_progress')
        response = HttpResponse(existing.body, status=existing.status_code, content_type=existing.content_type)
        response['Idempotent-Replay'] = 'true'
        return response

    def run(self, request, record):
        try:
            response = self.get_response(request)
        except BaseException:
            record.delete()
            raise
        body = b'' if getattr(response, 'streaming', False) else response.content
        if 200 <= response.status_code < 300 and len(body) <= MAX_STORED:
            IdempotentRequest.objects.filter(pk=record.pk).update(
                status_code=response.status_code, body=body, content_type=response.get('Content-Type', 'application/json'))
        else:
            record.delete()  # failures are never replayed; the client may simply try again
        return response
