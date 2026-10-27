"""notify(): the one entry point other features call. Delivery of email is separate (deliver_pending)."""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from .catalog import render
from .models import DeliveryAttempt, Notification

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
# Minutes to wait after failed attempt 1, 2, 3, 4.
BACKOFF_MINUTES = (5, 15, 60, 240)


def _recipient_parts(recipient):
    """-> (user or None, email address, recipient_key)"""
    if isinstance(recipient, str):
        address = recipient.strip().lower()
        return None, address, f'e:{address}'
    if isinstance(recipient, int):
        recipient = get_user_model().objects.get(pk=recipient)
    return recipient, (recipient.email or '').strip(), f'u:{recipient.pk}'


def notify(recipients, template, context, key):
    """Queue an in-app notification (and an email when possible) for each recipient.

    recipients: users, user ids or plain email addresses (addresses get email only).
    template:   a template id from notifications/catalog.py (or any id plus `subject` / `message` in context).
    context:    JSON-serialisable values for the template. `url` (a path such as '/records/42') becomes the
                link; `severity` overrides the template's.
    key:        idempotency key for the *event*, for example 'instrument:42:maturity:T-30:2026-11-01'.
                Calling again with the same key and recipient never creates a second notification.

    Call it inside the transaction of the event that caused it (transactional outbox). Returns the rows that
    were newly created.
    """
    context = dict(context or {})
    if not key:
        raise ValueError('notify() needs an idempotency key.')
    subject, body, severity, email_enabled = render(template, context)
    link = str(context.get('url', ''))[:300]
    created = []
    seen = set()
    for recipient in recipients:
        user, address, recipient_key = _recipient_parts(recipient)
        if recipient_key in seen:
            continue
        seen.add(recipient_key)
        channels = []
        if user is not None:
            channels.append(Notification.Channel.IN_APP)
        if email_enabled and address:
            channels.append(Notification.Channel.EMAIL)
        for channel in channels:
            row = Notification(
                recipient=user, recipient_email=address, recipient_key=recipient_key, channel=channel,
                template_id=template, context=context, subject=subject, body=body, link=link,
                severity=severity, idempotency_key=key,
                status=Notification.Status.SENT if channel == Notification.Channel.IN_APP
                else Notification.Status.PENDING,
                sent_at=timezone.now() if channel == Notification.Channel.IN_APP else None,
            )
            try:
                with transaction.atomic():
                    row.save()
            except IntegrityError:
                continue  # already queued for this event and recipient
            created.append(row)
    emails = [row.pk for row in created if row.channel == Notification.Channel.EMAIL]
    if emails and settings.NOTIFY_SEND_ON_COMMIT:
        # Best effort right after the event commits; the scheduled job retries anything that fails.
        transaction.on_commit(lambda: deliver_pending(ids=emails))
    return created


def _email_text(row):
    if row.template_id == 'weekly_digest':
        return (f'{row.body}\n\nThis optional digest contains aggregate activity counts. '
                'Sign in to inspect supporting records. Manage weekly email in Notifications.\n'
                'Pramaan - Trust Backed by Evidence.')
    link = f'{settings.PORTAL_BASE_URL.rstrip("/")}{row.link}' if row.link else settings.PORTAL_BASE_URL
    return (f'{row.body}\n\nOpen the portal: {link}\n\n'
            'This message contains no account or deposit details. Sign in to the portal to see them.\n'
            'Pramaan — Trust Backed by Evidence, the AICTE Security Deposit Portal (prototype, synthetic data).')


LEASE_MINUTES = 10


def deliver_pending(now=None, limit=100, ids=None):
    """Send due EMAIL rows. Returns (sent, failed). Several runners may overlap: a row is leased before sending."""
    now = now or timezone.now()
    due = Notification.objects.filter(channel=Notification.Channel.EMAIL, status=Notification.Status.PENDING)
    if ids is not None:
        due = due.filter(pk__in=ids)
    due = due.filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
    sent = failed = 0
    for row_id in list(due.order_by('pk').values_list('pk', flat=True)[:limit]):
        claimed = Notification.objects.filter(
            Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now),
            pk=row_id, status=Notification.Status.PENDING,
        ).update(attempts=F('attempts') + 1, next_attempt_at=now + timedelta(minutes=LEASE_MINUTES))
        if not claimed:
            continue  # another runner has it
        row = Notification.objects.get(pk=row_id)
        try:
            if row.template_id == 'weekly_digest':
                from .digest_sources import delivery_allowed
                if not delivery_allowed(row):
                    row.status = Notification.Status.FAILED
                    row.last_error = 'SUPPRESSED: digest disabled or recipient eligibility/scope changed.'
                    row.next_attempt_at = None
                    row.save(update_fields=['status', 'last_error', 'next_attempt_at'])
                    DeliveryAttempt.objects.create(notification=row, ok=False, error=row.last_error)
                    failed += 1
                    continue
            send_mail(row.subject, _email_text(row), settings.DEFAULT_FROM_EMAIL, [row.recipient_email],
                      fail_silently=False)
        except Exception as exc:  # SMTP, DNS, TLS, timeouts
            error = f'{type(exc).__name__}: {exc}'[:300]
            row.last_error = error
            if row.attempts >= MAX_ATTEMPTS:
                row.status = Notification.Status.FAILED
                row.next_attempt_at = None
            else:
                row.next_attempt_at = now + timedelta(minutes=BACKOFF_MINUTES[min(row.attempts, len(BACKOFF_MINUTES)) - 1])
            row.save(update_fields=['last_error', 'status', 'next_attempt_at'])
            DeliveryAttempt.objects.create(notification=row, ok=False, error=error)
            logger.warning('Email delivery failed (attempt %s) for notification %s: %s', row.attempts, row.pk,
                           type(exc).__name__)
            failed += 1
        else:
            row.status = Notification.Status.SENT
            row.sent_at = timezone.now()
            row.last_error = ''
            row.next_attempt_at = None
            row.save(update_fields=['status', 'sent_at', 'last_error', 'next_attempt_at'])
            DeliveryAttempt.objects.create(notification=row, ok=True)
            sent += 1
    return sent, failed
