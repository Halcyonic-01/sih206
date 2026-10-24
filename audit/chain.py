"""Tamper-evident audit trail: every AuditEvent is sealed into a keyed hash chain (K9, F9)."""
import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import timezone

from django.conf import settings
from django.db import IntegrityError, transaction

from portal.models import AuditEvent
from .models import AuditSeal

CHUNK = 500


def _json(value):
    return json.loads(json.dumps(value))  # same values the database will give back


def canonical(event):
    payload = {
        'id': event.pk, 'instrument_id': event.instrument_id, 'actor_id': event.actor_id, 'action': event.action,
        'reason': event.reason, 'before': _json(event.before), 'after': _json(event.after),
        'created_at': event.created_at.astimezone(timezone.utc).isoformat(timespec='microseconds'),
    }
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def compute_hash(prev_hash, event):
    key = settings.AUDIT_CHAIN_KEY.encode()
    return hmac.new(key, f'{prev_hash}|{canonical(event)}'.encode(), hashlib.sha256).hexdigest()


def seal_pending(new_event_id=None):
    """Seal every unsealed event, oldest first. Returns the number sealed.

    Runs inside the caller's transaction, so an event and its seal commit or roll back together. Events that were
    sealed late (they existed before sealing was on) are marked backfilled.
    """
    for attempt in range(3):
        try:
            with transaction.atomic():
                last = AuditSeal.objects.order_by('-pk').first()
                prev = last.hash if last else ''
                sealed = 0
                for event in AuditEvent.objects.filter(seal__isnull=True).order_by('pk'):
                    digest = compute_hash(prev, event)
                    AuditSeal.objects.create(event=event, prev_hash=prev, hash=digest,
                                             backfilled=event.pk != new_event_id)
                    prev, sealed = digest, sealed + 1
                return sealed
        except IntegrityError:
            if attempt == 2:
                raise  # a fork that keeps happening is not something to hide
    return 0


@dataclass
class Verification:
    status: str = 'ok'            # ok | broken | incomplete
    checked: int = 0
    backfilled: int = 0
    head: str = ''
    broken: list = field(default_factory=list)
    unsealed: int = 0

    @property
    def ok(self):
        return self.status == 'ok'

    def as_dict(self):
        return {'status': self.status, 'checked': self.checked, 'backfilled': self.backfilled, 'head': self.head,
                'broken': self.broken, 'unsealed': self.unsealed}


def verify_chain():
    result = Verification()
    prev = ''
    seals = AuditSeal.objects.order_by('pk')
    ids = list(seals.values_list('pk', flat=True))
    for start in range(0, len(ids), CHUNK):
        chunk = list(seals.filter(pk__in=ids[start:start + CHUNK]))
        events = AuditEvent.objects.in_bulk([seal.event_id for seal in chunk])
        for seal in chunk:
            result.checked += 1
            result.backfilled += seal.backfilled
            event = events.get(seal.event_id)
            if seal.prev_hash != prev:
                result.broken.append({'event_id': seal.event_id, 'reason': 'chain_break',
                                      'detail': 'A link is missing, reordered or inserted before this event.'})
            if event is None:
                result.broken.append({'event_id': seal.event_id, 'reason': 'event_missing',
                                      'detail': 'The event this seal covers no longer exists.'})
            elif not hmac.compare_digest(compute_hash(seal.prev_hash, event), seal.hash):
                result.broken.append({'event_id': seal.event_id, 'reason': 'event_modified',
                                      'detail': 'The event no longer matches its seal.'})
            prev = seal.hash
    result.head = prev
    result.unsealed = AuditEvent.objects.filter(seal__isnull=True).count()
    if result.broken:
        result.status = 'broken'
    elif result.unsealed:
        result.status = 'incomplete'
    return result
