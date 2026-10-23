"""Safe operational failures without retrying consequential requests."""
import logging

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
