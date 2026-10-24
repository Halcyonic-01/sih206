"""Owned release storage, registered by the existing obligations app.

No portal migration is allocated. A one-to-one legacy request preserves existing
renewal exclusion, monitoring, audit and completion services. See implementation
notes for the proposed storage choice requiring team review before integration.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q


class ReleaseCase(models.Model):
    release = models.OneToOneField('portal.ReleaseRequest', on_delete=models.PROTECT, related_name='casework')
    institution = models.ForeignKey('portal.Institution', on_delete=models.PROTECT)
    obligation = models.ForeignKey('obligations.DepositObligation', on_delete=models.PROTECT)
    rule_version = models.ForeignKey('obligations.RuleSet', on_delete=models.PROTECT)
    rule_sha256 = models.CharField(max_length=64)
    path = models.CharField(max_length=40)
    mode = models.CharField(max_length=8)
    declarations = models.JSONField(default=dict)
    template_ref = models.CharField(max_length=200, default='')
    version = models.PositiveIntegerField(default=1)
    penalty_review_complete = models.BooleanField(default=False)
    completion_reference = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(version__gte=1), name='case_version_positive'),
            models.CheckConstraint(condition=Q(mode__in=['FDR','RTGS','RPGF']), name='case_supported_mode'),
            models.CheckConstraint(condition=Q(path__in=['TERM_COMPLETE','PROGRESSIVE_CLOSURE','MERGER',
                'CONVERSION_TO_UNIVERSITY','CLOSURE_BY_AICTE']), name='case_supported_path')]


class ClearanceTask(models.Model):
    case = models.ForeignKey(ReleaseCase, on_delete=models.PROTECT, related_name='clearances')
    unit = models.CharField(max_length=40)
    status = models.CharField(max_length=12, default='OPEN', choices=[(s, s) for s in ['OPEN', 'CLEARED', 'OBJECTION', 'HOLD']])
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    reason = models.TextField(max_length=2000, blank=True)
    evidence_ref = models.CharField(max_length=200, blank=True)
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'unit'], name='case_unit_unique'),
            models.CheckConstraint(condition=Q(status='OPEN', decided_by__isnull=True) |
                (Q(status__in=['CLEARED', 'OBJECTION', 'HOLD'], decided_by__isnull=False) & ~Q(reason='') & ~Q(evidence_ref='')),
                name='case_clearance_decision_evidenced')]


class PenaltyAssessment(models.Model):
    case = models.ForeignKey(ReleaseCase, on_delete=models.PROTECT, related_name='penalties')
    kind = models.CharField(max_length=40)
    clause = models.CharField(max_length=150)
    base_paise = models.PositiveBigIntegerField()
    rate_bps = models.PositiveIntegerField()
    amount_paise = models.PositiveBigIntegerField()
    status = models.CharField(max_length=12, default='PROPOSED')
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    reason = models.TextField(max_length=2000)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['case', 'kind'], name='case_penalty_kind_unique'),
            models.CheckConstraint(condition=Q(rate_bps__lte=10000, base_paise__gt=0), name='case_penalty_range'),
            models.CheckConstraint(condition=(Q(status='PROPOSED', decided_by__isnull=True) |
                Q(status='CONFIRMED', decided_by__isnull=False)) & ~Q(reason=''), name='case_penalty_disposition')]


class IssuedLetter(models.Model):
    case = models.OneToOneField(ReleaseCase, on_delete=models.PROTECT, related_name='letter')
    serial = models.CharField(max_length=80, unique=True)
    kind = models.CharField(max_length=20)
    institution_name = models.CharField(max_length=250)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='owned_letters')
    issued_at = models.DateTimeField(auto_now_add=True)
    pdf = models.BinaryField()
    sha256 = models.CharField(max_length=64)
    token_sha256 = models.CharField(max_length=64, unique=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.TextField(max_length=2000, blank=True)

