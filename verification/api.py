import json

from django.shortcuts import get_object_or_404
from rest_framework.response import Response

from portal.api.records import RecordEndpoint, item_for
from portal.permissions import require_officer, scoped_instruments
from .models import StatementImport
from .services import checks, import_statement, plan_matches


class Evidence(RecordEndpoint):
    def get(self, request, pk):
        item = item_for(request.user, pk)
        evidence = item.verification_evidence.order_by('-created_at', '-pk')
        return Response({'level': item.verification_level, 'checks': checks(request.user, item),
            'evidence': list(evidence.values('id', 'method', 'result', 'source', 'instrument_version',
                'fields_observed', 'document_id', 'created_at')),
            'notice': 'Document review and simulated matches do not establish bank authenticity.'})


class Statements(RecordEndpoint):
    def get(self, request):
        require_officer(request.user)
        return Response(list(StatementImport.objects.order_by('-created_at').values(
            'id', 'source', 'simulated', 'created_at')[:100]))

    def post(self, request):
        require_officer(request.user)
        file = request.FILES.get('document')
        if file is None or file.size > 1024 * 1024:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('A synthetic CSV file of at most 1 MB is required.')
        content = file.read()
        if request.data.get('commit') != 'true':
            planned = plan_matches(request.user, content)
            return Response({'simulated': True, 'rows': planned,
                'versions': {str(r['instrument_id']): r['version'] for r in planned if r['instrument_id']}})
        versions = json.loads(request.data.get('versions', '{}'))
        batch, existing = import_statement(request.user, content, request.data.get('source', ''), versions)
        return Response({'id': batch.pk, 'existing': existing, 'simulated': True,
            'rows': list(batch.lines.values('number', 'utr', 'amount_paise', 'value_date', 'result', 'instrument_id'))})
