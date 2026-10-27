"""Weekly catch-up dispatch using the existing durable, leased email outbox."""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .digest import business_window, DigestInputError, VERSION
from .digest_sources import prepare_digest
from .models import Notification

logger = logging.getLogger(__name__)


def dispatch(*, now=None, dry_run=True, user_id=None):
    now = now or timezone.now()
    result = {'prepared': 0, 'queued': 0, 'existing': 0, 'skipped': 0, 'failed': 0}
    if not dry_run and not getattr(settings, 'WEEKLY_DIGEST_ENABLED', False):
        return {**result, 'disabled': True}
    window = business_window(now)
    if now < window['proposed_send_at']:
        return {**result, 'not_due': True}
    users = get_user_model().objects.filter(is_active=True).order_by('pk')
    if user_id is not None:
        users = users.filter(pk=user_id)
    for user in users.iterator(chunk_size=100):
        try:
            # A queued/sent/suppressed weekly snapshot is immutable. Avoid rebuilding expensive case facts
            # on every five-minute scheduler tick; the sender still rechecks live authorization.
            key = f'{VERSION}:u:{user.pk}:week:{window["week_start"].date().isoformat()}'
            if not dry_run and Notification.objects.filter(idempotency_key=key,
                    channel=Notification.Channel.EMAIL, recipient_key=f'u:{user.pk}').exists():
                result['existing'] += 1
                continue
            with transaction.atomic():
                digest = prepare_digest(user, as_of=now, portal_base_url=settings.PORTAL_BASE_URL)
                if not digest['eligible']:
                    result['skipped'] += 1
                    continue
                result['prepared'] += 1
                if dry_run:
                    continue
                _, created = Notification.objects.get_or_create(
                    idempotency_key=digest['idempotency_key'], channel=Notification.Channel.EMAIL,
                    recipient_key=f'u:{user.pk}', defaults={
                        'recipient': user, 'recipient_email': user.email.strip(), 'template_id': 'weekly_digest',
                        'subject': digest['subject'], 'body': digest['body'],
                        'context': {'scope_fingerprint': digest['scope_fingerprint'], 'week_start': digest['week_start'],
                            'metrics': digest['metrics'], 'template_version': digest['template_version']},
                        'link': digest['portal_link'].removeprefix(settings.PORTAL_BASE_URL.rstrip('/'))})
                result['queued' if created else 'existing'] += 1
        except PermissionDenied:
            result['skipped'] += 1
        except Exception as exc:
            # Isolate recipients; log exception class only, never email, body or private record data.
            result['failed'] += 1
            logger.warning('Weekly digest preparation failed for user %s: %s', user.pk, type(exc).__name__)
    return result
