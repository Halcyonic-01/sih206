"""Y3/Y5 feature endpoints. K1 mounts records_urls under /api/."""
from drf_spectacular.utils import extend_schema, extend_schema_view
from .schema_types import PAGINATION, FILE, responses
from . import records_schema as docs

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from portal.api.authentication import ApiSessionAuthentication
from rest_framework.exceptions import ValidationError as ApiValidationError
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from access import mfa
from access.logging import log_access
from access.models import AccessLog
from portal import record_operations, record_reporting, services
from portal.deadlines import business_today, classify_maturity
from portal.exports import register_csv
from portal.models import Document, Instrument
from portal.notification_hook import notify_record
from portal.permissions import institution_for, role, scoped_instruments
from portal.queue_ageing import submission_waits
from portal.scanning import downloadable
from portal.uploads import DocumentIntegrityError, open_verified, record_integrity_failure
from portal.validation import run_checks
from verification.services import field_provenance
from .records_serializers import ActionInput, RecordWrite, UploadInput


class RecordEndpoint(APIView):
    authentication_classes = [ApiSessionAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if role(request.user) is None:
            raise PermissionDenied('This account has no portal role.')

    def handle_exception(self, exc):
        if isinstance(exc, services.WorkflowError):
            return Response({'detail': str(exc)}, status=409)
        if isinstance(exc, ValidationError):
            return Response({'errors': exc.message_dict if hasattr(exc, 'message_dict') else exc.messages}, status=400)
        if isinstance(exc, ValueError):
            return Response({'detail': str(exc)}, status=400)
        if isinstance(exc, ObjectDoesNotExist):
            raise Http404 from None
        if isinstance(exc, (DatabaseError, OSError)):
            return Response({'detail': 'Operation unavailable. Reload before retrying.'}, status=503)
        return super().handle_exception(exc)


def item_for(user, pk):
    return get_object_or_404(scoped_instruments(user).select_related('institution', 'obligation'), pk=pk)


def actions(user, item):
    own = role(user) == 'institution' and item.institution_id == institution_for(user).pk
    editable = own and item.status in ['DRAFT', 'CHANGES_REQUESTED']
    reviewable = role(user) == 'officer' and item.created_by_id != user.pk and item.status == 'SUBMITTED'
    return {'can_edit': editable, 'can_submit': editable, 'can_upload': editable,
            'can_request_bank': role(user) == 'officer' and item.created_by_id != user.pk
                                and item.status in ('SUBMITTED', 'ACCEPTED') and not item.released_at and not item.superseded_at,
            'can_review': reviewable, 'can_observe': reviewable, 'can_correct': reviewable,
            'can_renew': own and item.is_current and not item.has_active_release
                         and not Instrument.objects.filter(predecessor=item).exists(),
            'can_upload_release_documents': own and record_operations.release_documents_allowed(item),
            'can_request_release': own and record_operations.release_documents_allowed(item)
                                   and item.obligation_id is not None}


def release_case_id(user, item):
    from casework.services import scoped_cases
    return scoped_cases(user).filter(release__instrument=item).order_by('-pk').values_list('pk', flat=True).first()


def brief(item, wait=None):
    return {'waiting': wait, 'id': item.pk, 'reference': item.reference, 'bank': item.bank,
        'institution': {'id': item.institution_id, 'code': item.institution.code, 'name': item.institution.name},
        'amount': str(item.amount), 'issue_date': item.issue_date, 'maturity_date': item.maturity_date,
        'mode': item.mode, 'status': item.status, 'version': item.version,
        'verification_level': item.verification_level, 'released': item.is_released,
        'superseded': item.is_superseded}


def link_reason(item):
    """Why the successor replaces the predecessor (recorded when the renewal draft was opened), seen from either end; or None."""
    successor = item if item.predecessor_id else Instrument.objects.filter(predecessor=item).first()
    if successor is None:
        return None
    event = successor.audit_events.filter(action='DRAFT_CREATED').order_by('pk').first()
    link = (event.after or {}).get('renewal_link') if event else None
    return {'reason': link['reason'], 'note': link.get('note', '')} if link else {'reason': 'NOT_RECORDED', 'note': ''}


def detail(user, item):
    result = brief(item)
    result.update({key: getattr(item, key) for key in [
        'obligation_id', 'ifsc', 'branch', 'holder_names', 'utr', 'lien_marked']})
    visible = scoped_instruments(user)
    result.update(actions=actions(user, item), release_case_id=release_case_id(user, item),
        documents=[{'id': d.pk, 'name': d.original_name, 'kind': d.kind,
            'page_count': d.page_count, 'sha256': d.sha256, 'uploaded_at': d.created_at, 'scan_status': d.scan_status,
            'download_url': f'/api/documents/{d.pk}/download/'} for d in item.documents.all()],
        observations=[services.observation_snapshot(o) for o in item.observations.all()],
        history=[{'id': e.pk, 'action': e.action, 'reason': e.reason, 'actor_id': e.actor_id,
                  'at': e.created_at, 'before': e.before, 'after': e.after} for e in item.audit_events.all()],
        findings=[f.as_dict() for f in run_checks(item)],
        field_provenance=field_provenance(item),
        lineage={'predecessor': visible.filter(pk=item.predecessor_id).values('id', 'reference').first(),
                 'successor': visible.filter(predecessor=item).values('id', 'reference').first(),
                 'link': link_reason(item)},
        maturity=classify_maturity(item.maturity_date, business_today()).__dict__)
    return result


@extend_schema_view(
    get=extend_schema(operation_id='records_list', parameters=docs.FILTERS + PAGINATION, responses=responses(docs.REGISTER)),
    post=extend_schema(request=docs.RecordCreate, responses=responses(docs.DETAIL, 201)))
class Records(RecordEndpoint):
    def get(self, request):
        records, _ = record_reporting.query_records(request.user, request.query_params)
        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('page_size', 20))
        if page < 1 or not 1 <= size <= 100:
            raise ValueError('Page must be positive and page_size between 1 and 100.')
        count = records.count()
        rows = list(records[(page-1)*size:page*size])
        waits = submission_waits(rows, business_today())
        return Response({'count': count, 'page': page, 'page_size': size,
            'results': [brief(item, waits.get(item.pk)) for item in rows]})

    def post(self, request):
        institution = institution_for(request.user)
        serializer = RecordWrite(data=request.data, context={'institution_id': institution.pk})
        serializer.is_valid(raise_exception=True)
        item = services.save_draft(request.user, serializer.validated_data)
        return Response(detail(request.user, item), status=201)


@extend_schema_view(
    get=extend_schema(responses=responses(docs.DETAIL)),
    patch=extend_schema(request=docs.RecordUpdate, responses=responses(docs.DETAIL)))
class RecordDetail(RecordEndpoint):
    def get(self, request, pk):
        return Response(detail(request.user, item_for(request.user, pk)))

    def patch(self, request, pk):
        item = item_for(request.user, pk)
        institution = institution_for(request.user)
        serializer = RecordWrite(data=request.data, context={'item': item, 'institution_id': institution.pk})
        serializer.is_valid(raise_exception=True)
        item = services.save_draft(request.user, serializer.validated_data, pk)
        return Response(detail(request.user, item))


@extend_schema_view(post=extend_schema(
    description='Requires the current version. Review also requires decision and reason; observations require document ID, severity and comment; resolution requires resolution text. Renewal requires new deposit fields. Upload requires a PDF and kind.',
    responses={**responses(docs.DETAIL), 201: docs.DETAIL}))
class RecordAction(RecordEndpoint):
    schema = docs.RecordActionSchema()

    @transaction.atomic
    def post(self, request, pk, action, observation_pk=None):
        item = item_for(request.user, pk)
        if action == 'renew':
            institution = institution_for(request.user)
            data = request.data.copy()
            data['predecessor_version'] = data.get('version')
            serializer = RecordWrite(data=data, context={'institution_id': institution.pk})
            serializer.is_valid(raise_exception=True)
            if 'predecessor_version' not in serializer.validated_data:
                raise ApiValidationError({'version': 'A current predecessor version is required.'})
            successor = services.save_draft(request.user, serializer.validated_data, predecessor_id=pk)
            return Response(detail(request.user, successor), status=201)
        if action == 'upload':
            serializer = UploadInput(data=request.data)
        else:
            serializer = ActionInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        version = values['version']
        queued = None
        if action == 'submit':
            item = services.submit(request.user, pk, version)
            queued = getattr(item, '_notification_queued', False)
        elif action == 'review':
            if not {'decision', 'reason'} <= set(values):
                raise ApiValidationError('Decision and reason are required.')
            item = services.review(request.user, pk, version, values['decision'], values['reason'])
            queued = getattr(item, '_notification_queued', False)
        elif action == 'observe':
            if not {'document', 'severity', 'comment'} <= set(values):
                raise ApiValidationError('Document, severity and comment are required.')
            document = get_object_or_404(item.documents, pk=values['document'])
            services.add_observation(request.user, pk, version, document,
                values.get('page_number'), values['severity'], values['comment'])
        elif action == 'resolve':
            get_object_or_404(item.observations, pk=observation_pk)
            if 'resolution' not in values:
                raise ApiValidationError({'resolution': 'A resolution is required.'})
            services.resolve_observation(request.user, pk, observation_pk, version, values['resolution'])
        elif action == 'upload':
            record_operations.upload_document(request.user, pk, version, values['document'], values['kind'])
        else:
            raise Http404
        item.refresh_from_db()
        result = detail(request.user, item)
        if queued is not None:
            result['notification_queued'] = queued
        return Response(result)


@extend_schema_view(post=extend_schema(request=docs.CORRECTION, responses=responses(docs.DETAIL)))
class CorrectRecord(RecordEndpoint):
    def post(self, request, pk):
        mfa.require_recent_mfa(request)  # an officer correction rewrites a submitted record
        item = item_for(request.user, pk)
        serializer = RecordWrite(data=request.data, context={'item': item, 'institution_id': item.institution_id})
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        reason = request.data.get('reason', '')
        if not isinstance(reason, str) or len(reason) > 2000:
            raise ApiValidationError({'reason': 'Use a correction reason of at most 2000 characters.'})
        changes = {key: value for key, value in values.items() if key not in ['version', 'predecessor_version', 'document', 'amount']}
        changes['amount_paise'] = int(values['amount'] * 100)
        corrected = record_operations.correct_record(request.user, pk, values['version'], changes, reason)
        return Response(detail(request.user, corrected))


@extend_schema_view(get=extend_schema(responses={**{code: value for code, value in responses(FILE).items() if code != 200}, (200, 'application/pdf'): FILE}))
class Download(RecordEndpoint):
    def get(self, request, pk):
        document = get_object_or_404(Document.objects.filter(instrument__in=scoped_instruments(request.user)), pk=pk)
        if not downloadable(document):
            quarantined = document.scan_status == 'REJECTED'
            return Response({'detail': 'This document was quarantined by the malware scan.' if quarantined else
                             'This document has not been scanned yet and cannot be downloaded.',
                             'code': 'document_quarantined' if quarantined else 'document_not_scanned'}, status=409)
        try:
            file = open_verified(document)
        except FileNotFoundError:
            raise Http404 from None
        except DocumentIntegrityError as error:
            with transaction.atomic():
                record_integrity_failure(error, request.user)
            log_access(request, AccessLog.DOCUMENT_DOWNLOAD, document,
                       detail=f'instrument={document.instrument_id} refused=integrity')
            return Response({'detail': 'This document failed its integrity check and cannot be downloaded. '
                                       'The officers have been told.', 'code': 'document_integrity_failed'}, status=409)
        log_access(request, AccessLog.DOCUMENT_DOWNLOAD, document, detail=f'instrument={document.instrument_id}')
        response = FileResponse(file, content_type='application/pdf', as_attachment=True,
                                filename=document.original_name)
        response['Cache-Control'] = 'no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


@extend_schema_view(get=extend_schema(parameters=docs.FILTERS,
    responses={(200, 'text/csv'): {'type': 'string'}}))
class Export(RecordEndpoint):
    def get(self, request):
        records, as_of = record_reporting.query_records(request.user, request.query_params)
        log_access(request, AccessLog.EXPORT, object_type='instrument_register',
                   detail=f'rows={records.count()} query={request.query_params.urlencode()[:200]}')
        return register_csv(records, as_of)


@extend_schema_view(get=extend_schema(parameters=docs.FILTERS, responses=responses(docs.DASHBOARD)))
class Dashboard(RecordEndpoint):
    def get(self, request):
        return Response(record_reporting.dashboard(request.user, request.query_params))
