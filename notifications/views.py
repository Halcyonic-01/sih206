from django.db.models import Count
from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from portal.api.permissions import has_role
from .models import DeliveryAttempt, Notification
from .serializers import NotificationSerializer


def inbox(user):
    """A person only ever sees their own in-app notifications."""
    return Notification.objects.filter(recipient=user, channel=Notification.Channel.IN_APP)


class InboxView(generics.ListAPIView):
    serializer_class = NotificationSerializer

    @extend_schema(parameters=[OpenApiParameter('unread', bool, description='Only unread notifications')])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        rows = inbox(self.request.user)
        if self.request.query_params.get('unread', '').lower() in ('1', 'true', 'yes'):
            rows = rows.filter(read_at__isnull=True)
        return rows


class UnreadCountView(APIView):
    @extend_schema(responses=inline_serializer('UnreadCount', {'count': serializers.IntegerField()}))
    def get(self, request):
        return Response({'count': inbox(request.user).filter(read_at__isnull=True).count()})


class MarkReadView(APIView):
    @extend_schema(request=None, responses=NotificationSerializer)
    def post(self, request, pk):
        row = inbox(request.user).filter(pk=pk).first()
        if row is None:
            raise Http404
        if row.read_at is None:
            row.read_at = timezone.now()
            row.save(update_fields=['read_at'])
        return Response(NotificationSerializer(row).data)


class MarkAllReadView(APIView):
    @extend_schema(request=None, responses=inline_serializer('MarkedRead', {'marked': serializers.IntegerField()}))
    def post(self, request):
        marked = inbox(request.user).filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({'marked': marked})


class DeliveryStatusView(APIView):
    """Operations view: email delivery health without any message content. Auditors only."""
    permission_classes = [has_role('auditor')]

    @extend_schema(responses=inline_serializer('DeliveryStatus', {
        'counts': serializers.DictField(child=serializers.IntegerField()),
        'failures': serializers.ListField(child=serializers.DictField()),
    }))
    def get(self, request):
        emails = Notification.objects.filter(channel=Notification.Channel.EMAIL)
        counts = {row['status']: row['n'] for row in emails.values('status').annotate(n=Count('pk'))}
        failures = [
            {'id': row.pk, 'template_id': row.template_id, 'status': row.status, 'attempts': row.attempts,
             'last_error': row.last_error, 'next_attempt_at': row.next_attempt_at, 'created_at': row.created_at}
            for row in emails.exclude(last_error='').order_by('-created_at')[:20]
        ]
        return Response({'counts': {'PENDING': 0, 'SENT': 0, 'FAILED': 0, **counts}, 'failures': failures,
                         'attempts_recorded': DeliveryAttempt.objects.count()})
