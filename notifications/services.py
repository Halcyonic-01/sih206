"""Transactional outbox. SMTP delivery occurs only in the explicit sender command."""
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from .models import DeliveryAttempt, Notification

TEMPLATES = {'record_submitted': 'Deposit submitted for review', 'record_reviewed': 'Deposit review completed',
    'verification_discrepancy': 'Deposit verification discrepancy', 'maturity_reminder': 'Deposit maturity reminder'}


@transaction.atomic
def notify(*, recipients, template, context, key):
    if not isinstance(key, str) or not key.strip() or len(key) > 200:
        raise ValueError('A notification key of at most 200 characters is required.')
    if template not in TEMPLATES:
        raise ValueError('Unknown notification template.')
    safe = {name: context[name] for name in ('instrument_id', 'reference') if name in context}
    safe['reference'] = str(safe.get('reference', ''))[:100]
    rows = []
    for user in get_user_model().objects.filter(pk__in=recipients, is_active=True):
        for channel in (('IN_APP', 'EMAIL') if settings.NOTIFICATION_EMAIL_ENABLED else ('IN_APP',)):
            row, _ = Notification.objects.get_or_create(recipient=user, key=key, channel=channel,
                defaults={'template': template, 'context': safe, 'next_attempt_at': timezone.now()})
            rows.append(row)
    return rows


def deliver_pending(limit=100):
    """Retry SMTP after 1/2/4/8 minutes, then fail visibly. Inbox enqueue is idempotent.

    SMTP cannot guarantee exactly-once delivery across a process crash after relay acceptance.
    """
    ids = list(Notification.objects.filter(status='PENDING', next_attempt_at__lte=timezone.now())
               .order_by('pk').values_list('pk', flat=True)[:limit])
    delivered = 0
    for pk in ids:
        with transaction.atomic():
            row = Notification.objects.select_for_update().select_related('recipient').get(pk=pk)
            if row.status != 'PENDING' or row.next_attempt_at > timezone.now():
                continue
            row.attempts += 1
            try:
                if not row.recipient.is_active:
                    raise ValueError('RECIPIENT_INACTIVE')
                if row.channel == 'EMAIL':
                    if not settings.NOTIFICATION_EMAIL_ENABLED:
                        raise ValueError('EMAIL_DISABLED')
                    if not row.recipient.email:
                        raise ValueError('NO_RECIPIENT_ADDRESS')
                    title = TEMPLATES[row.template]
                    body = f"{title}. Reference: {row.context.get('reference', '')}. Sign in to the portal to review."
                    if send_mail(title, body, settings.DEFAULT_FROM_EMAIL, [row.recipient.email]) != 1:
                        raise ValueError('EMAIL_NOT_ACCEPTED')
                captured = row.channel == 'EMAIL' and settings.EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend'
                row.status, row.sent_at, row.last_error = ('CAPTURED' if captured else 'SENT'), (None if captured else timezone.now()), ''
                delivered += 1
            except Exception as exc:
                row.last_error = str(exc) if isinstance(exc, ValueError) and str(exc) in (
                    'RECIPIENT_INACTIVE', 'EMAIL_DISABLED', 'NO_RECIPIENT_ADDRESS', 'EMAIL_NOT_ACCEPTED') else 'DELIVERY_FAILED'
                row.status = 'FAILED' if row.attempts >= 5 else 'PENDING'
                row.next_attempt_at = timezone.now() + timedelta(minutes=2**(row.attempts-1))
            row.save(update_fields=['status', 'sent_at', 'last_error', 'attempts', 'next_attempt_at'])
            DeliveryAttempt.objects.create(notification=row, number=row.attempts,
                outcome=row.status if row.status in ('SENT', 'CAPTURED') else 'FAILED', error_code=row.last_error)
    return delivered
