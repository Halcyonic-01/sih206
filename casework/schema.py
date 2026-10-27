"""Release-case API documentation; decisions still use existing runtime validators."""
from drf_spectacular.utils import OpenApiParameter
from portal.api.schema_types import TEXT, INTEGER, BOOLEAN, DATE, DATETIME, FILE, JSON, array, nullable, obj, page

EVIDENCE = obj({'id': INTEGER, 'name': TEXT, 'page_count': INTEGER, 'size_bytes': INTEGER,
    'sha256': TEXT, 'uploaded_by': TEXT, 'uploaded_at': DATETIME, 'download_path': TEXT})
CLEARANCE = obj({'unit': TEXT, 'status': TEXT, 'reason': TEXT, 'evidence_ref': TEXT,
    'can_decide': BOOLEAN, 'evidence_state': TEXT, 'evidence': nullable(EVIDENCE),
    'reviewer': nullable(TEXT), 'decided_at': nullable(DATETIME)})
EVIDENCE_LIST = obj({'version': INTEGER, 'results': array(EVIDENCE)})
EVIDENCE_UPLOAD = obj({'version': INTEGER, 'document': FILE})
EVIDENCE_CREATED = obj({'version': INTEGER, 'evidence': EVIDENCE})

CASE = obj({'id': INTEGER, 'institution_id': INTEGER, 'obligation_id': INTEGER, 'instrument_id': INTEGER,
    'version': INTEGER, 'instrument_version': INTEGER, 'status': TEXT, 'path': TEXT, 'mode': TEXT,
    'declarations': JSON, 'template_ref': TEXT, 'application_reason': TEXT, 'decision_reason': TEXT,
    'completion_notes': TEXT, 'documents': array(obj({'id': INTEGER, 'kind': TEXT, 'name': TEXT,
        'page_count': nullable(INTEGER), 'download_path': TEXT})),
    'history': array(obj({'action': TEXT, 'reason': TEXT, 'at': DATETIME})), 'history_has_more': BOOLEAN,
    'monitoring_active': BOOLEAN, 'readiness': nullable(JSON), 'simulation_label': TEXT, 'policy_label': TEXT,
    'notification_status': TEXT, 'ai_summary_enabled': BOOLEAN, 'next_action': TEXT, 'responsible_party': TEXT,
    'clearances': array(CLEARANCE),
    'penalties': array(obj({'id': INTEGER, 'kind': TEXT, 'amount_paise': INTEGER, 'base_paise': INTEGER,
        'rate_bps': INTEGER, 'clause': TEXT, 'status': TEXT, 'reason': TEXT})),
    'penalty_review_complete': BOOLEAN,
    'approval': obj({'required_signatures': INTEGER, 'signatures_given': INTEGER, 'threshold_paise': nullable(INTEGER),
        'second_signature_required': BOOLEAN, 'signature_voided': BOOLEAN, 'signed_by_me': BOOLEAN,
        'basis_matches': nullable(BOOLEAN), 'policy_source': TEXT, 'policy_label': TEXT}),
    'letter': nullable(obj({'serial': TEXT, 'kind': TEXT, 'revoked': BOOLEAN, 'unsigned_demo': BOOLEAN})),
    'actions': obj({name: BOOLEAN for name in ('can_approve', 'can_reject', 'can_ai_summary',
        'can_review_penalties', 'can_issue', 'can_complete', 'can_revoke')})})
CASES = page(CASE)
CREATE = obj({'instrument_id': INTEGER, 'obligation_id': INTEGER, 'instrument_version': INTEGER,
    'path': TEXT, 'declarations': JSON, 'reason': TEXT, 'template_ref': TEXT})
REQUIREMENTS = obj({'questionnaire': JSON, 'paths': array(TEXT), 'path': TEXT, 'mode': TEXT,
    'documents': array(obj({'name': TEXT, 'kind': TEXT, 'present': BOOLEAN, 'parsed': BOOLEAN})),
    'documents_ready': BOOLEAN, 'eligible': BOOLEAN, 'instrument_version': INTEGER,
    'term_end': nullable(DATE), 'term_elapsed': BOOLEAN, 'simulation_label': TEXT, 'policy_label': TEXT})
REQUIREMENT_PARAMS = [OpenApiParameter('instrument', int, required=True),
    OpenApiParameter('obligation', int, required=True), OpenApiParameter('path', str)]
ACTION_PARAMS = [OpenApiParameter('action', str, OpenApiParameter.PATH,
    enum=['approve', 'reject', 'issue', 'revoke', 'penalties', 'complete'])]
ACTION = obj({'version': INTEGER, 'instrument_version': INTEGER, 'reason': TEXT, 'notes': TEXT,
    'refund_reference': TEXT, 'document': FILE, 'kind': TEXT, 'base_paise': INTEGER, 'confirm_id': INTEGER},
    required=['version'])
CLEARANCE_INPUT = obj({'version': INTEGER, 'status': TEXT, 'reason': TEXT, 'evidence_ref': TEXT, 'evidence_id': INTEGER})
QUEUE = page(obj({'case_id': INTEGER, 'version': INTEGER, 'due_date': nullable(DATE), **CLEARANCE['properties']}))
PUBLIC = obj({'serial': TEXT, 'issue_date': DATE, 'institution_name': TEXT, 'kind': TEXT, 'status': TEXT})
