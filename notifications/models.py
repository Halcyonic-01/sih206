from django.conf import settings
from django.db import models


class Notification(models.Model):
    """Transactional outbox: written in the same database transaction as the event that caused it.

    One row per recipient and channel. IN_APP rows are the inbox (delivered the moment they exist);
    EMAIL rows are sent by `deliver_pending` with bounded retries. Subject and body are rendered when the row is
    created, so a later template edit never rewrites history.
    """

    class Channel(models.TextChoices):
        IN_APP = 'IN_APP', 'In-app'
        EMAIL = 'EMAIL', 'Email'
        # SMS (Mobile Seva, DLT templates) is a Stage 3 channel.

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed after retries'

    class Severity(models.TextChoices):
        INFO = 'info', 'Information'
        WARNING = 'warning', 'Warning'
        CRITICAL = 'critical', 'Critical'

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='notifications')
    recipient_email = models.EmailField(blank=True)
    # 'u:<user id>' or 'e:<address>': what makes (key, channel, recipient) unique even for outside addresses.
    recipient_key = models.CharField(max_length=300)
    channel = models.CharField(max_length=10, choices=Channel)
    template_id = models.CharField(max_length=60)
    context = models.JSONField(default=dict)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    link = models.CharField(max_length=300, blank=True)
    severity = models.CharField(max_length=10, choices=Severity, default=Severity.INFO)
    idempotency_key = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=300, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['idempotency_key', 'channel', 'recipient_key'],
                                    name='notification_idempotent'),
            models.CheckConstraint(
                condition=models.Q(recipient__isnull=False) | ~models.Q(recipient_email=''),
                name='notification_has_recipient'),
        ]
        indexes = [
            models.Index(fields=['recipient', 'channel', 'read_at']),
            models.Index(fields=['channel', 'status', 'next_attempt_at']),
        ]

    @property
    def is_read(self):
        return self.read_at is not None

    def __str__(self):
        return f'{self.template_id} -> {self.recipient_key} ({self.channel}, {self.status})'


class DeliveryAttempt(models.Model):
    """Every send attempt, so delivery problems are visible in the audit trail."""

    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='delivery_attempts')
    at = models.DateTimeField(auto_now_add=True)
    ok = models.BooleanField()
    error = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['at', 'pk']


class DigestPreference(models.Model):
    """Only controls optional weekly digests; individual workflow notices remain enabled."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='digest_preference')
    enabled = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(version__gte=1), name='digest_preference_version')]
