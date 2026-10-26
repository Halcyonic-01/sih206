from drf_spectacular.utils import extend_schema, extend_schema_view
from portal.api.schema_types import responses
from .schema import CONSENT, EXTRACTION

from django.shortcuts import get_object_or_404
from django.urls import path
from rest_framework.response import Response

from portal.api.records import RecordEndpoint
from portal.models import Document
from portal.permissions import scoped_instruments
from .services import extract
from .ocr import extract_local


@extend_schema_view(post=extend_schema(request={'application/json': CONSENT}, responses=responses(EXTRACTION)))
class Extract(RecordEndpoint):
    def post(self, request, pk):
        document = get_object_or_404(Document.objects.filter(instrument__in=scoped_instruments(request.user)), pk=pk)
        return Response(extract(request.user, document, consent=request.data.get('consent') is True,
                                synthetic=request.data.get('synthetic') is True))


@extend_schema_view(post=extend_schema(request=None, responses=responses(EXTRACTION)))
class LocalOcr(RecordEndpoint):
    def post(self, request, pk):
        document = get_object_or_404(Document.objects.filter(instrument__in=scoped_instruments(request.user)), pk=pk)
        return Response(extract_local(request.user, document))


urlpatterns = [path('documents/<int:pk>/ai-extract/', Extract.as_view()),
               path('documents/<int:pk>/ocr/', LocalOcr.as_view())]
