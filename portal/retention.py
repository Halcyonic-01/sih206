"""Retention, archival and legal hold (P3-1).

settled     = released or superseded by a renewal (the date that happened)
archival due = settled + RETENTION_YEARS (default 10)
archive      = freezes the record: the workflow refuses any further change; blocked while a legal hold is on
legal hold   = authority sets or lifts it with a reason; it blocks archiving (and so keeps the record open to correction)
Everything is audited through services.event so it is sealed in the chain.
"""
from datetime import date

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from . import services
from .deadlines import business_today
from .models import Instrument
from .permissions import require_authority


def retention_years():
    return int(getattr(settings, 'RETENTION_YEARS', 10))


def settled_on(instrument):
    moment = instrument.released_at or instrument.superseded_at
    return timezone.localtime(moment).date() if moment else None


def due_on(instrument):
    day = settled_on(instrument)
    if day is None:
        return None
    try:
        return day.replace(year=day.year + retention_years())
    except ValueError:      # 29 February
        return date(day.year + retention_years(), 3, 1)


def state(instrument):
    from audit.models import RecordRetention
    row = RecordRetention.objects.filter(instrument=instrument).first()
    due = due_on(instrument)
    archived = bool(row and row.archived_at)
    hold = bool(row and row.legal_hold)
    return {'settled_on': settled_on(instrument), 'archival_due_on': due,
            'archival_due': bool(due and due <= business_today() and not archived),
            'archived': archived, 'archived_at': row.archived_at if archived else None,
            'legal_hold': hold, 'hold_reason': row.hold_reason if hold else '', 'retention_years': retention_years()}


def is_archived(instrument):
    from audit.models import RecordRetention
    return RecordRetention.objects.filter(instrument_id=instrument.pk, archived_at__isnull=False).exists()


def require_not_archived(instrument):
    if is_archived(instrument):
        raise services.WorkflowError('This record is archived and frozen. A legal hold or a new record is needed to change anything.')


def _reason(text):
    text = (text or '').strip() if isinstance(text, str) else ''
    if not 5 <= len(text) <= 500:
        raise services.WorkflowError('Give a reason of 5 to 500 characters.')
    return text


@transaction.atomic
def set_legal_hold(actor, instrument, reason):
    from audit.models import RecordRetention
    require_authority(actor)
    reason = _reason(reason)
    row, _ = RecordRetention.objects.select_for_update().get_or_create(instrument=instrument)
    if row.legal_hold:
        raise services.WorkflowError('A legal hold is already in place.')
    before = services.snapshot(instrument)
    row.legal_hold, row.hold_reason, row.hold_by, row.hold_at = True, reason, actor, timezone.now()
    row.save()
    services.event(instrument, actor, 'LEGAL_HOLD_SET', before, reason)
    return row


@transaction.atomic
def lift_legal_hold(actor, instrument, reason):
    from audit.models import RecordRetention
    require_authority(actor)
    reason = _reason(reason)
    row = RecordRetention.objects.select_for_update().filter(instrument=instrument, legal_hold=True).first()
    if row is None:
        raise services.WorkflowError('There is no legal hold on this record.')
    before = services.snapshot(instrument)
    row.legal_hold, row.hold_reason, row.hold_by, row.hold_at = False, '', actor, timezone.now()
    row.save()
    services.event(instrument, actor, 'LEGAL_HOLD_LIFTED', before, reason)
    return row


@transaction.atomic
def archive(actor, instrument, reason):
    """Freeze a settled record whose retention period has passed and that is not under legal hold."""
    from audit.models import RecordRetention
    require_authority(actor)
    reason = _reason(reason)
    due = due_on(instrument)
    if due is None:
        raise services.WorkflowError('Only a released or renewed record can be archived.')
    if due > business_today():
        raise services.WorkflowError(f'This record is not archival due until {due.isoformat()}.')
    row, _ = RecordRetention.objects.select_for_update().get_or_create(instrument=instrument)
    if row.archived_at:
        raise services.WorkflowError('This record is already archived.')
    if row.legal_hold:
        raise services.WorkflowError('A legal hold blocks archiving.')
    before = services.snapshot(instrument)
    row.archived_at, row.archived_by = timezone.now(), actor
    row.save()
    services.event(instrument, actor, 'ARCHIVED', before, reason)
    return row


def due_records(user):
    """Settled records past their retention period that are neither archived nor held, within the user's scope."""
    from audit.models import RecordRetention
    from .permissions import scoped_instruments
    settled = scoped_instruments(user).filter(released_at__isnull=False) | scoped_instruments(user).filter(superseded_at__isnull=False)
    skip = RecordRetention.objects.filter(archived_at__isnull=False).values('instrument_id')
    held = RecordRetention.objects.filter(legal_hold=True).values('instrument_id')
    return [item for item in settled.exclude(pk__in=skip).exclude(pk__in=held).select_related('institution').distinct()
            if (due := due_on(item)) is not None and due <= business_today()]
