from django.conf import settings
from django.db import models


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    template = models.CharField(max_length=80)
    context = models.JSONField(default=dict)
    key = models.CharField(max_length=200)
    channel = models.CharField(max_length=10, choices=[('IN_APP', 'In-app'), ('EMAIL', 'Email')])
    status = models.CharField(max_length=12, default='PENDING', choices=[
        ('PENDING', 'Pending'), ('SENT', 'Sent'), ('CAPTURED', 'Captured locally'), ('FAILED', 'Failed')])
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=50, blank=True)
    next_attempt_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True)
    read_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['recipient', 'key', 'channel'], name='notification_idempotent')]


class DeliveryAttempt(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.PROTECT, related_name='delivery_attempts')
    number = models.PositiveIntegerField()
    outcome = models.CharField(max_length=20)
    error_code = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
