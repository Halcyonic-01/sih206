"""Owned endpoints using the shared K1 authentication, errors and pagination."""
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter

from access.logging import log_access
from access.models import AccessLog
from portal.api.pagination import StandardPagination

from portal.permissions import role
from portal.services import WorkflowError
from obligations import services
from obligations.models import DepositObligation, InstitutionProfile, ProgrammeApproval, RuleSet
from obligations.rules import RuleInputError
from . import schemas


class OwnedView(APIView):
    def handle_exception(self, exc):
        # Normalize only owned domain exceptions, then use K1's single handler.
        # DependencyUnavailable subclasses WorkflowError but is not a 409 conflict.
        if isinstance(exc, services.DependencyUnavailable):
            exc = Unavailable()
        elif isinstance(exc, RuleInputError):
            exc = ValidationError({'non_field_errors': [str(exc)]})
        elif isinstance(exc, IntegrityError):
            exc = WorkflowError('Identity conflict. Reload and check the existing record.')
        elif isinstance(exc, ValidationError):
            errors = [e for group in getattr(exc, 'error_dict', {}).values() for e in group]
            if any(e.code in {'unique', 'unique_together'} for e in errors):
                exc = WorkflowError('Identity conflict. Reload and check the existing record.')
        return super().handle_exception(exc)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response


class Unavailable(APIException):
    status_code = 503
    default_detail = 'Required source integration unavailable. Reload saved state before retrying.'
    default_code = 'unavailable'


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
    paginator = StandardPagination()
    records = paginator.paginate_queryset(query.order_by('pk'), request)
    return paginator.get_paginated_response([serializer(item) for item in records])


def institution_json(item, actor):
    profile = InstitutionProfile.objects.filter(institution=item).first()
    return {'id': item.pk, 'code': item.code, 'name': item.name,
        'profile': services.snapshot(profile) if profile else None,
        'version': profile.version if profile else None,
        'actions': {'can_edit': role(actor) == 'officer' and profile is not None}}


PAGE_PARAMETERS = [OpenApiParameter('page', int), OpenApiParameter('page_size', int)]


@extend_schema_view(
    get=extend_schema(operation_id='s2_institutions_list', parameters=PAGE_PARAMETERS + [OpenApiParameter('q', str)],
        responses=schemas.responses(schemas.InstitutionPage)),
    post=extend_schema(request=schemas.InstitutionCreate,
        responses=schemas.responses(schemas.InstitutionRead, created=True)))
class Institutions(OwnedView):
    def get(self, request):
        query = services.scoped_institutions(request.user)
        q = request.query_params.get('q', '')
        if len(q) > 100:
            raise ValidationError({'q': 'Search text is limited to 100 characters.'})
        query = query.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(deposit_profile__aicte_id__icontains=q))
        response = page(request, query, lambda i: institution_json(i, request.user))
        if role(request.user) in {'officer', 'authority'}:
            log_access(request, AccessLog.SEARCH, object_type='institution',
                       detail='Scoped institution master search')
        return response

    def post(self, request):
        data = body(request, services.PROFILE_FIELDS | {'code', 'name', 'reason'})
        reason = data.pop('reason', None)
        profile = services.create_institution(request.user, data, reason)
        return Response(institution_json(profile.institution, request.user), status=201)


@extend_schema_view(
    get=extend_schema(responses=schemas.responses(schemas.InstitutionRead)),
    patch=extend_schema(request=schemas.InstitutionUpdate,
        responses=schemas.responses(schemas.InstitutionRead)))
class InstitutionDetail(OwnedView):
    def get(self, request, pk):
        return Response(institution_json(services.institution(request.user, pk), request.user))

    def patch(self, request, pk):
        data = body(request, services.PROFILE_FIELDS | {'code', 'name', 'version', 'reason'})
        profile = services.update_institution(request.user, pk, data.pop('version', None), data,
                                             data.pop('reason', None))
        return Response(institution_json(profile.institution, request.user))


@extend_schema_view(
    get=extend_schema(parameters=PAGE_PARAMETERS, responses=schemas.responses(schemas.ApprovalPage)),
    post=extend_schema(request=schemas.ApprovalCreate,
        responses=schemas.responses(schemas.ApprovalRead, created=True)))
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


@extend_schema_view(
    get=extend_schema(parameters=PAGE_PARAMETERS, responses=schemas.responses(schemas.ObligationPage)),
    post=extend_schema(request=schemas.ObligationCreate,
        responses=schemas.responses(schemas.ObligationRead, created=True)))
class Obligations(Children):
    model = DepositObligation


@extend_schema_view(
    get=extend_schema(responses=schemas.responses(schemas.ApprovalRead)),
    patch=extend_schema(request=schemas.ApprovalUpdate,
        responses=schemas.responses(schemas.ApprovalRead)))
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


@extend_schema_view(
    get=extend_schema(responses=schemas.responses(schemas.ObligationDetailRead)),
    patch=extend_schema(request=schemas.ObligationUpdate,
        responses=schemas.responses(schemas.ObligationRead)))
class ObligationDetail(ChildDetail):
    model = DepositObligation


@extend_schema_view(post=extend_schema(
    request=schemas.ProofReceiptInput,
    responses=schemas.responses(schemas.ObligationDetailRead)))
class ProofReceipts(OwnedView):
    """Officer records when deposit proof and Affidavit-3 were received (empty = reviewed, not received)."""
    def post(self, request, pk):
        data = body(request, {'version', 'payment_proof_on', 'affidavit_on', 'reason'})
        services.record_proof_receipts(request.user, pk, data.get('version'), data.get('payment_proof_on'),
                                       data.get('affidavit_on'), data.get('reason'))
        return Response(services.obligation_detail(request.user, pk))


@extend_schema_view(post=extend_schema(request=schemas.CalculatorRequest,
    responses=schemas.responses(schemas.CalculatorRead)))
class Calculator(OwnedView):
    def post(self, request):
        data = body(request, {'institution_id', 'rule_set_id', 'approvals'})
        for field in ['institution_id', 'rule_set_id']:
            if type(data.get(field)) is not int or data[field] < 1:
                raise ValidationError({field: 'Supply a positive integer identity.'})
        return Response(services.calculator(request.user, data['institution_id'],
                        data['rule_set_id'], data.get('approvals')))


@extend_schema_view(get=extend_schema(parameters=PAGE_PARAMETERS,
    responses=schemas.responses(schemas.RulePage)))
class Rules(OwnedView):
    def get(self, request):
        services.scoped_institutions(request.user)
        return page(request, RuleSet.objects.all(), lambda r: {
            'id': r.pk, 'code': r.code, 'version': r.version,
            'effective_from': r.effective_from, 'effective_to': r.effective_to,
            'policy_label': 'DRAFT_DEMO_NOT_APPROVED'})
