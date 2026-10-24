from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('Verification evidence is append-only.')

    def delete(self):
        raise ValidationError('Verification evidence is append-only.')

    def bulk_update(self, *args, **kwargs):
        raise ValidationError('Verification evidence is append-only.')


class StatementImport(models.Model):
    source = models.CharField(max_length=200)
    sha256 = models.CharField(max_length=64)
    simulated = models.BooleanField(default=True)
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source', 'sha256'], name='verification_batch_unique')]


class StatementLine(models.Model):
    batch = models.ForeignKey(StatementImport, on_delete=models.PROTECT, related_name='lines')
    number = models.PositiveIntegerField()
    utr = models.CharField(max_length=100)
    amount_paise = models.PositiveBigIntegerField()
    value_date = models.DateField()
    result = models.CharField(max_length=30)
    instrument = models.ForeignKey('portal.Instrument', null=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['batch', 'number'], name='verification_line_unique')]


class VerificationEvidence(models.Model):
    instrument = models.ForeignKey('portal.Instrument', on_delete=models.PROTECT, related_name='verification_evidence')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    instrument_version = models.PositiveIntegerField()
    method = models.CharField(max_length=40, choices=[
        ('OFFICER_REVIEW', 'Officer document review'),
        ('BANK_CONFIRMATION', 'Bank email confirmation'),
        ('SIMULATED_BANK', 'SIMULATED bank email confirmation'),
        ('SIMULATED_STATEMENT', 'SIMULATED statement reconciliation')])
    result = models.CharField(max_length=30, choices=[('REVIEWED', 'Reviewed'),
        ('SIMULATED_MATCH', 'SIMULATED match; not bank confirmed'), ('DISCREPANCY', 'Discrepancy'),
        ('CONFIRMED', 'Independently confirmed fields')])
    source = models.CharField(max_length=200)
    fields_observed = models.JSONField(default=dict)
    document = models.ForeignKey('portal.Document', null=True, blank=True, on_delete=models.PROTECT)
    statement_line = models.OneToOneField(StatementLine, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = AppendOnlyQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Verification evidence is append-only.')
        if self.document_id and self.document.instrument_id != self.instrument_id:
            raise ValidationError('Evidence document must belong to this instrument.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Verification evidence is append-only.')


class BankConfirmation(models.Model):
    import uuid
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrument = models.ForeignKey('portal.Instrument', on_delete=models.PROTECT, related_name='bank_requests')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    instrument_version = models.PositiveIntegerField()
    ifsc = models.CharField(max_length=11)
    recipient_email = models.EmailField()
    contact_source = models.CharField(max_length=200)
    simulated = models.BooleanField(default=True)
    status = models.CharField(max_length=12, default='PENDING')
    otp_hash = models.CharField(max_length=200, blank=True)
    otp_attempts = models.PositiveIntegerField(default=0)
    delivery_attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True)
    response = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['instrument'], condition=models.Q(status__in=['PENDING', 'SENT']),
            name='bank_one_open_request')]
