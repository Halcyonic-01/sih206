"""Safe operational failures without retrying consequential requests."""
import logging
import re
import uuid

from django.db import DatabaseError
from django.http import HttpResponse
from django.utils.cache import add_never_cache_headers

logger = logging.getLogger(__name__)


class OperationalSafetyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Edit/validation pages contain the same private fields as the register.
        add_never_cache_headers(response)
        return response

    def process_exception(self, request, exception):
        if not isinstance(exception, (DatabaseError, OSError)):
            return None
        # Services have already left their atomic blocks and performed file cleanup.
        # Avoid SQL, exception messages, filenames, applicant values or request bodies.
        logger.warning('Operational request failure: %s', type(exception).__name__)
        return HttpResponse(
            'Service temporarily unavailable. The action could not be confirmed. '
            'Reload the record and check its status before retrying. '
            'If the problem continues, contact the portal operator.',
            status=503, content_type='text/plain; charset=utf-8',
        )


_REQUEST_ID = re.compile(r'^[A-Za-z0-9._-]{8,64}$')


class RequestIdMiddleware:
    """Gives every request an ID for logs and the access log; honours a sane inbound X-Request-ID."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        inbound = request.META.get('HTTP_X_REQUEST_ID', '')
        request.request_id = inbound if _REQUEST_ID.match(inbound) else uuid.uuid4().hex
        response = self.get_response(request)
        response['X-Request-ID'] = request.request_id
        return response


# The React build is plain script/style files. Ant Design injects <style> tags at runtime, which is
# why style-src allows 'unsafe-inline'; scripts stay limited to our own origin.
CONTENT_SECURITY_POLICY = '; '.join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "frame-src 'self'",
    "object-src 'self'",
    "worker-src 'self' blob:",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'self'",
])
# Swagger UI initialises itself with one inline script.
DOCS_CONTENT_SECURITY_POLICY = CONTENT_SECURITY_POLICY.replace(
    "script-src 'self'", "script-src 'self' 'unsafe-inline'")
PERMISSIONS_POLICY = 'camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()'


class SecurityHeadersMiddleware:
    """CSP and Permissions-Policy; Django's own middleware covers nosniff, referrer and COOP."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if 'Content-Security-Policy' not in response:
            docs = request.path.startswith('/api/docs/')
            response['Content-Security-Policy'] = DOCS_CONTENT_SECURITY_POLICY if docs else CONTENT_SECURITY_POLICY
        response.setdefault('Permissions-Policy', PERMISSIONS_POLICY)
        return response
