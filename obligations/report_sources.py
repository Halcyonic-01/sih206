"""Read-only P5 adapters; simulated matches never establish bank confirmation."""
from django.core.exceptions import PermissionDenied, ValidationError
from portal.permissions import role, scoped_instruments

MAX_RECORDS = 5000


def records_for(actor):
    if role(actor) not in {'institution', 'officer', 'authority'}:
        raise PermissionDenied('Institution, officer or authority access is required.')
    records = list(scoped_instruments(actor).select_related('institution').prefetch_related(
        'documents', 'observations', 'audit_events', 'verification_evidence').order_by('pk')[:MAX_RECORDS + 1])
    if len(records) > MAX_RECORDS:
        raise ValidationError('This demo report supports at most 5000 visible records. No truncated export was produced.')
    return records


def independent(evidence):
    return evidence.method == 'BANK_CONFIRMATION' and evidence.result == 'CONFIRMED'


def verified_current(item):
    return item.verification_level == 'CONFIRMED' and any(
        independent(e) and e.instrument_version == item.version for e in item.verification_evidence.all())


def latest_action(item, action, when):
    from notifications.rules import business_date
    dates = [business_date(e.created_at) for e in item.audit_events.all()
             if e.action == action and business_date(e.created_at) <= when]
    return max(dates) if dates else None


def sla_context(when):
    from notifications.rules import load_config
    from .services import DependencyUnavailable
    config = load_config(when)
    try:
        submission = config['sla']['submission_working_days']
        corrections = config['sla']['correction_days']
        if type(submission) is not int or submission < 0 or not corrections or any(
                type(value) is not int or value < 0 for value in corrections):
            raise ValueError
        from datetime import date
        holidays = tuple(date.fromisoformat(day) for day in config['holidays'])
    except (KeyError, TypeError, ValueError):
        raise DependencyUnavailable('SLA_CONFIGURATION_UNAVAILABLE') from None
    return submission, min(corrections), holidays, config['_source']
