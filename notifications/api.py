from django.shortcuts import get_object_or_404
from django.urls import path
from django.utils import timezone
from rest_framework.response import Response
from portal.api.records import RecordEndpoint
from portal.permissions import require_officer
from .models import Notification
from .services import TEMPLATES


class Inbox(RecordEndpoint):
    def get(self, request):
        rows = Notification.objects.filter(recipient=request.user, channel='IN_APP').order_by('-created_at')[:100]
        return Response([{'id': row.pk, 'title': TEMPLATES.get(row.template, 'Deposit portal update'),
            'reference': row.context.get('reference', ''), 'instrument_id': row.context.get('instrument_id'),
            'created_at': row.created_at, 'read_at': row.read_at} for row in rows])


class Read(RecordEndpoint):
    def post(self, request, pk):
        row = get_object_or_404(Notification, pk=pk, recipient=request.user, channel='IN_APP')
        if row.read_at is None:
            Notification.objects.filter(pk=row.pk, read_at__isnull=True).update(read_at=timezone.now())
        return Response({'read': True})


class Deliveries(RecordEndpoint):
    def get(self, request):
        require_officer(request.user)
        return Response(list(Notification.objects.order_by('-created_at').values(
            'id', 'template', 'channel', 'status', 'attempts', 'last_error', 'created_at', 'sent_at')[:100]))


urlpatterns = [path('notifications/', Inbox.as_view()), path('notifications/<int:pk>/read/', Read.as_view()),
               path('notifications/deliveries/', Deliveries.as_view())]
