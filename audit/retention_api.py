"""Retention endpoints: what is due, archive, and legal hold (P3-1)."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response

from portal import retention
from portal.api.records import RecordEndpoint
from portal.models import Instrument
from portal.permissions import role, scoped_instruments

REASON = inline_serializer('RetentionReason', {'reason': serializers.CharField(max_length=500)})
RESULT = inline_serializer('RetentionState', {'archived': serializers.BooleanField(), 'legal_hold': serializers.BooleanField(),
                                              'archival_due': serializers.BooleanField()})


def _item(request, pk):
    return get_object_or_404(scoped_instruments(request.user), pk=pk)


class Due(RecordEndpoint):
    @extend_schema(responses=inline_serializer('ArchivalDue', {'results': serializers.ListField(child=serializers.DictField())}))
    def get(self, request):
        if role(request.user) not in ('officer', 'authority', 'auditor'):
            return Response({'results': []})
        return Response({'results': [{'id': item.pk, 'reference': item.reference, 'institution': item.institution.name,
                                      **retention.state(item)} for item in retention.due_records(request.user)[:200]]})


class Archive(RecordEndpoint):
    @extend_schema(request=REASON, responses=RESULT)
    def post(self, request, pk):
        item = _item(request, pk)
        retention.archive(request.user, item, request.data.get('reason'))
        return Response(retention.state(item))


class Hold(RecordEndpoint):
    @extend_schema(request=REASON, responses=RESULT)
    def post(self, request, pk):
        item = _item(request, pk)
        retention.set_legal_hold(request.user, item, request.data.get('reason'))
        return Response(retention.state(item))

    @extend_schema(request=REASON, responses=RESULT)
    def delete(self, request, pk):
        item = _item(request, pk)
        retention.lift_legal_hold(request.user, item, request.data.get('reason'))
        return Response(retention.state(item))
