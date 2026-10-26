"""Advisory extraction contracts, including manual fallback responses."""
from portal.api.schema_types import TEXT, INTEGER, BOOLEAN, JSON, array, nullable, obj

CONSENT = obj({'consent': BOOLEAN, 'synthetic': BOOLEAN})
VERSION = obj({'version': INTEGER})
FIELD = obj({'value': nullable(TEXT), 'page': nullable(INTEGER)})
EXTRACTION = obj({'run_id': INTEGER, 'status': TEXT, 'advisory': BOOLEAN, 'label': TEXT,
    'fields': {'type': 'object', 'additionalProperties': FIELD}, 'findings': array(JSON),
    'pages': array(JSON), 'detail': TEXT, 'code': TEXT},
    required=['status', 'advisory', 'label', 'fields', 'findings'])
SUMMARY = obj({'run_id': INTEGER, 'status': TEXT, 'cached': BOOLEAN, 'advisory': BOOLEAN,
    'label': TEXT, 'detail': TEXT, 'summary': TEXT,
    'risk_flags': array(obj({'field': TEXT, 'severity': TEXT, 'message': TEXT}))},
    required=['run_id', 'status', 'cached', 'advisory', 'label'])
