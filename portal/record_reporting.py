"""Y5 scope-preserving register, dashboard and intervention queries."""
from datetime import timedelta

from django.db.models import Count, F, Q

from .deadlines import business_today, category_filters, parse_as_of
from .models import Instrument
from .permissions import scoped_instruments


def filters(as_of):
    old = category_filters(as_of)
    return {'all': Q(), 'active': old['accepted'], 'expiring': old['approaching'] | old['today'],
            'matured': old['matured'], 'renewed': Q(superseded_at__isnull=False),
            'released': Q(released_at__isnull=False),
            'pending': Q(status__in=['SUBMITTED', 'CHANGES_REQUESTED'])}


def query_records(user, params):
    records = scoped_instruments(user).select_related('institution', 'obligation')
    as_of = parse_as_of(params.get('as_of'))
    # Date overrides are for the explicitly labelled synthetic demo only.
    from django.conf import settings
    if params.get('as_of') and not settings.DEBUG:
        raise ValueError('Date overrides are available only in local demo mode.')
    category = params.get('category', 'all')
    if category not in filters(as_of):
        raise ValueError('Unknown category.')
    records = records.filter(filters(as_of)[category])
    q = params.get('q', '').strip()
    if len(q) > 200:
        raise ValueError('Search text must be at most 200 characters.')
    if q:
        records = records.filter(Q(reference__icontains=q) | Q(bank__icontains=q) |
            Q(ifsc__icontains=q) | Q(utr__icontains=q) | Q(institution__code__icontains=q) |
            Q(institution__name__icontains=q))
    for field, choices in [('mode', Instrument.Mode.values), ('status', Instrument.Status.values),
                           ('verification_level', Instrument.VerificationLevel.values)]:
        value = params.get(field)
        if value:
            if value not in choices:
                raise ValueError(f'Invalid {field}.')
            records = records.filter(**{field: value})
    for param, lookup in [('maturity_from', 'maturity_date__gte'), ('maturity_to', 'maturity_date__lte')]:
        if params.get(param):
            records = records.filter(**{lookup: parse_as_of(params[param])})
    return records.order_by('-updated_at', '-pk'), as_of


def dashboard(user, params):
    _, as_of = query_records(user, params)
    records = scoped_instruments(user)
    counts = records.aggregate(**{name: Count('pk', filter=condition) for name, condition in filters(as_of).items()})
    unresolved = records.filter(observations__severity='BLOCKING', observations__resolved_at__isnull=True)
    interventions = [
        ('maturity_follow_up', records.filter(category_filters(as_of)['matured']), 'Officer must assess renewal, replacement or release'),
        ('blocking_observation', unresolved, 'Resolve blocking evidence observations'),
        ('ageing_correction', records.filter(status='CHANGES_REQUESTED', updated_at__date__lt=as_of-timedelta(days=15)), 'Institution must respond'),
        ('discrepancy', records.filter(verification_level='DISCREPANCY'), 'Officer must inspect verification evidence'),
    ]
    rows = []
    for code, items, action in interventions:
        for item in items.distinct().order_by('maturity_date', 'pk')[:50]:
            rows.append({'id': item.pk, 'reference': item.reference, 'kind': code, 'next_action': action})
    from obligations.coverage import coverage, scoped_obligations
    coverage_rows = [coverage(item, as_of) for item in scoped_obligations(user).order_by('pk')[:200]]
    shortfalls = [item for item in coverage_rows if item['known'] and item['shortfall_paise']]
    months = records.filter(status='ACCEPTED', superseded_at__isnull=True, released_at__isnull=True,
                            maturity_date__gte=as_of).values_list('maturity_date', flat=True)
    buckets = {}
    for day in months:
        key = day.strftime('%Y-%m')
        buckets[key] = buckets.get(key, 0) + 1
    from notifications.alerts import open_alerts
    return {'as_of': as_of, 'demo_date': bool(params.get('as_of')), 'counts': counts,
            'interventions': rows, 'alerts': open_alerts(user), 'shortfalls': shortfalls, 'coverage': coverage_rows,
            'coverage_available': bool(coverage_rows) and all(item['known'] for item in coverage_rows),
            'maturity_chart': [{'month': key, 'count': count} for key, count in sorted(buckets.items())]}
