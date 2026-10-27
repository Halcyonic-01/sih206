"""Read-only readiness endpoint; existing source failures never become zeros."""
from django.db import DatabaseError
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.response import Response

from access.logging import log_access
from access.models import AccessLog
from obligations import readiness_sources
from obligations.readiness import ReadinessInputError
from portal.permissions import role
from portal.api.schema_types import JSON, responses
from .views import OwnedView, Unavailable


@extend_schema_view(get=extend_schema(operation_id='institution_deposit_readiness',
    description='Scoped six-step deposit-readiness snapshot, not regulatory compliance. No workflow writes.',
    responses=responses(JSON)))
class Readiness(OwnedView):
    def get(self, request, pk):
        if request.query_params:
            from django.core.exceptions import ValidationError
            raise ValidationError('Readiness uses the server business date; query overrides are not supported.')
        result = readiness_sources.assemble(request.user, pk)
        if role(request.user) in {'officer', 'authority'}:
            log_access(request, AccessLog.SEARCH, object_type='institution', object_id=pk,
                       detail='Scoped institution deposit-readiness snapshot')
        return Response(result)

    def handle_exception(self, exc):
        if isinstance(exc, (DatabaseError, OSError, ReadinessInputError)):
            exc = Unavailable()
        return super().handle_exception(exc)
