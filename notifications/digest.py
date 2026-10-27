"""Pure synthetic weekly digest preparation. No ORM, email, scheduler or writes.

The future adapter must authenticate recipients and scope its queries first.
Declared scope here is an input consistency boundary, not authorization.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

IST = ZoneInfo('Asia/Kolkata')
VERSION = 'weekly-digest-v1'
ROLES = {'institution', 'officer', 'authority', 'clearance', 'auditor'}
UNITS = {'PGRC', 'VIGILANCE', 'GRANTS'}
SOURCES = {
    'institution': ('deposits', 'observations'),
    'officer': ('submissions', 'discrepancies', 'reviews'),
    'authority': ('releases', 'escalations'),
    'clearance': ('clearances',),
    'auditor': ('audit_alerts',),
}
SCHEMAS = {
    'deposits': {'maturity_date': 'date', 'status': 'instrument_status', 'released': 'bool', 'superseded': 'bool'},
    'observations': {'resolved': 'bool', 'requires_institution_action': 'bool'},
    'submissions': {'status': 'instrument_status'},
    'discrepancies': {'unresolved': 'bool', 'simulated': 'bool'},
    'reviews': {'submitted_at': 'instant', 'accepted_at': 'instant', 'history_complete': 'bool'},
    'releases': {'status': 'release_status', 'ready_for_authority': 'bool'},
    'escalations': {'unit': 'unit', 'raised_at': 'instant', 'unresolved': 'bool'},
    'clearances': {'unit': 'unit', 'status': 'clearance_status'},
    'audit_alerts': {'unresolved': 'bool'},
}
VALUES = {'instrument_status': {'DRAFT', 'SUBMITTED', 'CHANGES_REQUESTED', 'ACCEPTED'},
          'release_status': {'PENDING', 'APPROVED', 'REJECTED', 'COMPLETED'},
          'clearance_status': {'OPEN', 'CLEARED', 'OBJECTION', 'HOLD'}, 'unit': UNITS}
LINKS = {'institution': '/records', 'officer': '/records', 'authority': '/releases',
         'clearance': '/clearance-tasks', 'auditor': '/audit'}


class DigestInputError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise DigestInputError(message)


def positive_id(value):
    require(type(value) is int and value > 0, 'Use positive integer identities.')


def instant(value):
    if type(value) is str:
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise DigestInputError('Use an aware ISO timestamp.') from exc
    require(type(value) is datetime and value.utcoffset() is not None, 'Use an aware timestamp.')
    try:
        return value.astimezone(IST)
    except (ValueError, OverflowError) as exc:
        raise DigestInputError('Timestamp cannot be represented in the business timezone.') from exc


def day(value):
    if type(value) is str:
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise DigestInputError('Use a calendar date.') from exc
        require(parsed.isoformat() == value, 'Use YYYY-MM-DD dates.')
        value = parsed
    require(type(value) is date, 'Use a calendar date, not a timestamp.')
    return value


def business_window(as_of):
    current = instant(as_of)
    try:
        monday = current.date() - timedelta(days=current.weekday())
        start = datetime.combine(monday, time.min, IST)
        previous = start - timedelta(days=7)
        due = datetime.combine(monday, time(9), IST)
    except (ValueError, OverflowError) as exc:
        raise DigestInputError('Business week is outside the supported date range.') from exc
    return {'as_of': current, 'week_start': start, 'previous_start': previous,
            'previous_end': start, 'proposed_send_at': due}


def portal_origin(value):
    require(type(value) is str and 0 < len(value) <= 250 and not any(c.isspace() for c in value)
            and '\\' not in value, 'Use a trusted portal origin.')
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
        require(host and not parsed.username and not parsed.password and parsed.path in {'', '/'}
                and not parsed.query and not parsed.fragment, 'Use an origin without credentials, path or query.')
        require(parsed.scheme == 'https' or parsed.scheme == 'http' and host in {'127.0.0.1', 'localhost', '::1'},
                'Use HTTPS except for an explicit loopback demo.')
        require(port is None or 1 <= port <= 65535, 'Invalid portal port.')
        require(not any(c in value for c in '<>"\''), 'Invalid portal origin.')
    except ValueError as exc:
        raise DigestInputError('Invalid portal origin.') from exc
    return value.rstrip('/')


def validate_rows(name, rows, scope, current, unit):
    if rows is None:
        return None
    require(type(rows) in {list, tuple} and len(rows) <= 5000, 'Supply bounded concrete source rows.')
    cleaned, seen = [], set()
    for original in rows:
        require(type(original) is dict and set(original) == {'id', 'institution_id'} | set(SCHEMAS[name]),
                'Unexpected or missing source fields.')
        row = dict(original)
        positive_id(row['id']); positive_id(row['institution_id'])
        require(row['id'] not in seen, 'Duplicate source identity.')
        seen.add(row['id'])
        require(row['institution_id'] in scope, 'Source row is outside the declared recipient scope.')
        for field, kind in SCHEMAS[name].items():
            if kind == 'bool':
                require(type(row[field]) is bool, 'Use explicit boolean facts.')
            elif kind == 'date':
                row[field] = day(row[field])
            elif kind == 'instant':
                row[field] = instant(row[field])
                require(row[field] <= current, 'Source events cannot be in the future.')
            else:
                require(type(row[field]) is str and row[field] in VALUES[kind], 'Unsupported source status.')
        if name == 'reviews':
            require(row['submitted_at'] <= row['accepted_at'], 'Review duration cannot be negative.')
        if name == 'clearances':
            require(row['unit'] == unit, 'Clearance facts belong to another unit.')
        cleaned.append(row)
    return cleaned


def _metric(code, label, rows, predicate):
    return {'code': code, 'label': label, 'value': None if rows is None else sum(bool(predicate(row)) for row in rows),
            'unit': 'count', 'available': rows is not None}


def build_digest(recipient, facts, *, as_of, portal_base_url, recorded=False):
    """Return rendered synthetic content, never send it or claim it was queued.

    `facts` are explicit snapshots, not caller-authorized ORM rows. Missing sources
    are unavailable. Zero is produced only from a known, complete supplied source.
    The deterministic key needs the existing outbox uniqueness constraint to have
    any delivery/idempotency effect. Preview works any day for retry/catch-up design.
    """
    require(type(recipient) is dict, 'Supply a recipient snapshot.')
    positive_id(recipient.get('id'))
    for field in ['active', 'email_available', 'digest_enabled']:
        require(type(recipient.get(field)) is bool, 'Supply explicit recipient eligibility facts.')
    roles = recipient.get('roles')
    require(type(roles) in {list, tuple} and all(type(role) is str for role in roles), 'Supply role names.')
    require(len(set(roles)) == len(roles), 'Duplicate role name.')
    role = roles[0] if len(roles) == 1 and roles[0] in ROLES else None
    reason = ('INACTIVE' if not recipient['active'] else 'NO_VALID_ROLE' if not roles or role is None and len(roles) == 1
              else 'AMBIGUOUS_ROLE' if role is None else 'OPTED_OUT' if not recipient['digest_enabled']
              else 'NO_EMAIL' if not recipient['email_available'] else None)
    if reason:
        return {'eligible': False, 'reason': reason, 'recipient_id': recipient['id']}
    scope_ids = recipient.get('scope_institution_ids')
    require(type(scope_ids) in {list, tuple}, 'Supply declared institution scope.')
    for identity in scope_ids:
        positive_id(identity)
    require(len(set(scope_ids)) == len(scope_ids), 'Duplicate scope identity.')
    require(role != 'institution' or len(scope_ids) == 1, 'Institution digest needs exactly one institution.')
    unit = recipient.get('unit')
    require(role != 'clearance' or type(unit) is str and unit in UNITS, 'A clearance unit is required.')
    require(type(facts) is dict and facts.get('simulation_label') == ('RECORDED' if recorded else 'SIMULATED')
            and set(facts) <= {'simulation_label', *SOURCES[role]}, 'Only explicitly synthetic, role-minimal facts are supported.')
    window = business_window(as_of)
    current = window['as_of']; today = current.date()
    source = {name: validate_rows(name, facts.get(name), set(scope_ids), current, unit) for name in SOURCES[role]}
    metrics = []
    if role == 'institution':
        metrics.append(_metric('expiring_this_month', 'Deposits expiring in the rest of this month', source['deposits'],
            lambda row: row['status'] == 'ACCEPTED' and not row['released'] and not row['superseded']
            and today <= row['maturity_date'] and row['maturity_date'].year == today.year and row['maturity_date'].month == today.month))
        metrics.append(_metric('observations_needing_action', 'Observations needing your attention', source['observations'],
            lambda row: not row['resolved'] and row['requires_institution_action']))
    elif role == 'officer':
        metrics.append(_metric('pending_submissions', 'Submissions pending review', source['submissions'],
                               lambda row: row['status'] == 'SUBMITTED'))
        metrics.append(_metric('unresolved_discrepancies', 'Unresolved reconciliation mismatches', source['discrepancies'],
                               lambda row: row['unresolved']))
        cohort = None if source['reviews'] is None else [row for row in source['reviews']
            if window['previous_start'] <= row['accepted_at'] < window['previous_end']]
        complete = cohort is not None and bool(cohort) and all(row['history_complete'] for row in cohort)
        durations = [] if not complete else [row['accepted_at'] - row['submitted_at'] for row in cohort]
        seconds = [Decimal(value.days * 86400 + value.seconds) + Decimal(value.microseconds)/Decimal(1000000)
                   for value in durations]
        average = None if not seconds else str((sum(seconds)
            / Decimal(len(durations)) / Decimal(86400)).quantize(Decimal('.1'), rounding=ROUND_HALF_UP))
        metrics.append({'code': 'average_review_days', 'label': 'Average submission-to-acceptance time last week',
            'value': average, 'unit': 'days', 'available': complete, 'sample_count': None if cohort is None else len(cohort),
            'reason': None if complete else 'NO_COMPLETE_COHORT'})
    elif role == 'authority':
        metrics.append(_metric('awaiting_authority', 'Release cases awaiting your decision', source['releases'],
                               lambda row: row['status'] == 'PENDING' and row['ready_for_authority']))
        metrics.append(_metric('pgrc_escalations', 'Recorded unresolved PGRC escalations', source['escalations'],
                               lambda row: row['unit'] == 'PGRC' and row['unresolved']))
    elif role == 'clearance':
        metrics.append(_metric('open_clearance_tasks', 'Open tasks for your clearance unit', source['clearances'],
                               lambda row: row['status'] == 'OPEN'))
    else:
        metrics.append(_metric('audit_alerts', 'Recorded unresolved audit alerts', source['audit_alerts'], lambda row: row['unresolved']))
    origin = portal_origin(portal_base_url)
    link = origin + LINKS[role]
    week = window['week_start'].date().isoformat()
    subject = f'Pramaan weekly digest - {role.title()} - {week}'
    lines = [f"{metric['label']}: {metric['value'] if metric['available'] else 'unavailable'}"
             + (' days' if metric['unit'] == 'days' and metric['available'] else '') for metric in metrics]
    disclaimer = ('Recorded portal activity. ' if recorded else 'SIMULATED preview. ') + 'Counts describe recorded work, not bank authenticity or regulatory compliance.'
    body = '\n'.join([disclaimer, f'Business week beginning {week} (Asia/Kolkata).', *lines,
                      f'Open the portal and sign in: {link}'])
    html = '<p>' + escape(disclaimer) + '</p><ul>' + ''.join('<li>' + escape(line) + '</li>' for line in lines)
    html += '</ul><p><a href="' + escape(link, quote=True) + '">Open the portal and sign in</a></p>'
    return {'eligible': True, 'recipient_id': recipient['id'], 'role': role, 'simulation_label': 'RECORDED' if recorded else 'SIMULATED',
        'template_version': VERSION, 'idempotency_key': f'{VERSION}:u:{recipient["id"]}:week:{week}',
        'week_start': window['week_start'].isoformat(), 'previous_week_start': window['previous_start'].isoformat(),
        'previous_week_end': window['previous_end'].isoformat(), 'proposed_send_at': window['proposed_send_at'].isoformat(),
        'metrics': metrics, 'subject': subject, 'body': body, 'html': html, 'portal_link': link,
        'delivery_state': 'PREVIEW_ONLY'}
