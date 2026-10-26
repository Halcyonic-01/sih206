from django.conf import settings
from django.db import models


class UnitAssignment(models.Model):
    """Which clearance unit a Clearance-role account works for. Only meaningful with the Clearance role."""

    class Unit(models.TextChoices):
        PGRC = 'PGRC', 'PGRC'
        VIGILANCE = 'VIGILANCE', 'Vigilance'
        GRANTS = 'GRANTS', 'Grants'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='unit_assignment')
    unit = models.CharField(max_length=12, choices=Unit)

    def __str__(self):
        return f'{self.user} -> {self.unit}'


class MfaDevice(models.Model):
    """A staff member's authenticator app (TOTP). Unconfirmed until the first valid code is entered.

    The secret is stored as is, as other TOTP libraries do: protect the database and its backups. `last_step` is the
    last accepted 30-second step (a code cannot be replayed); after five wrong codes in a row the device locks for 15 minutes.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mfa_device')
    secret = models.CharField(max_length=64)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_step = models.BigIntegerField(default=0)
    failures = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'MFA for {self.user} ({"confirmed" if self.confirmed_at else "pending"})'


class AppendOnlyError(Exception):
    pass


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise AppendOnlyError('Access log rows cannot be changed.')

    def delete(self):
        raise AppendOnlyError('Access log rows cannot be deleted.')


class AccessLog(models.Model):
    """Who looked at or took what, and from where. Append-only at the application layer.

    Stage 3 adds database-level protection (PostgreSQL trigger / INSERT-only role) and retention.
    `action` is a free string so each area can add its own without a migration; the constants below are the
    ones the platform writes itself.
    """

    LOGIN = 'LOGIN'
    LOGOUT = 'LOGOUT'
    LOGIN_FAILED = 'LOGIN_FAILED'
    DOCUMENT_DOWNLOAD = 'DOCUMENT_DOWNLOAD'
    EXPORT = 'EXPORT'
    REPORT = 'REPORT'
    NOC_VIEW = 'NOC_VIEW'
    SEARCH = 'SEARCH'
    DOWNLOAD = 'DOWNLOAD'  # fallback written by the middleware for download-like URLs nobody logged explicitly

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                             related_name='access_logs')
    username = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=40, db_index=True)
    object_type = models.CharField(max_length=40, blank=True)
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    detail = models.CharField(max_length=500, blank=True)
    path = models.CharField(max_length=300, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at', '-pk']
        indexes = [models.Index(fields=['object_type', 'object_id'])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AppendOnlyError('Access log rows cannot be changed.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyError('Access log rows cannot be deleted.')

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} {self.username or "anonymous"} {self.action}'
