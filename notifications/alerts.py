"""Open actions raised by the scheduled rules: list them and let a person take charge (P2-3)."""
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from access.logging import log_access
from portal.api.exceptions import envelope
from portal.permissions import institution_for, role, scoped_instruments

from .models import AlertAction


def visible_alerts(user):
    """Region-aware scope: the records the user can see, plus institution-level alerts of institutions they can see."""
    current = role(user)
    if current == 'institution':
        institution = institution_for(user)
        return AlertAction.objects.filter(Q(institution=institution) | Q(instrument__institution=institution))
    if current in ('officer', 'authority', 'auditor'):
        from obligations.services import scoped_institutions
        try:
            institutions = scoped_institutions(user)
        except PermissionDenied:  # auditors have no institution master access: records only
            institutions = None
        mine = Q(instrument__in=scoped_instruments(user))
        if institutions is not None:
            mine |= Q(instrument__isnull=True, institution__in=institutions)
        return AlertAction.objects.filter(mine)
    return AlertAction.objects.none()


def alert_json(alert, user=None):
    return {'id': alert.pk, 'rule': alert.rule, 'reference': alert.reference, 'summary': alert.summary, 'url': alert.url,
            'instrument_id': alert.instrument_id, 'status': alert.status, 'opened_on': alert.opened_on,
            'acknowledged_by': alert.acknowledged_by.get_username() if alert.acknowledged_by_id else None,
            'acknowledged_at': alert.acknowledged_at, 'note': alert.note, 'escalation_level': alert.escalation_level,
            'can_acknowledge': bool(user) and role(user) in ('officer', 'authority') and alert.status == AlertAction.Status.OPEN}


def open_alerts(user, limit=50):
    rows = (visible_alerts(user).exclude(status=AlertAction.Status.RESOLVED)
            .select_related('acknowledged_by').order_by('-escalation_level', 'opened_on', 'pk')[:limit])
    return [alert_json(row, user) for row in rows]


class AlertsView(APIView):
    @extend_schema(responses=inline_serializer('AlertList', {'results': serializers.ListField(child=serializers.DictField())}))
    def get(self, request):
        return Response({'results': open_alerts(request.user, 200)})


class AcknowledgeView(APIView):
    @extend_schema(request=inline_serializer('AlertAcknowledge', {'note': serializers.CharField(max_length=1000)}),
                   responses=inline_serializer('AlertAcknowledged', {'id': serializers.IntegerField(), 'status': serializers.CharField(),
                       'acknowledged_by': serializers.CharField(allow_null=True), 'note': serializers.CharField()}))
    def post(self, request, pk):
        if role(request.user) not in ('officer', 'authority'):
            raise PermissionDenied('Only officers and the authority can take charge of an action.')
        alert = visible_alerts(request.user).filter(pk=pk).first()
        if alert is None:
            raise Http404
        note = request.data.get('note')
        if type(note) is not str or not note.strip() or len(note) > 1000:
            return envelope(status.HTTP_400_BAD_REQUEST, 'Write a short note (at most 1,000 characters) on what you are doing about it.',
                            code='note_required')
        updated = AlertAction.objects.filter(pk=alert.pk, status=AlertAction.Status.OPEN).update(
            status=AlertAction.Status.ACKNOWLEDGED, acknowledged_by=request.user, acknowledged_at=timezone.now(), note=note.strip())
        if not updated:
            return envelope(status.HTTP_409_CONFLICT, 'This action was already acknowledged or has cleared. Reload it.')
        alert.refresh_from_db()
        log_access(request, 'ALERT_ACKNOWLEDGED', alert, detail=alert.key[:200])
        return Response(alert_json(alert, request.user))
