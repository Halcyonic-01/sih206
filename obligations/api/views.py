"""Thin owned endpoints; provisional integration surface, not K1 replacement."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, IntegrityError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from portal.permissions import role
from portal.services import WorkflowError
from obligations import services
from obligations.models import DepositObligation, InstitutionProfile, ProgrammeApproval, RuleSet
from obligations.rules import RuleInputError


class OwnedView(APIView):
    # TODO(K1): consume the agreed shared base/auth/error adapters when supplied.
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        status, code, fields = None, None, None
        if isinstance(exc, services.DependencyUnavailable):
            status, code = 503, 'DEPENDENCY_UNAVAILABLE'
        elif isinstance(exc, (ValidationError, RuleInputError)):
            status, code = 400, 'VALIDATION_ERROR'
            if isinstance(exc, ValidationError):
                fields = getattr(exc, 'message_dict', None)
                errors = [e for group in getattr(exc, 'error_dict', {}).values() for e in group]
                if any(e.code in {'unique','unique_together'} for e in errors):
                    status, code, fields = 409, 'IDENTITY_CONFLICT', None
        elif isinstance(exc, WorkflowError):
            status, code = 409, 'WORKFLOW_CONFLICT'
        elif isinstance(exc, IntegrityError):
            status, code = 409, 'IDENTITY_CONFLICT'
        elif isinstance(exc, (DatabaseError, OSError)):
            status, code = 503, 'SERVICE_UNAVAILABLE'
        elif isinstance(exc, Http404):
            status, code = 404, 'NOT_FOUND'
        elif isinstance(exc, PermissionDenied):
            status, code = 403, 'PERMISSION_DENIED'
        if status is not None:
            return Response({'error': {'code': code, 'fields': fields}}, status=status)
        return super().handle_exception(exc)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response


def body(request, allowed):
    values = request.data
    services.strict_fields(values, allowed)
    return dict(values)


def pagination(request):
    try:
        number = int(request.query_params.get('page', '1'))
        size = int(request.query_params.get('page_size', '25'))
        if number < 1 or not 1 <= size <= 100 or number > 100000:
            raise ValueError
    except ValueError:
        raise ValidationError({'page': 'Use a positive page and page_size 1–100.'}) from None
    return number, size


def page(request, query, serializer):
    number, size = pagination(request)
    start = (number - 1) * size
    return Response({'count': query.count(), 'page': number, 'page_size': size,
                     'results': [serializer(item) for item in query.order_by('pk')[start:start + size]]})


def institution_json(item, actor):
    profile = InstitutionProfile.objects.filter(institution=item).first()
    return {'id': item.pk, 'code': item.code, 'name': item.name,
        'profile': services.snapshot(profile) if profile else None,
        'version': profile.version if profile else None,
        'actions': {'can_edit': role(actor) == 'officer' and profile is not None}}


class Institutions(OwnedView):
    def get(self, request):
        query = services.scoped_institutions(request.user)
        q = request.query_params.get('q', '')
        if len(q) > 100:
            raise ValidationError({'q': 'Search text is limited to 100 characters.'})
        query = query.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(deposit_profile__aicte_id__icontains=q))
        return page(request, query, lambda i: institution_json(i, request.user))

    def post(self, request):
        data = body(request, services.PROFILE_FIELDS | {'code', 'name', 'reason'})
        reason = data.pop('reason', None)
        profile = services.create_institution(request.user, data, reason)
        return Response(institution_json(profile.institution, request.user), status=201)


class InstitutionDetail(OwnedView):
    def get(self, request, pk):
        return Response(institution_json(services.institution(request.user, pk), request.user))

    def patch(self, request, pk):
        data = body(request, services.PROFILE_FIELDS | {'code', 'name', 'version', 'reason'})
        profile = services.update_institution(request.user, pk, data.pop('version', None), data,
                                             data.pop('reason', None))
        return Response(institution_json(profile.institution, request.user))


class Children(OwnedView):
    model = ProgrammeApproval

    def get(self, request, pk):
        item = services.institution(request.user, pk)
        return page(request, self.model.objects.filter(institution=item), services.snapshot)

    def post(self, request, pk):
        allowed = services.APPROVAL_FIELDS if self.model is ProgrammeApproval else services.OBLIGATION_FIELDS
        data = body(request, allowed | {'reason'})
        record = services.save_child(request.user, self.model, pk, data, data.pop('reason', None))
        return Response(services.snapshot(record), status=201)


class Obligations(Children):
    model = DepositObligation


class ChildDetail(OwnedView):
    model = ProgrammeApproval

    def get(self, request, pk):
        if self.model is DepositObligation:
            return Response(services.obligation_detail(request.user, pk))
        item = get_object_or_404(self.model.objects.filter(institution__in=services.scoped_institutions(request.user)), pk=pk)
        return Response(services.snapshot(item))

    def patch(self, request, pk):
        item = get_object_or_404(self.model.objects.filter(institution__in=services.scoped_institutions(request.user)), pk=pk)
        allowed = services.APPROVAL_FIELDS if self.model is ProgrammeApproval else services.OBLIGATION_FIELDS
        data = body(request, allowed | {'version', 'reason'})
        version, reason = data.pop('version', None), data.pop('reason', None)
        record = services.save_child(request.user, self.model, item.institution_id, data, reason, pk, version)
        return Response(services.snapshot(record))


class ObligationDetail(ChildDetail):
    model = DepositObligation


class Calculator(OwnedView):
    def post(self, request):
        data = body(request, {'institution_id', 'rule_set_id', 'approvals'})
        for field in ['institution_id', 'rule_set_id']:
            if type(data.get(field)) is not int or data[field] < 1:
                raise ValidationError({field: 'Supply a positive integer identity.'})
        return Response(services.calculator(request.user, data['institution_id'],
                        data['rule_set_id'], data.get('approvals')))


class Rules(OwnedView):
    def get(self, request):
        services.scoped_institutions(request.user)
        return page(request, RuleSet.objects.all(), lambda r: {
            'id': r.pk, 'code': r.code, 'version': r.version,
            'effective_from': r.effective_from, 'effective_to': r.effective_to,
            'policy_label': 'DRAFT_DEMO_NOT_APPROVED'})
