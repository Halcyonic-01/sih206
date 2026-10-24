from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.response import Response

from obligations.api.views import OwnedView, body, page, pagination
from obligations.models import ClearanceTask, IssuedLetter, MasterAudit
from obligations.services import DependencyUnavailable
from portal.permissions import role
from . import services


def case_json(actor, case):
    readiness = None
    if case.release.status == 'PENDING':
        try:
            readiness = services.assessment(actor, case)
        except DependencyUnavailable:
            readiness = {'outcome': 'CONTEXT_UNAVAILABLE', 'projection_only': True, 'effects_applied': False}
    independent = role(actor) == 'authority' and actor.pk != case.release.requested_by_id
    independent = independent and not case.clearances.filter(decided_by=actor).exists()
    ready = readiness is not None and readiness['outcome'] == 'READY_FOR_AUTHORITY_REVIEW'
    letter = IssuedLetter.objects.filter(case=case).first()
    history = MasterAudit.objects.filter(entity='releasecase', entity_id=case.pk, institution_id=case.institution_id).order_by('-pk')
    return {'id': case.pk, 'institution_id': case.institution_id, 'obligation_id': case.obligation_id,
        'instrument_id': case.release.instrument_id, 'version': case.version,
        'instrument_version': case.release.instrument.version, 'status': case.release.status,
        'path': case.path, 'mode': case.mode, 'declarations': case.declarations,
        'template_ref': case.template_ref, 'application_reason': case.release.reason,
        'decision_reason': case.release.decision_reason, 'completion_notes': case.release.completion_notes,
        'documents': [{'id': d.pk, 'kind': d.kind, 'name': d.original_name,
            'page_count': getattr(d, 'page_count', None),
            'download_path': reverse('document_download', args=[d.pk])}
            for d in case.release.instrument.documents.order_by('pk')],
        'history': [{'action': h.action, 'reason': h.reason, 'at': h.created_at.isoformat()}
                    for h in history[:100]], 'history_has_more': history.count() > 100,
        'monitoring_active': case.release.instrument.is_current, 'readiness': readiness,
        'simulation_label': 'SIMULATED', 'policy_label': 'DRAFT_DEMO_NOT_APPROVED',
        'notification_status': 'ENQUEUE_ADAPTER_CONFIGURED_DELIVERY_UNVERIFIED' if callable(
            getattr(settings, 'SAKSHAM_NOTIFY', None)) else 'INTEGRATION_PENDING',
        'next_action': 'Separate evidence-backed completion' if case.release.status == 'APPROVED' else
                       'Review prerequisites' if case.release.status == 'PENDING' else 'Read recorded history',
        'responsible_party': 'Authority and institution' if case.release.status == 'APPROVED' else
                             'Institution and reviewing units' if case.release.status == 'PENDING' else 'No pending release action',
        'clearances': [{'unit': t.unit, 'status': t.status, 'reason': t.reason,
            'evidence_ref': t.evidence_ref, 'can_decide': case.release.status == 'PENDING' and t.status == 'OPEN'
            and services.clearance_allowed(actor, t)} for t in case.clearances.order_by('unit')],
        'penalties': [{'id': p.pk, 'kind': p.kind, 'amount_paise': p.amount_paise,
            'base_paise': p.base_paise, 'rate_bps': p.rate_bps, 'clause': p.clause,
            'status': p.status, 'reason': p.reason} for p in case.penalties.order_by('pk')],
        'penalty_review_complete': case.penalty_review_complete,
        'letter': None if letter is None else {'serial': letter.serial, 'kind': letter.kind,
            'revoked': letter.revoked_at is not None, 'unsigned_demo': True},
        'actions': {'can_approve': independent and ready, 'can_reject': independent and ready,
            'can_review_penalties': role(actor) == 'officer' and case.release.status == 'PENDING',
            'can_issue': independent and case.release.status == 'APPROVED' and letter is None,
            'can_complete': independent and case.release.status == 'APPROVED' and letter is not None and
                letter.revoked_at is None and callable(getattr(settings, 'SAKSHAM_COMPLETION_VALIDATOR', None)),
            'can_revoke': independent and letter is not None and letter.revoked_at is None}}


class Cases(OwnedView):
    def get(self, request):
        return page(request, services.scoped_cases(request.user).select_related('release__instrument'),
                    lambda c: case_json(request.user, c))

    def post(self, request):
        data = body(request, {'instrument_id','obligation_id','instrument_version','path','declarations','reason','template_ref'})
        for key in ['instrument_id','obligation_id']:
            if type(data.get(key)) is not int or data[key] < 1:
                raise ValidationError({key: 'Supply a positive integer identity.'})
        for key in ['instrument_version','path','declarations','reason','template_ref']:
            if key not in data:
                raise ValidationError({key: 'Required.'})
        case = services.request_case(request.user, **data)
        return Response(case_json(request.user, case), status=201)


class CaseDetail(OwnedView):
    def get(self, request, pk):
        return Response(case_json(request.user, services.get_case(request.user, pk)))


class CaseAction(OwnedView):
    def post(self, request, pk, action):
        if action == 'complete':
            if set(request.data) - {'version','instrument_version','notes','refund_reference','document'}:
                raise ValidationError('Unexpected completion field.')
            try:
                version = int(request.data['version'])
                instrument_version = int(request.data['instrument_version'])
            except (KeyError, TypeError, ValueError):
                raise ValidationError('Current versions are required.') from None
            if len(request.FILES.getlist('document')) != 1:
                raise ValidationError('A new completion PDF is required.')
            case = services.complete(request.user, pk, version, instrument_version,
                request.data.get('notes'), request.FILES['document'], request.data.get('refund_reference',''))
        elif action in {'approve','reject'}:
            data = body(request, {'version','instrument_version','reason'})
            case = services.decide(request.user, pk, data.get('version'), data.get('instrument_version'), action, data.get('reason'))
        elif action == 'issue':
            data = body(request, {'version','reason'})
            services.issue(request.user, pk, data.get('version'), data.get('reason'))
            case = services.get_case(request.user, pk)
        elif action == 'revoke':
            data = body(request, {'version','reason'})
            case = services.revoke(request.user, pk, data.get('version'), data.get('reason'))
        elif action == 'penalties':
            data = body(request, {'version','reason','kind','base_paise','confirm_id'})
            case = services.review_penalties(request.user, pk, data.get('version'), data.get('reason'),
                kind=data.get('kind'), base_paise=data.get('base_paise'), confirm_id=data.get('confirm_id'))
        else:
            raise Http404
        return Response(case_json(request.user, case))


class Clearance(OwnedView):
    def post(self, request, pk, unit):
        data = body(request, {'version','status','reason','evidence_ref'})
        case = services.decide_clearance(request.user, pk, unit, data.get('version'),
            data.get('status'), data.get('reason'), data.get('evidence_ref'))
        return Response(case_json(request.user, case))


class ClearanceQueue(OwnedView):
    def get(self, request):
        if not callable(getattr(settings, 'SAKSHAM_CLEARANCE_PERMISSION', None)):
            raise DependencyUnavailable('Clearance membership integration unavailable.')
        tasks = ClearanceTask.objects.filter(case__in=services.scoped_cases(request.user)).select_related('case__release')
        # TODO(K4): replace per-task callback with a server-scoped query adapter.
        visible = [{'case_id': t.case_id, 'version': t.case.version,
            'unit': t.unit, 'status': t.status, 'due_date': t.due_date,
            'can_decide': t.status == 'OPEN' and t.case.release.status == 'PENDING'}
            for t in tasks.order_by('pk') if services.clearance_allowed(request.user, t)]
        number, size = pagination(request)
        start = (number - 1) * size
        return Response({'count': len(visible), 'page': number, 'page_size': size,
                         'results': visible[start:start+size]})


class LetterDownload(OwnedView):
    def get(self, request, pk):
        case = services.get_case(request.user, pk)
        letter = get_object_or_404(IssuedLetter, case=case)
        response = HttpResponse(bytes(letter.pdf), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="synthetic-release-letter.pdf"'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class PublicVerify(OwnedView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, token):
        result = services.public_record(token)
        if result is None:
            raise Http404
        return Response(result)
