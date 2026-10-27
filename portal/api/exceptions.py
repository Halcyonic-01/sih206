"""One error envelope for the whole API: {"detail": str, "code": str, "errors": {...}?}.

WorkflowError -> 409, PermissionDenied -> 403, missing rows -> 404, database or storage outage -> 503.
"""
import logging

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from portal.services import WorkflowError

logger = logging.getLogger(__name__)

CODES = {
    status.HTTP_400_BAD_REQUEST: 'validation_error',
    status.HTTP_401_UNAUTHORIZED: 'not_authenticated',
    status.HTTP_403_FORBIDDEN: 'permission_denied',
    status.HTTP_404_NOT_FOUND: 'not_found',
    status.HTTP_405_METHOD_NOT_ALLOWED: 'method_not_allowed',
    status.HTTP_409_CONFLICT: 'conflict',
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: 'unsupported_media_type',
    status.HTTP_429_TOO_MANY_REQUESTS: 'throttled',
    status.HTTP_503_SERVICE_UNAVAILABLE: 'unavailable',
}
UNAVAILABLE = ('Service temporarily unavailable. The action could not be confirmed. '
               'Reload the record and check its status before retrying.')


def envelope(http_status, detail, code=None, errors=None, headers=None):
    body = {'detail': str(detail), 'code': code or CODES.get(http_status, 'error')}
    if errors:
        body['errors'] = errors
    return Response(body, status=http_status, headers=headers)


def exception_handler(exc, context):
    if isinstance(exc, WorkflowError):
        return envelope(status.HTTP_409_CONFLICT, exc or 'This record changed. Reload it before trying again.')
    if isinstance(exc, PermissionDenied):
        return envelope(status.HTTP_403_FORBIDDEN, exc or 'You do not have permission to perform this action.',
                        code=getattr(exc, 'code', None))
    if isinstance(exc, (Http404, ObjectDoesNotExist)):
        return envelope(status.HTTP_404_NOT_FOUND, 'Not found.')
    if isinstance(exc, DjangoValidationError):
        errors = exc.message_dict if hasattr(exc, 'error_dict') else {'non_field_errors': exc.messages}
        return envelope(status.HTTP_400_BAD_REQUEST, 'Invalid input.', errors=errors)
    if isinstance(exc, (DatabaseError, OSError)):
        # Same rule as OperationalSafetyMiddleware: never echo SQL, paths or exception text.
        logger.warning('Operational API failure: %s', type(exc).__name__)
        return envelope(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE)
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    if response.status_code == status.HTTP_400_BAD_REQUEST:
        errors = data if isinstance(data, dict) else {'non_field_errors': data}
        response.data = {'detail': 'Invalid input.', 'code': CODES[400], 'errors': errors}
    else:
        detail = data.get('detail', '') if isinstance(data, dict) else data
        response.data = {'detail': str(detail), 'code': CODES.get(response.status_code, 'error')}
    return response
