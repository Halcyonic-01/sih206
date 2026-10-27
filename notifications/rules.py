"""Daily rules (K6): reminders, overdue renewals, penalty review, proof-due reminders and SLA breaches.

Everything here is idempotent: each notification carries a key built from the record, the rule and the
boundary that was crossed, so running the command twice, or again after a missed day, never duplicates anything.
A rule fires when its boundary has been *crossed* (for example "at least 30 days past maturity"), not only on the
exact day, so a missed run catches up with one notification per rule rather than silently skipping it.

Thresholds come from the active `RuleSet` (code `escalation-matrix`, see docs/scheduled-rules.md) and fall back to
the defaults below, which follow F4 of the implementation plan. The values are a proposal for AICTE to confirm.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Q

from obligations.models import DepositObligation, RuleSet
from .models import AlertAction
from portal.models import AuditEvent, Instrument
from . import recipients as who
from .service import notify

logger = logging.getLogger(__name__)

RULESET_CODES = ('escalation-matrix', 'escalation_matrix')

DEFAULTS = {
    'maturity_reminder_days': [90, 60, 30, 7],
    # From these thresholds on, the dealing officer is told as well as the institution.
    'maturity_officer_days': [30, 7],
    'renewal_overdue_after_days': 1,
    'penalty_review_after_days': 30,
    'proof_reminder_days': [7, 12, 15],
    'proof_penalty_label': 'see APH 2.25(f)',
    'sla': {
        'submission_working_days': 7,
        'correction_days': [15, 30],
        'clearance_working_days': [7, 14],
    },
    'holidays': [],
    # An alert nobody has acknowledged after this many days is escalated one level (P2-3).
    'alert_escalation_days': 7,
}


def _merge(base, override):
    merged = dict(base)
    for key, value in (override or {}).items():
        if key not in base:
            continue
        merged[key] = _merge(base[key], value) if isinstance(base[key], dict) and isinstance(value, dict) else value
    return merged


def load_config(as_of):
    """Defaults overlaid with the newest RuleSet effective on `as_of` (unknown keys are ignored)."""
    rule = (RuleSet.objects.filter(code__in=RULESET_CODES, effective_from__lte=as_of)
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
            .order_by('-effective_from', '-version').first())
    config = _merge(DEFAULTS, rule.payload if rule else None)
    config['_source'] = f'{rule.code} v{rule.version}' if rule else 'built-in defaults'
    return config


def business_date(moment):
    return moment.astimezone(ZoneInfo(settings.TIME_ZONE)).date()


def working_days_after(start, end, holidays=()):
    """Working days (Mon-Fri, excluding holidays) after `start` up to and including `end`."""
    closed = {date.fromisoformat(day) if isinstance(day, str) else day for day in holidays}
    count, day = 0, start
    while day < end:
        day += timedelta(days=1)
        if day.weekday() < 5 and day not in closed:
            count += 1
    return count


@dataclass
class Result:
    created: int = 0
    skipped: int = 0
    lines: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    alert_keys: set = field(default_factory=set)

    def add(self, rule, label, recipients, created):
        self.created += len(created)
        self.skipped += 0 if created else 1
        self.lines.append(f'{rule}: {label} -> {len(recipients)} recipient(s), '
                          f'{"queued " + str(len(created)) + " notification(s)" if created else "already sent"}')


def _current(institution=None):
    records = Instrument.objects.filter(status=Instrument.Status.ACCEPTED, superseded_at__isnull=True,
                                        released_at__isnull=True).select_related('institution')
    return records.filter(institution=institution) if institution else records


def _recipients(*groups):
    seen, ordered = set(), []
    for group in groups:
        for recipient in group:
            marker = recipient if isinstance(recipient, str) else recipient.pk
            if marker not in seen:
                seen.add(marker)
                ordered.append(recipient)
    return ordered


# Rules that ask someone to act. Each keeps one AlertAction per notification key until the condition clears.
ALERT_RULES = {
    'maturity': ('renewal-overdue', 'penalty-review'),
    'proof': ('proof-due',),
    'sla': ('sla-submission', 'sla-correction', 'sla-clearance'),
}


def _dispatch(result, dry_run, rule, label, recipients, template, context, key, target=None, as_of=None):
    if dry_run:
        result.lines.append(f'{rule}: {label} -> {len(recipients)} recipient(s) [dry run: {key}]')
        return
    created = notify(recipients, template, context, key)
    result.add(rule, label, recipients, created)
    if target is not None:
        result.alert_keys.add(key)
        open_alert(rule, key, label, context, target, as_of or date.today())


def open_alert(rule, key, label, context, target, as_of):
    """Create the action for this key, or reopen it if the same condition returned after being resolved."""
    values = {'rule': rule, 'reference': str(context.get('reference') or '')[:200], 'summary': label[:300],
              'url': str(context.get('url') or '')[:300], 'opened_on': as_of,
              'instrument_id': target.get('instrument_id'), 'institution_id': target.get('institution_id')}
    alert, created = AlertAction.objects.get_or_create(key=key, defaults=values)
    if not created and alert.status == AlertAction.Status.RESOLVED:
        alert.status, alert.resolved_at, alert.resolved_reason = AlertAction.Status.OPEN, None, ''
        alert.acknowledged_by = alert.acknowledged_at = None
        alert.note, alert.escalation_level, alert.escalated_at, alert.opened_on = '', 0, None, as_of
        alert.save()
    elif not created and alert.summary != values['summary']:
        AlertAction.objects.filter(pk=alert.pk).update(summary=values['summary'])
    return alert


def resolve_cleared(group, result, institution=None):
    """The group ran to the end: an open action whose key did not fire this time has cleared by itself."""
    stale = AlertAction.objects.filter(rule__in=ALERT_RULES[group]).exclude(status=AlertAction.Status.RESOLVED)
    stale = stale.exclude(key__in=result.alert_keys)
    if institution:
        stale = stale.filter(Q(institution=institution) | Q(instrument__institution=institution))
    from django.utils import timezone
    count = stale.update(status=AlertAction.Status.RESOLVED, resolved_at=timezone.now(),
                         resolved_reason='Condition cleared (renewal, release, proof received or case closed)')
    if count:
        result.lines.append(f'alerts: {count} {group} action(s) resolved because the condition cleared')


def escalate_alerts(as_of, config, result, dry_run):
    """An action nobody acknowledged within `alert_escalation_days` goes one level up (regional head and authority)."""
    limit = timedelta(days=int(config['alert_escalation_days']))
    waiting = AlertAction.objects.filter(status=AlertAction.Status.OPEN, escalation_level=0,
                                         opened_on__lte=as_of - limit).select_related('instrument', 'institution')
    for alert in waiting:
        institution = alert.institution or (alert.instrument.institution if alert.instrument_id else None)
        recipients = _recipients(who.regional_heads(institution) if institution else who.officers(), who.authorities())
        label = f'{alert.reference or alert.rule}: not acknowledged for {(as_of - alert.opened_on).days} days'
        if dry_run:
            result.lines.append(f'alert-escalation: {label} -> {len(recipients)} recipient(s) [dry run: alert:{alert.pk}]')
            continue
        created = notify(recipients, 'alert_escalated',
                         {'reference': alert.reference, 'rule': alert.rule, 'days': (as_of - alert.opened_on).days, 'url': alert.url},
                         f'alert:{alert.pk}:escalated:1')
        from django.utils import timezone
        alert.escalation_level, alert.escalated_at = 1, timezone.now()
        alert.save(update_fields=['escalation_level', 'escalated_at'])
        result.add('alert-escalation', label, recipients, created)


def _ends_after_obligation(instrument):
    """True when the holding matures after the obligation term ends, so no renewal is needed."""
    obligation = getattr(instrument, 'obligation', None)  # field arrives with portal migration 0005 (Y1)
    return bool(obligation and obligation.term_end and instrument.maturity_date >= obligation.term_end)


def maturity_rules(as_of, config, result, dry_run, institution=None):
    reminder_days = sorted(config['maturity_reminder_days'])
    officer_days = set(config['maturity_officer_days'])
    for instrument in _current(institution):
        days = (instrument.maturity_date - as_of).days
        if has_active_release(instrument) or _ends_after_obligation(instrument):
            continue
        ref, url = instrument.reference, f'/records/{instrument.pk}'
        context = {'reference': ref, 'maturity_date': instrument.maturity_date.isoformat(), 'url': url}
        if days > 0:
            crossed = [threshold for threshold in reminder_days if days <= threshold]
            if crossed:
                threshold = min(crossed)
                groups = [who.institution_contacts(instrument.institution)]
                if threshold in officer_days:
                    groups.append(who.officers(instrument.institution))
                _dispatch(result, dry_run, 'maturity-reminder', f'{ref} T-{threshold} ({days} days left)',
                          _recipients(*groups), 'maturity_reminder', {**context, 'days': days},
                          f'instrument:{instrument.pk}:maturity:T-{threshold}:{instrument.maturity_date}')
            continue
        overdue_days = -days
        if overdue_days >= config['renewal_overdue_after_days']:
            _dispatch(result, dry_run, 'renewal-overdue', f'{ref} {overdue_days} day(s) past maturity',
                      _recipients(who.institution_contacts(instrument.institution), who.officers(instrument.institution),
                                  who.regional_heads(instrument.institution), who.authorities()),
                      'renewal_overdue', {**context, 'days': overdue_days},
                      f'instrument:{instrument.pk}:renewal-overdue:{instrument.maturity_date}',
                      target={'instrument_id': instrument.pk}, as_of=as_of)
        if overdue_days >= config['penalty_review_after_days']:
            _dispatch(result, dry_run, 'penalty-review', f'{ref} {overdue_days} day(s) past maturity',
                      _recipients(who.officers(instrument.institution)), 'penalty_review_due', {**context, 'days': overdue_days},
                      f'instrument:{instrument.pk}:penalty-review:{instrument.maturity_date}',
                      target={'instrument_id': instrument.pk}, as_of=as_of)


def has_active_release(instrument):
    return instrument.release_requests.filter(status__in=['PENDING', 'APPROVED']).exists()


def proof_rules(as_of, config, result, dry_run, institution=None):
    thresholds = sorted(config['proof_reminder_days'])
    # UNKNOWN only means the requirement is not settled yet; an intimated deposit still needs its proof.
    open_states = [DepositObligation.Status.UNKNOWN, DepositObligation.Status.DUE, DepositObligation.Status.PARTIALLY_MET]
    obligations = DepositObligation.objects.filter(status__in=open_states, intimation_date__isnull=False,
                                                   intimation_date__lte=as_of).select_related('institution')
    if institution:
        obligations = obligations.filter(institution=institution)
    for obligation in obligations:
        review = obligation.proof_reviews.first()  # the officer's latest receipt review
        if review and review.payment_proof_on and review.affidavit_on:
            continue  # both documents recorded as received: nothing left to remind about
        day = (as_of - obligation.intimation_date).days
        crossed = [threshold for threshold in thresholds if day >= threshold]
        if not crossed:
            continue
        threshold = max(crossed)
        label = f'{obligation.institution.code} day {day} since intimation'
        _dispatch(result, dry_run, 'proof-due', label, _recipients(who.institution_contacts(obligation.institution)),
                  'proof_due_reminder',
                  {'institution': obligation.institution.name, 'day': threshold,
                   'band': config['proof_penalty_label'], 'url': f'/institutions/{obligation.institution_id}'},
                  f'obligation:{obligation.pk}:proof-due:day{threshold}:{obligation.intimation_date}',
                  target={'institution_id': obligation.institution_id}, as_of=as_of)


def _latest_event_date(instrument, action):
    event = AuditEvent.objects.filter(instrument=instrument, action=action).order_by('-created_at').first()
    return business_date(event.created_at if event else instrument.updated_at)


def sla_rules(as_of, config, result, dry_run, institution=None, clearance_provider=None):
    sla, holidays = config['sla'], config['holidays']
    records = Instrument.objects.select_related('institution')
    if institution:
        records = records.filter(institution=institution)

    limit = sla['submission_working_days']
    for instrument in records.filter(status=Instrument.Status.SUBMITTED):
        since = _latest_event_date(instrument, 'SUBMITTED')
        waited = working_days_after(since, as_of, holidays)
        if waited > limit:
            _dispatch(result, dry_run, 'sla-submission', f'{instrument.reference} waiting {waited} working days',
                      _recipients(who.authorities()), 'sla_submission_pending',
                      {'reference': instrument.reference, 'days': waited, 'limit': limit,
                       'url': f'/records/{instrument.pk}'},
                      f'instrument:{instrument.pk}:sla-submission:{since}',
                      target={'instrument_id': instrument.pk}, as_of=as_of)

    first, second = sla['correction_days']
    for instrument in records.filter(status=Instrument.Status.CHANGES_REQUESTED):
        since = _latest_event_date(instrument, 'CHANGES_REQUESTED')
        waited = (as_of - since).days
        for limit, group in ((first, who.institution_contacts(instrument.institution)), (second, who.regional_heads(instrument.institution))):
            if waited >= limit:
                _dispatch(result, dry_run, 'sla-correction', f'{instrument.reference} open {waited} days (>= {limit})',
                          _recipients(group), 'sla_correction_pending',
                          {'reference': instrument.reference, 'days': waited, 'limit': limit,
                           'url': f'/records/{instrument.pk}'},
                          f'instrument:{instrument.pk}:sla-correction:{limit}:{since}',
                          target={'instrument_id': instrument.pk}, as_of=as_of)

    provider = clearance_provider or open_clearance_tasks
    unit_days, head_days = sla['clearance_working_days']
    for task in provider(as_of):
        waited = working_days_after(task['opened_on'], as_of, holidays)
        for limit, group in ((unit_days, who.clearance_users(task['unit'])), (head_days, who.authorities())):
            if waited > limit:
                _dispatch(result, dry_run, 'sla-clearance', f'{task["unit"]} task {task["id"]} open {waited} working days',
                          _recipients(group), 'sla_clearance_pending',
                          {'reference': task['reference'], 'unit': task['unit'], 'days': waited, 'limit': limit,
                           'url': f'/releases/{task["case_id"]}'},
                          f'clearance:{task["id"]}:sla:{limit}:{task["opened_on"]}',
                          target={'instrument_id': task.get('instrument_id')}, as_of=as_of)


def add_working_days(start, days, holidays=()):
    """The date `days` working days (Mon-Fri, excluding holidays) after `start`."""
    closed = {date.fromisoformat(day) if isinstance(day, str) else day for day in holidays}
    day = start
    while days > 0:
        day += timedelta(days=1)
        if day.weekday() < 5 and day not in closed:
            days -= 1
    return day


def open_clearance_tasks(as_of):
    """Open clearance tasks of pending release cases (S5) as dicts {id, unit, opened_on, reference, case_id}."""
    from obligations.models import ClearanceTask
    return [{'id': task.pk, 'unit': task.unit, 'opened_on': business_date(task.case.created_at),
             'reference': task.case.release.instrument.reference, 'case_id': task.case_id,
             'instrument_id': task.case.release.instrument_id}
            for task in ClearanceTask.objects.filter(status='OPEN', case__release__status='PENDING')
            .select_related('case__release__instrument').order_by('pk')]


RULES = ('maturity', 'proof', 'sla', 'alerts')


def run_rules(as_of, *, dry_run=False, institution=None, only=None, clearance_provider=None):
    """Evaluate every rule for `as_of`. One failing rule never stops the others; its error is reported."""
    config = load_config(as_of)
    result = Result()
    result.lines.append(f'Evaluation date {as_of.isoformat()} (business timezone {settings.TIME_ZONE}); '
                        f'thresholds from {config["_source"]}')
    for name in only or RULES:
        try:
            if name == 'maturity':
                maturity_rules(as_of, config, result, dry_run, institution)
            elif name == 'proof':
                proof_rules(as_of, config, result, dry_run, institution)
            elif name == 'sla':
                sla_rules(as_of, config, result, dry_run, institution, clearance_provider)
            elif name == 'alerts':
                escalate_alerts(as_of, config, result, dry_run)
            if name in ALERT_RULES and not dry_run:
                resolve_cleared(name, result, institution)
        except Exception as exc:
            logger.exception('Rule group %s failed', name)
            result.errors.append(f'{name}: {type(exc).__name__}: {exc}')
    return result
