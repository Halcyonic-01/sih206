"""Validated explicit snapshots: no implicit latest-rule selection or DB writes."""
from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
import json

from .catalogue import LEVELS, draft_payload


class RuleInputError(ValueError):
    pass


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise RuleInputError(f'{name} must be an integer >= {minimum}.')
    return value


def day(value, name):
    if type(value) is not date:
        raise RuleInputError(f'{name} must be a date, not a datetime or string.')
    return value


def add_days(value, days):
    """Bound date arithmetic so callers get the documented input error."""
    day(value, 'date')
    integer(days, 'day offset')
    try:
        return value + timedelta(days=days)
    except OverflowError as exc:
        raise RuleInputError('Computed deadline exceeds the supported date range; human review is required.') from exc


def validate_payload(payload):
    template = draft_payload()
    if not isinstance(payload, dict) or payload.keys() != template.keys():
        raise RuleInputError('Unknown or incomplete policy schema.')
    if type(payload['schema_version']) is not int or payload['schema_version'] != 1:
        raise RuleInputError('Unsupported policy schema version.')
    if payload['label'] != 'DRAFT_DEMO_NOT_APPROVED':
        raise RuleInputError('Only explicitly labelled draft demo rules are supported.')
    amounts = payload['amounts']
    if not isinstance(amounts, dict) or amounts.keys() != template['amounts'].keys():
        raise RuleInputError('The programme catalogue is incomplete or unsupported.')
    for programme, levels in amounts.items():
        if not isinstance(levels, dict) or set(levels) != set(LEVELS):
            raise RuleInputError('Every programme needs all three level entries.')
        for level, amount in levels.items():
            if amount is None:
                if template['amounts'][programme][level] is not None:
                    raise RuleInputError('A supported amount cannot be unknown.')
            else:
                if template['amounts'][programme][level] is None:
                    raise RuleInputError('This programme/level is unsupported in schema v1.')
                integer(amount, 'amount', 1)
    for key in ['leased_multiplier', 'term_years', 'proof_days']:
        integer(payload[key], key, 1)
    rates = payload['penalties_bps']
    if not isinstance(rates, dict) or rates.keys() != template['penalties_bps'].keys():
        raise RuleInputError('Incomplete penalty catalogue.')
    for rate in rates.values():
        if integer(rate, 'basis points') > 10000:
            raise RuleInputError('Penalty rate cannot exceed 100 percent.')
    clauses = payload['clauses']
    if not isinstance(clauses, dict) or clauses.keys() != template['clauses'].keys() or not all(
            isinstance(v, str) and v.strip() for v in clauses.values()):
        raise RuleInputError('Every rule needs a source clause.')
    # Check schema recursively, allowing a new explicit version to configure
    # thresholds without accepting untyped/unrecognised fields.
    def shape(value, sample):
        if isinstance(sample, dict):
            if not isinstance(value, dict) or value.keys() != sample.keys():
                raise RuleInputError('Incomplete nested configuration.')
            for key in sample:
                shape(value[key], sample[key])
        elif isinstance(sample, list):
            if not isinstance(value, list) or not value:
                raise RuleInputError('Configuration lists must be nonempty.')
            for entry in value:
                shape(entry, sample[0])
        elif type(value) is not type(sample) or (isinstance(value, str) and not value.strip()):
            raise RuleInputError('Invalid configuration value type.')
    for key in ['release', 'reminders', 'escalation']:
        shape(payload[key], template[key])
    if payload['release']['paths'] != template['release']['paths']:
        raise RuleInputError('Unsupported release paths.')
    release = payload['release']
    for key in ['common_documents', 'clearance_units']:
        values = release[key]
        if len(values) != len(set(values)) or set(values) != set(template['release'][key]):
            raise RuleInputError(f'Incomplete or unsupported required {key}.')
    for key in ['mode_documents', 'conditional_documents', 'external_noc_if_embezzlement',
                'conversion_requires_no_pending_proceedings']:
        if release[key] != template['release'][key]:
            raise RuleInputError(f'Unsupported release requirement {key}; revise the schema deliberately.')
    for days in payload['reminders'].values():
        if len(days) != len(set(days)) or any(day < 1 for day in days):
            raise RuleInputError('Reminder days must be distinct positive integers.')
    allowed_triggers = {entry['trigger'] for entry in template['escalation']}
    allowed_recipients = {recipient for entry in template['escalation'] for recipient in entry['recipients']}
    identities = set()
    for entry in payload['escalation']:
        if entry['clock'] not in {'CALENDAR', 'WORKING'}:
            raise RuleInputError('Unknown escalation clock.')
        if entry['trigger'] not in allowed_triggers or not set(entry['recipients']) <= allowed_recipients:
            raise RuleInputError('Unknown escalation trigger or recipient symbol.')
        if len(entry['recipients']) != len(set(entry['recipients'])):
            raise RuleInputError('Duplicate escalation recipient.')
        identity = (entry['trigger'], entry['days'], entry['clock'])
        if identity in identities:
            raise RuleInputError('Duplicate escalation boundary.')
        identities.add(identity)
        if (entry['trigger'] == 'MATURITY' and entry['days'] >= 0) or (
                entry['trigger'] != 'MATURITY' and entry['days'] <= 0):
            raise RuleInputError('Escalation offset has the wrong direction.')
    if {entry['trigger'] for entry in payload['escalation']} != allowed_triggers:
        raise RuleInputError('Required escalation trigger is missing.')
    return payload


@dataclass(frozen=True)
class RuleSnapshot:
    code: str
    version: int
    effective_from: date
    effective_to: date | None
    source_document: str
    source_clause: str
    payload_json: str

    def __post_init__(self):
        integer(self.version, 'rule version', 1)
        day(self.effective_from, 'effective_from')
        if self.effective_to is not None:
            day(self.effective_to, 'effective_to')
            if self.effective_to < self.effective_from:
                raise RuleInputError('Invalid rule interval.')
        if not all(isinstance(v, str) and v.strip() for v in [self.code, self.source_document, self.source_clause]):
            raise RuleInputError('Rule identity and source references are required.')
        try:
            validate_payload(json.loads(self.payload_json))
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuleInputError('Invalid policy JSON.') from exc

    @property
    def payload(self):
        return json.loads(self.payload_json)

    @property
    def sha256(self):
        data = [self.code, self.version, self.effective_from.isoformat(),
                self.effective_to.isoformat() if self.effective_to else None,
                self.source_document, self.source_clause, self.payload]
        return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def evidence(self, clause):
        return {'rule_code': self.code, 'rule_version': self.version, 'rule_sha256': self.sha256,
                'source_document': self.source_document, 'source_clause': self.payload['clauses'][clause],
                'policy_label': 'DRAFT_DEMO_NOT_APPROVED'}


def rule_snapshot(ruleset, as_of):
    """Accept a deliberately selected RuleSet or an already frozen snapshot."""
    day(as_of, 'as_of')
    if isinstance(ruleset, RuleSnapshot):
        result = ruleset
    else:
        result = RuleSnapshot(ruleset.code, ruleset.version, ruleset.effective_from,
            ruleset.effective_to, ruleset.source_document, ruleset.source_clause,
            json.dumps(ruleset.payload, sort_keys=True, separators=(',', ':')))
    if as_of < result.effective_from or (result.effective_to and as_of > result.effective_to):
        raise RuleInputError('Rule snapshot is not effective on the explicit evaluation date.')
    return result
