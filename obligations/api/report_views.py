from datetime import datetime

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from rest_framework.response import Response

from obligations import imports, reports
from obligations.kpis import KpiInputError
from .views import OwnedView, body


class CsvPreview(OwnedView):
    def post(self, request):
        from portal.permissions import require_officer
        require_officer(request.user)
        if set(request.data) != {'file'} or len(request.FILES.getlist('file')) != 1:
            raise ValidationError({'file': 'Supply one CSV file.'})
        upload = request.FILES['file']
        content = upload.read(1024 * 1024 + 1)
        return Response(imports.preview(request.user, content))


class CsvCommit(OwnedView):
    def post(self, request, pk):
        data = body(request, {'version', 'reason'})
        return Response(imports.commit(request.user, pk, data.get('version'), data.get('reason')))


class Report(OwnedView):
    def get(self, request, kind):
        result = reports.report_rows(request.user, kind)
        if request.query_params.get('download') == 'xlsx':
            response = HttpResponse(reports.xlsx_bytes(result), content_type=
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="simulated-{kind}.xlsx"'
            return response
        return Response(result)


class Kpis(OwnedView):
    def get(self, request):
        try:
            start = datetime.fromisoformat(request.query_params['window_start'])
            end = datetime.fromisoformat(request.query_params['window_end'])
            return Response(reports.kpi_report(request.user, window_start=start, window_end=end))
        except (KeyError, ValueError, KpiInputError):
            raise ValidationError({'window': 'Supply ordered aware window_start/window_end no later than now.'}) from None
