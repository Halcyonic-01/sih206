"""Evidence, synthetic statement and bank-request wire contracts."""
from portal.api.schema_types import TEXT, INTEGER, BOOLEAN, DATE, DATETIME, FILE, JSON, array, nullable, obj

EVIDENCE = obj({'level': TEXT, 'notice': TEXT, 'checks': array(JSON),
    'evidence': array(obj({'id': INTEGER, 'method': TEXT, 'result': TEXT, 'source': TEXT,
        'instrument_version': INTEGER, 'fields_observed': JSON, 'document_id': nullable(INTEGER), 'created_at': DATETIME}))})
IMPORT = obj({'id': INTEGER, 'source': TEXT, 'simulated': BOOLEAN, 'created_at': DATETIME})
LINE = obj({'number': INTEGER, 'utr': TEXT, 'amount_paise': INTEGER, 'value_date': DATE,
    'result': TEXT, 'instrument_id': nullable(INTEGER), 'version': nullable(INTEGER)},
    required=['number', 'utr', 'amount_paise', 'value_date', 'result', 'instrument_id'])
STATEMENT_INPUT = obj({'document': FILE, 'source': TEXT,
    'commit': {'type': 'string', 'enum': ['true', 'false'], 'description': 'Only literal true commits; otherwise preview.'},
    'versions': {'type': 'string', 'description': 'JSON object mapping matched instrument IDs to preview versions.'}}, required=['document'])
STATEMENT_RESULT = {'oneOf': [obj({'simulated': BOOLEAN, 'rows': array(LINE), 'format': TEXT,
    'rejected': array(obj({'where': TEXT, 'reason': TEXT})), 'ignored': array(obj({'where': TEXT, 'reason': TEXT})),
    'versions': {'type': 'object', 'additionalProperties': INTEGER}}),
    obj({'id': INTEGER, 'existing': BOOLEAN, 'simulated': BOOLEAN, 'rows': array(LINE)})]}
BANK_REQUEST = obj({'id': {'type': 'string', 'format': 'uuid'}, 'instrument_version': INTEGER,
    'simulated': BOOLEAN, 'status': TEXT, 'created_at': DATETIME, 'expires_at': DATETIME, 'last_error': TEXT})
BANK_CREATED = obj({'id': {'type': 'string', 'format': 'uuid'}, 'status': TEXT, 'simulated': BOOLEAN, 'detail': TEXT})
