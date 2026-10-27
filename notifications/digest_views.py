from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, transaction
from django.db.models import F
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from access.logging import log_access
from access.models import AccessLog
from portal.permissions import role
from portal.services import WorkflowError
from .digest_sources import prepare_digest
from .digest import DigestInputError
from .models import DigestPreference

PREFERENCE = inline_serializer('WeeklyDigestPreference', {
    'enabled': serializers.BooleanField(), 'version': serializers.IntegerField(min_value=0),
    'dispatch_enabled': serializers.BooleanField(read_only=True)})
PREVIEW = {'type': 'object', 'additionalProperties': True}


class DigestView(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, (DatabaseError, OSError, DigestInputError)):
            return Response({'detail': 'Digest source unavailable. Retry later.', 'code': 'unavailable'}, status=503)
        return super().handle_exception(exc)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not role(request.user):
            raise PermissionDenied('A single active portal role is required.')


class DigestPreferenceView(DigestView):
    @extend_schema(responses=PREFERENCE)
    def get(self, request):
        row = DigestPreference.objects.filter(user=request.user).first()
        return Response({'enabled': row.enabled if row else True, 'version': row.version if row else 0,
                         'dispatch_enabled': bool(getattr(settings, 'WEEKLY_DIGEST_ENABLED', False))})

    @extend_schema(request=PREFERENCE, responses=PREFERENCE)
    @transaction.atomic
    def patch(self, request):
        if type(request.data) is not dict or set(request.data) != {'enabled', 'version'} or type(request.data['enabled']) is not bool or type(request.data['version']) is not int or request.data['version'] < 0:
            raise serializers.ValidationError('Supply enabled (boolean) and current version (integer).')
        row, created = DigestPreference.objects.get_or_create(user=request.user, defaults={'version': 1})
        version = request.data['version']
        if version == 0:
            # First save must not overwrite a preference created concurrently.
            if not created:
                raise WorkflowError('Record changed. Reload your email preference.')
            row.enabled = request.data['enabled']
            row.save(update_fields=['enabled'])
        elif not DigestPreference.objects.filter(pk=row.pk, version=version).update(enabled=request.data['enabled'], version=F('version') + 1):
            raise WorkflowError('Record changed. Reload your email preference.')
        log_access(request, 'DIGEST_PREFERENCE_CHANGED', object_type='digestpreference', object_id=row.pk,
                   detail=f'Weekly digest enabled={request.data["enabled"]}; previous version={version}')
        row.refresh_from_db()
        return Response({'enabled': row.enabled, 'version': row.version,
                         'dispatch_enabled': bool(getattr(settings, 'WEEKLY_DIGEST_ENABLED', False))})


class DigestPreviewView(DigestView):
    @extend_schema(responses={200: PREVIEW})
    def get(self, request):
        if request.query_params:
            raise serializers.ValidationError('Digest preview always uses your own current scope; no parameters accepted.')
        log_access(request, AccessLog.SEARCH, object_type='weeklydigest', object_id=request.user.pk,
                   detail='Own scoped aggregate digest preview')
        return Response(prepare_digest(request.user, as_of=timezone.now(), portal_base_url=settings.PORTAL_BASE_URL))
