"""Read-only maturity facts shared by the UI and due-action command."""
from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Count, Q
from django.utils import timezone

from .models import Instrument

CATEGORIES = {
    'all': 'All visible records',
    'pending': 'Pending officer review',
    'accepted': 'Accepted current records',
    'approaching': 'Approaching maturity',
    'today': 'Matures today',
    'matured': 'Matured',
}


def reminder_days():
    days = settings.REMINDER_DAYS
    if not days or any(type(day) is not int or day < 1 for day in days):
        raise ImproperlyConfigured('REMINDER_DAYS must contain positive integer day thresholds.')
    return tuple(sorted(set(days), reverse=True))


def business_today():
    return timezone.localdate(timezone=ZoneInfo(settings.TIME_ZONE))


def parse_as_of(value):
    if not value:
        return business_today()
    try:
        result = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError('Evaluation date must be a valid date in YYYY-MM-DD format.') from None
    if result.isoformat() != value:
        raise ValueError('Evaluation date must use YYYY-MM-DD format.')
    return result


@dataclass(frozen=True)
class Maturity:
    code: str
    label: str
    days_remaining: int
    reminder_band: int | None
    action: str


def classify_maturity(maturity_date, as_of):
    days = (maturity_date - as_of).days
    if days < 0:
        return Maturity('matured', f'Matured {abs(days)} day(s) ago', days, None,
                        'Review the matured instrument and any required follow-up.')
    if days == 0:
        return Maturity('today', 'Matures today', days, None,
                        'Review the instrument maturing today and any required follow-up.')
    bands = [threshold for threshold in reminder_days() if days <= threshold]
    if bands:
        return Maturity('approaching', f'Matures in {days} day(s)', days, min(bands),
                        'Review upcoming maturity and any required follow-up.')
    return Maturity('future', f'Matures in {days} day(s); outside reminder window', days, None,
                    'No maturity action in the configured reminder window.')


def category_filters(as_of):
    # Clamp to date.max so a valid far-future demo date cannot overflow.
    upper = date.fromordinal(min(date.max.toordinal(), as_of.toordinal() + max(reminder_days())))
    accepted = Q(status=Instrument.Status.ACCEPTED, superseded_at__isnull=True, released_at__isnull=True)
    return {
        'all': Q(),
        'pending': Q(status=Instrument.Status.SUBMITTED),
        'accepted': accepted,
        'approaching': accepted & Q(maturity_date__gt=as_of, maturity_date__lte=upper),
        'today': accepted & Q(maturity_date=as_of),
        'matured': accepted & Q(maturity_date__lt=as_of),
    }


def filter_instruments(records, category, as_of):
    if category not in CATEGORIES:
        raise ValueError('Unknown report category.')
    return records.filter(category_filters(as_of)[category])


def dashboard_counts(records, as_of):
    return records.aggregate(**{
        category: Count('pk', filter=condition)
        for category, condition in category_filters(as_of).items()
    })


def due_actions(records, as_of):
    filters = category_filters(as_of)
    due = records.filter(filters['approaching'] | filters['today'] | filters['matured'])
    return [{'instrument': instrument, 'maturity': classify_maturity(instrument.maturity_date, as_of)}
            for instrument in due.select_related('institution').order_by('maturity_date', 'institution__code', 'reference', 'pk')]
