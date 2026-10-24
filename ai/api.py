from django.shortcuts import get_object_or_404
from django.urls import path
from rest_framework.response import Response

from portal.api.records import RecordEndpoint
from portal.models import Document
from portal.permissions import scoped_instruments
from .services import extract


class Extract(RecordEndpoint):
    def post(self, request, pk):
        document = get_object_or_404(Document.objects.filter(instrument__in=scoped_instruments(request.user)), pk=pk)
        return Response(extract(request.user, document, consent=request.data.get('consent') is True,
                                synthetic=request.data.get('synthetic') is True))


urlpatterns = [path('documents/<int:pk>/ai-extract/', Extract.as_view())]
