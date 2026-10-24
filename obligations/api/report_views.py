from datetime import datetime

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiTypes
from rest_framework import serializers
from access.logging import log_access
from portal.api.pagination import StandardPagination

from obligations import imports, reports
from obligations.kpis import KpiInputError
from .views import OwnedView, body


class CsvUpload(serializers.Serializer):
    file = serializers.FileField()


class CommitInput(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=2000)


@extend_schema_view(post=extend_schema(request=CsvUpload, responses={200: OpenApiTypes.OBJECT}))
class CsvPreview(OwnedView):
    parser_classes = [MultiPartParser]
    def post(self, request):
        from portal.permissions import require_officer
        require_officer(request.user)
        if set(request.data) != {'file'} or len(request.FILES.getlist('file')) != 1:
            raise ValidationError({'file': 'Supply one CSV file.'})
        upload = request.FILES['file']
        content = upload.read(1024 * 1024 + 1)
        return Response(imports.preview(request.user, content))


@extend_schema_view(post=extend_schema(request=CommitInput, responses={200: OpenApiTypes.OBJECT}))
class CsvCommit(OwnedView):
    def post(self, request, pk):
        data = body(request, {'version', 'reason'})
        return Response(imports.commit(request.user, pk, data.get('version'), data.get('reason')))


@extend_schema_view(get=extend_schema(parameters=[OpenApiParameter('kind', str, location='path'),
    OpenApiParameter('download', str, enum=['xlsx'])], responses={200: OpenApiTypes.OBJECT}))
class Report(OwnedView):
    def get(self, request, kind):
        if set(request.query_params) - {'download', 'page', 'page_size'} or request.query_params.get('download', '') not in {'', 'xlsx'}:
            raise ValidationError({'download': 'Use download=xlsx or omit it.'})
        result = reports.report_rows(request.user, kind)
        if request.query_params.get('download') == 'xlsx':
            log_access(request, 'REPORT', object_type='s4_report', detail=kind)
            response = HttpResponse(reports.xlsx_bytes(result), content_type=
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="simulated-{kind}.xlsx"'
            return response
        paginator = StandardPagination()
        rows = paginator.paginate_queryset(result.pop('rows'), request)
        log_access(request, 'REPORT', object_type='s4_report', detail=kind)
        response = paginator.get_paginated_response(rows)
        response.data.update(result, rows=rows)  # Retain the owned rows alias for existing consumers.
        return response


@extend_schema_view(get=extend_schema(parameters=[OpenApiParameter('window_start', str, required=True),
    OpenApiParameter('window_end', str, required=True)], responses={200: OpenApiTypes.OBJECT}))
class Kpis(OwnedView):
    def get(self, request):
        try:
            if set(request.query_params) != {'window_start', 'window_end'}:
                raise ValueError
            start = datetime.fromisoformat(request.query_params['window_start'])
            end = datetime.fromisoformat(request.query_params['window_end'])
            result = reports.kpi_report(request.user, window_start=start, window_end=end)
        except (KeyError, ValueError, KpiInputError):
            raise ValidationError({'window': 'Supply ordered aware window_start/window_end no later than now.'}) from None
        log_access(request, 'REPORT', object_type='s4_kpis', detail='Selected event cohort')
        return Response(result)
