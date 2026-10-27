"""How long things have been waiting, coloured by the escalation matrix (P2-9). Read-only; nothing is stored."""
from notifications.rules import business_date, load_config, working_days_after

from .models import AuditEvent


def band(waited, limit):
    """ok below half the limit, soon from half, overdue once past it (the same limit that triggers the escalation)."""
    if waited > limit:
        return 'overdue'
    return 'soon' if limit and waited * 2 >= limit else 'ok'


def waiting(since, today, limit, holidays):
    days = working_days_after(since, today, holidays)
    return {'working_days': days, 'calendar_days': (today - since).days, 'limit': limit, 'band': band(days, limit),
            'since': since.isoformat()}


def submission_waits(instruments, today):
    """{instrument id: waiting info} for the SUBMITTED ones in `instruments`, using the latest SUBMITTED event."""
    ids = [item.pk for item in instruments if item.status == 'SUBMITTED']
    if not ids:
        return {}
    config = load_config(today)
    limit, holidays = config['sla']['submission_working_days'], config['holidays']
    latest = {}
    for event in AuditEvent.objects.filter(instrument_id__in=ids, action='SUBMITTED').order_by('created_at').only('instrument_id', 'created_at'):
        latest[event.instrument_id] = event.created_at
    return {item.pk: waiting(business_date(latest.get(item.pk, item.updated_at)), today, limit, holidays)
            for item in instruments if item.pk in ids}


def clearance_wait(task, today, config=None):
    config = config or load_config(today)
    return waiting(business_date(task.case.created_at), today, config['sla']['clearance_working_days'][0], config['holidays'])
