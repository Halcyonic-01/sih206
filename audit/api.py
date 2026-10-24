"""Read-only auditor endpoints: audit-trail explorer and access log (K7). Auditor role only."""
import csv
from datetime import date, datetime, time, timedelta
from io import StringIO
from zoneinfo import ZoneInfo

from django.conf import settings
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_field, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from access.logging import log_access
from access.models import AccessLog
from portal.api.permissions import has_role
from portal.exports import spreadsheet_text
from portal.models import AuditEvent
from portal.permissions import scoped_access_logs, scoped_audit_events
from .chain import verify_chain

EXPORT_LIMIT = 5000
SKIP_DIFF = {'version'}


def parse_day(value, name):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError({name: ['Use YYYY-MM-DD.']}) from None


def apply_date_range(rows, params, field='created_at'):
    """Inclusive date range in the business timezone."""
    zone = ZoneInfo(settings.TIME_ZONE)
    if params.get('date_from'):
        start = datetime.combine(parse_day(params['date_from'], 'date_from'), time.min, zone)
        rows = rows.filter(**{f'{field}__gte': start})
    if params.get('date_to'):
        end = datetime.combine(parse_day(params['date_to'], 'date_to') + timedelta(days=1), time.min, zone)
        rows = rows.filter(**{f'{field}__lt': end})
    return rows


def positive_int(params, name):
    value = params.get(name)
    if value in (None, ''):
        return None
    if not value.isdigit():
        raise ValidationError({name: ['Must be a whole number.']})
    return int(value)


class InstrumentRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    reference = serializers.CharField()
    institution = serializers.CharField(help_text='Institution code')


class ActorRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()


class ChangeSerializer(serializers.Serializer):
    field = serializers.CharField()
    before = serializers.JSONField(allow_null=True)
    after = serializers.JSONField(allow_null=True)


class SealSerializer(serializers.Serializer):
    hash = serializers.CharField()
    prev_hash = serializers.CharField(allow_blank=True)
    backfilled = serializers.BooleanField()


class AuditEventSerializer(serializers.ModelSerializer):
    instrument = serializers.SerializerMethodField()
    actor = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = ['id', 'created_at', 'action', 'reason', 'instrument', 'actor']

    @extend_schema_field(InstrumentRefSerializer)
    def get_instrument(self, event):
        item = event.instrument
        return {'id': item.pk, 'reference': item.reference, 'institution': item.institution.code}

    @extend_schema_field(ActorRefSerializer)
    def get_actor(self, event):
        return {'id': event.actor_id, 'username': event.actor.get_username()}


def changes(before, after):
    """Top-level fields that differ between the two snapshots (the version counter is noise)."""
    keys = [key for key in dict.fromkeys([*(before or {}), *(after or {})]) if key not in SKIP_DIFF]
    return [{'field': key, 'before': (before or {}).get(key), 'after': (after or {}).get(key)}
            for key in keys if (before or {}).get(key) != (after or {}).get(key)]


class AuditEventDetailSerializer(AuditEventSerializer):
    changes = serializers.SerializerMethodField()
    seal = serializers.SerializerMethodField()

    class Meta(AuditEventSerializer.Meta):
        fields = AuditEventSerializer.Meta.fields + ['before', 'after', 'changes', 'seal']

    @extend_schema_field(SealSerializer(allow_null=True))
    def get_seal(self, event):
        seal = getattr(event, 'seal', None)
        return {'hash': seal.hash, 'prev_hash': seal.prev_hash, 'backfilled': seal.backfilled} if seal else None

    @extend_schema_field(ChangeSerializer(many=True))
    def get_changes(self, event):
        return changes(event.before, event.after)


def filtered_events(request):
    rows = scoped_audit_events(request.user).select_related('instrument__institution', 'actor')
    params = request.query_params
    if (instrument := positive_int(params, 'instrument')) is not None:
        rows = rows.filter(instrument_id=instrument)
    if params.get('q'):
        rows = rows.filter(instrument__reference__icontains=params['q'])
    if params.get('institution'):
        rows = rows.filter(instrument__institution__code=params['institution'])
    if (actor := positive_int(params, 'actor')) is not None:
        rows = rows.filter(actor_id=actor)
    if params.get('actor_name'):
        rows = rows.filter(actor__username__icontains=params['actor_name'])
    actions = [value for value in params.getlist('action') if value]
    if actions:
        rows = rows.filter(action__in=actions)
    return apply_date_range(rows, params).order_by('-created_at', '-pk')


EVENT_PARAMETERS = [
    OpenApiParameter('instrument', int, description='Instrument id'),
    OpenApiParameter('q', str, description='Reference contains'),
    OpenApiParameter('institution', str, description='Institution code'),
    OpenApiParameter('actor', int, description='Actor user id'),
    OpenApiParameter('actor_name', str, description='Actor username contains'),
    OpenApiParameter('action', str, many=True, description='One or more action codes'),
    OpenApiParameter('date_from', str, description='YYYY-MM-DD, business timezone'),
    OpenApiParameter('date_to', str, description='YYYY-MM-DD, inclusive'),
]


class AuditEventList(ListAPIView):
    permission_classes = [has_role('auditor')]
    serializer_class = AuditEventSerializer

    @extend_schema(parameters=EVENT_PARAMETERS)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return filtered_events(self.request)


class AuditEventDetail(RetrieveAPIView):
    permission_classes = [has_role('auditor')]
    serializer_class = AuditEventDetailSerializer

    def get_queryset(self):
        return scoped_audit_events(self.request.user).select_related('instrument__institution', 'actor')


class AuditFacetsSerializer(serializers.Serializer):
    actions = serializers.ListField(child=serializers.CharField())
    actors = ActorRefSerializer(many=True)
    institutions = serializers.ListField(child=serializers.CharField())


class AccessFacetsSerializer(serializers.Serializer):
    actions = serializers.ListField(child=serializers.CharField())
    object_types = serializers.ListField(child=serializers.CharField())


class AuditFacets(APIView):
    """Values for the filter drop-downs."""
    permission_classes = [has_role('auditor')]

    @extend_schema(responses=AuditFacetsSerializer)
    def get(self, request):
        events = scoped_audit_events(request.user)
        actors = events.order_by('actor__username').values('actor_id', 'actor__username').distinct()
        return Response({
            'actions': list(events.order_by('action').values_list('action', flat=True).distinct()),
            'actors': [{'id': row['actor_id'], 'username': row['actor__username']} for row in actors],
            'institutions': list(events.order_by('instrument__institution__code')
                                 .values_list('instrument__institution__code', flat=True).distinct()),
        })


class AccessLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessLog
        fields = ['id', 'created_at', 'username', 'user', 'action', 'object_type', 'object_id', 'detail', 'path',
                  'ip_address', 'user_agent', 'request_id']


def filtered_access_logs(request):
    rows = scoped_access_logs(request.user)
    params = request.query_params
    if (user := positive_int(params, 'user')) is not None:
        rows = rows.filter(user_id=user)
    if params.get('username'):
        rows = rows.filter(username__icontains=params['username'])
    actions = [value for value in params.getlist('action') if value]
    if actions:
        rows = rows.filter(action__in=actions)
    if params.get('object_type'):
        rows = rows.filter(object_type=params['object_type'])
    if (object_id := positive_int(params, 'object_id')) is not None:
        rows = rows.filter(object_id=object_id)
    if params.get('ip'):
        rows = rows.filter(ip_address=params['ip'])
    return apply_date_range(rows, params).order_by('-created_at', '-pk')


ACCESS_PARAMETERS = [
    OpenApiParameter('user', int), OpenApiParameter('username', str, description='Username contains'),
    OpenApiParameter('action', str, many=True), OpenApiParameter('object_type', str),
    OpenApiParameter('object_id', int), OpenApiParameter('ip', str),
    OpenApiParameter('date_from', str), OpenApiParameter('date_to', str),
]


class AccessLogList(ListAPIView):
    permission_classes = [has_role('auditor')]
    serializer_class = AccessLogSerializer

    @extend_schema(parameters=ACCESS_PARAMETERS)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return filtered_access_logs(self.request)


class AccessLogFacets(APIView):
    permission_classes = [has_role('auditor')]

    @extend_schema(responses=AccessFacetsSerializer)
    def get(self, request):
        rows = scoped_access_logs(request.user)
        return Response({
            'actions': list(rows.order_by('action').values_list('action', flat=True).distinct()),
            'object_types': list(rows.exclude(object_type='').order_by('object_type')
                                 .values_list('object_type', flat=True).distinct()),
        })


def csv_response(filename, header, lines):
    output = StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(header)
    for line in lines:
        writer.writerow([spreadsheet_text(cell) if isinstance(cell, str) else cell for cell in line])
    response = HttpResponse('﻿' + output.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


class AuditEventExport(APIView):
    permission_classes = [has_role('auditor')]

    @extend_schema(parameters=EVENT_PARAMETERS, responses={(200, 'text/csv'): bytes})
    def get(self, request):
        rows = list(filtered_events(request)[:EXPORT_LIMIT])
        log_access(request, AccessLog.EXPORT, object_type='audit_events',
                   detail=f'rows={len(rows)} query={request.META.get("QUERY_STRING", "")[:200]}')
        return csv_response('audit-trail.csv',
                            ['Event ID', 'Time', 'Institution', 'Reference', 'Instrument ID', 'Actor', 'Action', 'Reason'],
                            [[e.pk, e.created_at.isoformat(), e.instrument.institution.code, e.instrument.reference,
                              e.instrument_id, e.actor.get_username(), e.action, e.reason] for e in rows])


class AccessLogExport(APIView):
    permission_classes = [has_role('auditor')]

    @extend_schema(parameters=ACCESS_PARAMETERS, responses={(200, 'text/csv'): bytes})
    def get(self, request):
        rows = list(filtered_access_logs(request)[:EXPORT_LIMIT])
        log_access(request, AccessLog.EXPORT, object_type='access_log',
                   detail=f'rows={len(rows)} query={request.META.get("QUERY_STRING", "")[:200]}')
        return csv_response('access-log.csv',
                            ['ID', 'Time', 'Username', 'Action', 'Object type', 'Object ID', 'Detail', 'Path', 'IP',
                             'User agent', 'Request ID'],
                            [[r.pk, r.created_at.isoformat(), r.username, r.action, r.object_type, r.object_id,
                              r.detail, r.path, r.ip_address, r.user_agent, r.request_id] for r in rows])


class ChainVerify(APIView):
    """Recompute the whole hash chain. Read-only; safe to call repeatedly."""
    permission_classes = [has_role('auditor')]

    @extend_schema(responses=inline_serializer('ChainVerification', {
        'status': serializers.ChoiceField(choices=['ok', 'broken', 'incomplete']),
        'checked': serializers.IntegerField(), 'backfilled': serializers.IntegerField(),
        'unsealed': serializers.IntegerField(), 'head': serializers.CharField(),
        'broken': serializers.ListField(child=serializers.DictField()),
    }))
    def get(self, request):
        return Response(verify_chain().as_dict())
