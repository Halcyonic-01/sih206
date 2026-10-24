"""S1 storage foundation. Policy evaluation and publication belong to S2.

As with the portal models, callers must use full_clean() before saving user
input. Database constraints additionally protect local row invariants.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


def validate_payload_object(value):
    if not isinstance(value, dict):
        raise ValidationError('A rule payload must be a JSON object.')


class InstitutionProfile(models.Model):
    class Type(models.TextChoices):
        GOVERNMENT = 'GOVERNMENT', 'Government'
        AIDED = 'AIDED', 'Government aided'
        PRIVATE = 'PRIVATE', 'Private'
        UNIVERSITY = 'UNIVERSITY', 'University'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'

    institution = models.OneToOneField(
        'portal.Institution', on_delete=models.PROTECT, related_name='deposit_profile')
    aicte_id = models.CharField(max_length=50, unique=True)
    trust_name = models.CharField(max_length=250)
    institution_type = models.CharField(max_length=20, choices=Type)
    region = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    contact_email = models.EmailField()
    status = models.CharField(max_length=10, choices=Status, default=Status.ACTIVE)
    version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(version__gte=1), name='profile_version_positive')]

    def __str__(self):
        return f'{self.aicte_id}: {self.institution}'


class ProgrammeApproval(models.Model):
    class Level(models.TextChoices):
        DIPLOMA = 'DIPLOMA', 'Diploma'
        UG = 'UG', 'Undergraduate'
        PG = 'PG', 'Postgraduate'

    class Tenure(models.TextChoices):
        OWNED = 'OWNED', 'Owned'
        LEASED = 'LEASED', 'Leased'

    institution = models.ForeignKey(
        'portal.Institution', on_delete=models.PROTECT, related_name='programme_approvals')
    programme = models.CharField(max_length=120)
    level = models.CharField(max_length=10, choices=Level)
    approved_on = models.DateField()
    loa_ref = models.CharField('LoA / EoA reference', max_length=150)
    land_tenure = models.CharField(max_length=10, choices=Tenure)
    building_tenure = models.CharField(max_length=10, choices=Tenure)
    version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=['institution', 'programme', 'level', 'loa_ref'],
            name='obligation_unique_approval'),
            models.CheckConstraint(condition=Q(version__gte=1), name='approval_version_positive')]

    def __str__(self):
        return f'{self.institution}: {self.programme} {self.level} ({self.loa_ref})'


class RuleSet(models.Model):
    """Versioned rule metadata, not a published policy or executable rules engine."""

    code = models.SlugField(max_length=80)
    version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True, validators=[validate_payload_object])
    source_clause = models.CharField(max_length=150)
    source_document = models.CharField(max_length=500)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name='deposit_rule_approvals')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['code', 'version'], name='obligation_rule_version_unique'),
            models.CheckConstraint(condition=Q(version__gte=1), name='obligation_rule_version_positive'),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=F('effective_from')),
                name='obligation_rule_dates_ordered'),
        ]

    def clean(self):
        super().clean()
        validate_payload_object(self.payload)
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({'effective_to': 'The effective end cannot precede its start.'})

    def __str__(self):
        return f'{self.code} v{self.version}'


class DepositObligation(models.Model):
    class Basis(models.TextChoices):
        UNKNOWN = 'UNKNOWN', 'Not yet established'
        APPROVAL = 'APPROVAL', 'Programme approval'
        CONVERSION = 'CONVERSION', 'Institution conversion'
        MIGRATED = 'MIGRATED', 'Legacy record; requirement needs review'

    class Status(models.TextChoices):
        UNKNOWN = 'UNKNOWN', 'Requirement not yet established'
        DUE = 'DUE', 'Due'
        PARTIALLY_MET = 'PARTIALLY_MET', 'Partially met'
        MET = 'MET', 'Met'
        EXEMPT = 'EXEMPT', 'Exemption recorded'
        EXTENDED = 'EXTENDED', 'Extended'
        RELEASED = 'RELEASED', 'Released'
        FORFEITED = 'FORFEITED', 'Forfeited'

    institution = models.ForeignKey(
        'portal.Institution', on_delete=models.PROTECT, related_name='deposit_obligations')
    basis = models.CharField(max_length=15, choices=Basis, default=Basis.UNKNOWN)
    basis_reference = models.TextField(blank=True)
    rule_version = models.ForeignKey(
        RuleSet, null=True, blank=True, on_delete=models.PROTECT, related_name='obligations')
    required_paise = models.PositiveBigIntegerField(null=True, blank=True)
    term_start = models.DateField(null=True, blank=True)
    term_end = models.DateField(null=True, blank=True)
    intimation_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status, default=Status.UNKNOWN)
    exemption_code = models.CharField(max_length=80, blank=True)
    exemption_clause = models.CharField(max_length=150, blank=True)
    exemption_reason = models.TextField(blank=True)
    exemption_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name='deposit_exemptions')
    version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(version__gte=1), name='ledger_version_positive'),
            models.CheckConstraint(
                condition=Q(term_start__isnull=True, term_end__isnull=True) |
                          Q(term_start__isnull=False, term_end__isnull=False, term_end__gte=F('term_start')),
                name='obligation_term_consistent'),
            models.CheckConstraint(
                condition=Q(required_paise__isnull=True, status='UNKNOWN') |
                          Q(required_paise__isnull=False, required_paise__gt=0) |
                          Q(required_paise__isnull=False, required_paise=0, status='EXEMPT'),
                name='obligation_amount_consistent'),
            models.CheckConstraint(
                condition=~Q(status='EXEMPT') |
                          (Q(required_paise__isnull=False, required_paise=0, exemption_approved_by__isnull=False) &
                           ~Q(exemption_code='') & ~Q(exemption_clause='') & ~Q(exemption_reason='')),
                name='obligation_exemption_evidenced'),
        ]

    def clean(self):
        super().clean()
        if (self.term_start is None) != (self.term_end is None):
            raise ValidationError('Provide both term dates, or leave both unknown.')
        if self.term_start and self.term_end and self.term_end < self.term_start:
            raise ValidationError({'term_end': 'The term end cannot precede its start.'})
        evidence = (self.exemption_code, self.exemption_clause, self.exemption_reason)
        if self.status == self.Status.EXEMPT:
            if self.required_paise != 0 or not self.exemption_approved_by_id or not all(
                    value.strip() for value in evidence):
                raise ValidationError('An exemption needs zero amount, a code, clause, reason and approver.')
        elif any(value.strip() for value in evidence) or self.exemption_approved_by_id:
            raise ValidationError('Exemption metadata requires EXEMPT status.')

    def __str__(self):
        return f'{self.institution}: obligation #{self.pk or "unsaved"} ({self.status})'


class MasterAudit(models.Model):
    """Entity audit for owned masters; never fabricate an Instrument audit link."""
    institution = models.ForeignKey('portal.Institution', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    entity = models.CharField(max_length=40)
    entity_id = models.PositiveBigIntegerField()
    action = models.CharField(max_length=50)
    reason = models.TextField(max_length=2000)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['pk']


class CsvImport(models.Model):
    """Private SIMULATED preview, consumed once by its creating officer."""
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    source = models.BinaryField()
    source_sha256 = models.CharField(max_length=64)
    identity_sha256 = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    committed_at = models.DateTimeField(null=True, blank=True)
    created_ids = models.JSONField(default=list)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)


# Owned storage only: shared settings and portal migration numbering stay intact.
from .case_models import ClearanceTask, IssuedLetter, PenaltyAssessment, ReleaseCase  # noqa: E402,F401
