from django.db import models

from access.models import AppendOnlyError, AppendOnlyQuerySet


class AuditSeal(models.Model):
    """One link of the audit hash chain: hash = HMAC(prev_hash | canonical event). Append-only.

    The chain starts when sealing was switched on; events that existed earlier are sealed in id order and marked
    `backfilled`, which proves they were not changed since, not that they were correct when written.
    """

    event = models.OneToOneField('portal.AuditEvent', on_delete=models.PROTECT, related_name='seal')
    prev_hash = models.CharField(max_length=64, blank=True)
    hash = models.CharField(max_length=64)
    backfilled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ['pk']
        constraints = [
            # Two seals can never claim the same predecessor: a fork is rejected by the database.
            models.UniqueConstraint(fields=['prev_hash'], name='audit_seal_no_fork'),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AppendOnlyError('Audit seals cannot be changed.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyError('Audit seals cannot be deleted.')
