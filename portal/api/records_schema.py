"""Record response and action contracts for drf-spectacular."""
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.utils import OpenApiParameter
from rest_framework import serializers

from .records_serializers import ActionInput, RecordWrite, UploadInput
from .schema_types import (TEXT, INTEGER, BOOLEAN, DATE, DATETIME, JSON, array, nullable, obj, page)

INSTITUTION = obj({'id': INTEGER, 'code': TEXT, 'name': TEXT})
BRIEF = obj({
    'waiting': nullable(JSON), 'id': INTEGER, 'reference': TEXT, 'bank': TEXT, 'institution': INSTITUTION,
    'amount': TEXT, 'issue_date': DATE, 'maturity_date': DATE, 'mode': TEXT,
    'status': TEXT, 'version': INTEGER, 'verification_level': TEXT,
    'released': BOOLEAN, 'superseded': BOOLEAN,
})
DOCUMENT = obj({'id': INTEGER, 'name': TEXT, 'kind': TEXT, 'page_count': nullable(INTEGER),
                'sha256': TEXT, 'uploaded_at': DATETIME, 'download_url': TEXT, 'scan_status': TEXT})
OBSERVATION = obj({'id': INTEGER, 'document_id': INTEGER, 'page_number': nullable(INTEGER),
    'severity': TEXT, 'comment': TEXT, 'reviewer_id': INTEGER, 'created_at': DATETIME,
    'resolution': TEXT, 'resolved_by_id': nullable(INTEGER), 'resolved_at': nullable(DATETIME)})
HISTORY = obj({'id': INTEGER, 'action': TEXT, 'reason': TEXT, 'actor_id': INTEGER,
               'at': DATETIME, 'before': JSON, 'after': JSON})
DETAIL = obj({**BRIEF['properties'], 'obligation_id': nullable(INTEGER), 'ifsc': TEXT,
    'branch': TEXT, 'holder_names': TEXT, 'utr': TEXT, 'lien_marked': nullable(BOOLEAN),
    'actions': obj({name: BOOLEAN for name in ('can_edit', 'can_submit', 'can_upload',
        'can_request_bank', 'can_review', 'can_observe', 'can_correct', 'can_renew',
        'can_upload_release_documents', 'can_request_release')}),
    'release_case_id': nullable(INTEGER), 'documents': array(DOCUMENT),
    'observations': array(OBSERVATION), 'history': array(HISTORY), 'findings': array(JSON), 'field_provenance': JSON,
    'lineage': obj({key: nullable(obj({'id': INTEGER, 'reference': TEXT}))
                    for key in ('predecessor', 'successor')}), 'maturity': JSON,
    'notification_queued': BOOLEAN,
}, required=[*BRIEF['properties'], 'actions', 'documents', 'observations', 'history', 'findings', 'lineage', 'maturity'])
REGISTER = page(BRIEF)
COVERAGE = obj({'obligation_id': INTEGER, 'institution_id': INTEGER, 'institution': TEXT,
    'known': BOOLEAN, 'required_paise': nullable(INTEGER), 'held_paise': INTEGER,
    'shortfall_paise': nullable(INTEGER), 'coverage_end': nullable(DATE), 'term_end': nullable(DATE),
    'policy_label': TEXT}, required=['obligation_id', 'known', 'required_paise', 'held_paise', 'shortfall_paise'])
DASHBOARD = obj({'as_of': DATE, 'demo_date': BOOLEAN, 'counts': {'type': 'object', 'additionalProperties': INTEGER},
    'interventions': array(obj({'id': INTEGER, 'reference': TEXT, 'kind': TEXT, 'next_action': TEXT})),
    'alerts': array(JSON), 'maturity_calendar': array(JSON),
    'shortfalls': array(COVERAGE), 'coverage': array(COVERAGE), 'coverage_available': BOOLEAN,
    'maturity_chart': array(obj({'month': TEXT, 'count': INTEGER}))})
FILTERS = [OpenApiParameter(name, str, description=description) for name, description in (
    ('q', 'Search reference, bank, IFSC, UTR or institution'), ('category', 'all, active, expiring, matured, renewed, released, pending'),
    ('mode', 'FDR, RTGS or RPGF'), ('status', 'Workflow status'), ('verification_level', 'Recorded verification level'),
    ('maturity_from', 'ISO date'), ('maturity_to', 'ISO date'), ('as_of', 'ISO date; DEBUG-only demo override'))]


class RecordCreate(RecordWrite):
    def get_fields(self):
        fields = super().get_fields()
        for name in ('reference', 'bank', 'amount', 'issue_date', 'maturity_date'):
            fields[name].required = True
        return fields


class RecordUpdate(RecordWrite):
    version = serializers.IntegerField(min_value=1)


class RecordRenew(RecordCreate):
    version = serializers.IntegerField(min_value=1)


class RecordCorrection(RecordUpdate):
    reason = serializers.CharField(max_length=2000)


CORRECTION = RecordCorrection


class RecordVersionSchema(OpenApiSerializerExtension):
    target_class = RecordUpdate
    match_subclasses = True

    def map_serializer(self, auto_schema, direction):
        schema = auto_schema._map_serializer(self.target, direction, bypass_extensions=True)
        if direction == 'request':
            # PATCH is partial in deposit fields, but optimistic locking is mandatory.
            schema['required'] = ['version']
            if isinstance(self.target, RecordCorrection):
                schema['required'].append('reason')
        return schema


class RecordActionSchema(AutoSchema):
    """One runtime view has several URLs with different validated request bodies."""
    def get_request_serializer(self):
        if self.path.endswith('/renew/'):
            return RecordRenew
        if self.path.endswith('/documents/'):
            return UploadInput
        return ActionInput
