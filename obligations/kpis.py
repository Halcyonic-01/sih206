"""Pure SIMULATED KPI arithmetic over explicit scoped value snapshots only."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo('Asia/Kolkata')
ACTIONS = {'SUBMITTED', 'CHANGES_REQUESTED', 'ACCEPTED',
           'DECLARED', 'INDEPENDENTLY_CONFIRMED', 'DISCREPANCY'}


class KpiInputError(ValueError):
    pass


@dataclass(frozen=True)
class KpiEvent:
    id: int
    sequence: int
    action: str
    at: datetime


@dataclass(frozen=True)
class ProcessSnapshot:
    instrument_id: int
    institution_id: int
    history_complete: bool
    events: tuple[KpiEvent, ...]


@dataclass(frozen=True)
class AcceptedSuccessor:
    instrument_id: int
    institution_id: int
    accepted_at: datetime


@dataclass(frozen=True)
class RenewalSnapshot:
    instrument_id: int
    institution_id: int
    maturity_date: date
    eligible: bool | None
    history_complete: bool
    successor: AcceptedSuccessor | None = None


def _require(condition, message):
    if not condition:
        raise KpiInputError(message)


def _id(value):
    _require(type(value) is int and value > 0, 'IDs and sequences must be positive integers.')


def _instant(value):
    _require(type(value) is datetime and value.utcoffset() is not None, 'Use aware datetime instants.')
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise KpiInputError('Timestamp is outside the supported UTC range.') from exc


def _decimal(numerator, denominator, places):
    if denominator == 0:
        return None
    scaled = (2 * numerator * 10**places + denominator) // (2 * denominator)
    return f'{scaled // 10**places}.{scaled % 10**places:0{places}d}'


def _share(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'percentage_bps': None if denominator == 0 else (2 * numerator * 10000 + denominator) // (2 * denominator)}


def _duration(first, last):
    delta = last - first
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def _distribution(samples):
    values = sorted(samples)
    count = len(values)
    return {'sample_count': count,
            'median_seconds': None if not count else _decimal(
                values[(count - 1) // 2] + values[count // 2], 2000000, 6),
            'p90_seconds': None if not count else _decimal(values[(9 * count + 9) // 10 - 1], 1000000, 6)}


def calculate_kpis(*, processes, renewals, scope_institution_ids,
                   window_start, window_end, as_of, simulation_label):
    """No queries/writes/adapters. Snapshot completeness and scope are caller facts.

    Results describe synthetic cohorts, not measured real-world improvement.
    """
    _require(simulation_label == 'SIMULATED', 'Only explicitly SIMULATED snapshots are supported.')
    _require(type(processes) is tuple and type(renewals) is tuple and
             type(scope_institution_ids) is tuple, 'Supply explicit tuples, never lazy data sources.')
    for identity in scope_institution_ids:
        _id(identity)
    _require(len(set(scope_institution_ids)) == len(scope_institution_ids), 'Duplicate scope identity.')
    scope = set(scope_institution_ids)
    start, end, cutoff = map(_instant, (window_start, window_end, as_of))
    _require(start <= end <= cutoff, 'Window must be ordered and end no later than as_of.')
    try:
        first_day, last_day, today = (value.astimezone(IST).date() for value in (start, end, cutoff))
    except (OverflowError, ValueError) as exc:
        raise KpiInputError('Timestamp is outside the supported business-date range.') from exc
    seen_records, seen_events = {}, set()
    durations, confirmation_durations, cycles = [], [], []
    confirmed = known_verification = unknown_verification = incomplete = future_events = open_submissions = 0
    for record in processes:
        _require(type(record) is ProcessSnapshot, 'Process snapshots must be typed values.')
        _id(record.instrument_id)
        _id(record.institution_id)
        _require(record.instrument_id not in seen_records, 'Duplicate process snapshot.')
        _require(record.institution_id in scope, 'Process snapshot outside supplied scope.')
        seen_records[record.instrument_id] = record.institution_id
        _require(type(record.history_complete) is bool and type(record.events) is tuple,
                 'Supply explicit completeness and an event tuple.')
        ordered, sequences = [], set()
        for event in record.events:
            _require(type(event) is KpiEvent, 'Events must be typed values.')
            _id(event.id)
            _id(event.sequence)
            _require(event.id not in seen_events and event.sequence not in sequences, 'Duplicate event or sequence.')
            _require(isinstance(event.action, str) and event.action in ACTIONS, 'Unknown KPI event action.')
            seen_events.add(event.id)
            sequences.add(event.sequence)
            ordered.append((event.sequence, _instant(event.at), event.action))
        ordered.sort()
        _require(all(a[1] <= b[1] for a, b in zip(ordered, ordered[1:])), 'Sequence reverses timestamp order.')
        future_events += sum(at > cutoff for _, at, _ in ordered)
        if not record.history_complete:
            incomplete += 1
            continue
        submitted = accepted = declared = first_confirmed = None
        review_state, verification_state, corrections = None, None, 0
        for _, at, action in ordered:
            if at > cutoff:
                continue
            if action == 'SUBMITTED':
                _require(review_state in {None, 'CHANGES_REQUESTED'}, 'Invalid submission transition.')
                submitted = at if submitted is None else submitted
                review_state = action
            elif action in {'CHANGES_REQUESTED', 'ACCEPTED'}:
                _require(review_state == 'SUBMITTED', 'Review action lacks a pending submission.')
                review_state = action
                if action == 'ACCEPTED':
                    accepted = at
                else:
                    corrections += 1
            elif action == 'DECLARED':
                _require(verification_state is None, 'Repeated verification declaration.')
                declared, verification_state = at, action
            else:
                _require(verification_state in {'DECLARED', 'INDEPENDENTLY_CONFIRMED', 'DISCREPANCY'}
                         and verification_state != action, 'Invalid verification transition.')
                verification_state = action
                if action == 'INDEPENDENTLY_CONFIRMED' and first_confirmed is None:
                    first_confirmed = at
        if accepted is not None and start <= accepted <= end:
            durations.append(_duration(submitted, accepted))
            cycles.append(corrections)
            if verification_state is None:
                unknown_verification += 1
            else:
                known_verification += 1
                confirmed += int(verification_state == 'INDEPENDENTLY_CONFIRMED')
        elif accepted is None and submitted is not None and start <= submitted <= end:
            open_submissions += 1
        if first_confirmed is not None and start <= first_confirmed <= end:
            confirmation_durations.append(_duration(declared, first_confirmed))
    excluded = {key: 0 for key in ['outside_window', 'not_matured', 'eligibility_unknown',
                                  'not_required', 'incomplete_history']}
    renewal_ids, successor_ids = set(), set()
    identities, lineage = seen_records.copy(), {}
    renewal_count = on_time = 0
    for record in renewals:
        _require(type(record) is RenewalSnapshot, 'Renewal snapshots must be typed values.')
        _id(record.instrument_id)
        _id(record.institution_id)
        _require(record.instrument_id not in renewal_ids, 'Duplicate renewal snapshot.')
        renewal_ids.add(record.instrument_id)
        _require(record.institution_id in scope, 'Renewal snapshot outside supplied scope.')
        _require(identities.get(record.instrument_id, record.institution_id) == record.institution_id,
                 'Inconsistent instrument institution across snapshots.')
        identities[record.instrument_id] = record.institution_id
        _require(type(record.maturity_date) is date and type(record.history_complete) is bool and
                 (record.eligible is None or type(record.eligible) is bool), 'Invalid renewal context types.')
        accepted_at = None
        if record.successor is not None:
            successor = record.successor
            _require(type(successor) is AcceptedSuccessor, 'Successor must be an explicit accepted snapshot.')
            _id(successor.instrument_id)
            _id(successor.institution_id)
            _require(successor.institution_id == record.institution_id, 'Successor outside predecessor institution.')
            _require(successor.instrument_id != record.instrument_id and successor.instrument_id not in successor_ids,
                     'Self-link or successor reused across predecessors.')
            _require(identities.get(successor.instrument_id, successor.institution_id) == successor.institution_id,
                     'Inconsistent successor institution.')
            identities[successor.instrument_id] = successor.institution_id
            lineage[record.instrument_id] = successor.instrument_id
            successor_ids.add(successor.instrument_id)
            accepted_at = _instant(successor.accepted_at)
        reason = ('outside_window' if not first_day <= record.maturity_date <= last_day else
                  'not_matured' if record.maturity_date >= today else
                  'eligibility_unknown' if record.eligible is None else
                  'not_required' if not record.eligible else
                  'incomplete_history' if not record.history_complete else None)
        if reason:
            excluded[reason] += 1
            continue
        renewal_count += 1
        if accepted_at is not None and accepted_at <= cutoff:
            try:
                on_time += int(accepted_at.astimezone(IST).date() <= record.maturity_date)
            except (OverflowError, ValueError) as exc:
                raise KpiInputError('Successor acceptance is outside the business-date range.') from exc
    checked = set()
    for identity in lineage:
        path = set()
        while identity in lineage and identity not in checked:
            _require(identity not in path, 'Cyclic renewal lineage.')
            path.add(identity)
            identity = lineage[identity]
        checked.update(path)
    confirmed_share = {**_share(confirmed, len(cycles)), 'unknown_count': unknown_verification,
                       'known_subset': _share(confirmed, known_verification)}
    if unknown_verification:
        confirmed_share['percentage_bps'] = None
    renewal_share = {**_share(on_time, renewal_count), 'excluded': excluded,
                     'known_subset': _share(on_time, renewal_count)}
    if excluded['eligibility_unknown'] or excluded['incomplete_history']:
        renewal_share['percentage_bps'] = None
    return {'format': 's4-kpi-snapshots-v1', 'simulation_label': 'SIMULATED',
            'window_start': start.isoformat(), 'window_end': end.isoformat(), 'as_of': cutoff.isoformat(),
            'submission_to_acceptance': _distribution(durations),
            'declaration_to_confirmation': _distribution(confirmation_durations),
            'correction_cycles': {'sample_count': len(cycles), 'total': sum(cycles),
                                  'mean_per_accepted_record': _decimal(sum(cycles), len(cycles), 2)},
            'confirmed_share': confirmed_share,
            'renewed_on_time': renewal_share,
            'data_quality': {'process_snapshots': len(processes), 'renewal_snapshots': len(renewals),
                             'incomplete_process_histories': incomplete, 'ignored_future_events': future_events,
                             'open_submissions': open_submissions}}
