import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


def document_path(instance, filename):
    return f'{instance.instrument_id}/{uuid.uuid4().hex}.pdf'


class Institution(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)


class Instrument(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SUBMITTED = 'SUBMITTED', 'Submitted'
        CHANGES_REQUESTED = 'CHANGES_REQUESTED', 'Changes requested'
        ACCEPTED = 'ACCEPTED', 'Accepted for tracking'

    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    reference = models.CharField('FDR reference', max_length=100)
    bank = models.CharField('Issuing bank', max_length=200)
    amount_paise = models.PositiveBigIntegerField()
    issue_date = models.DateField()
    maturity_date = models.DateField()
    status = models.CharField(max_length=25, choices=Status, default=Status.DRAFT)
    predecessor = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT,
                                       related_name='successor')
    superseded_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-pk']
        constraints = [
            models.CheckConstraint(condition=Q(amount_paise__gt=0), name='amount_positive'),
            models.CheckConstraint(condition=Q(maturity_date__gte=F('issue_date')),
                                   name='maturity_after_issue'),
            models.CheckConstraint(condition=Q(predecessor__isnull=True) | ~Q(predecessor=F('pk')),
                                   name='instrument_not_own_predecessor'),
            models.CheckConstraint(condition=Q(superseded_at__isnull=True) | Q(status='ACCEPTED'),
                                   name='superseded_instrument_accepted'),
            models.CheckConstraint(condition=Q(released_at__isnull=True) |
                                   Q(status='ACCEPTED', superseded_at__isnull=True),
                                   name='released_instrument_accepted_not_superseded'),
        ]

    def clean(self):
        super().clean()
        if self.pk:
            original = Instrument.objects.filter(pk=self.pk).values('predecessor_id').first()
            if original and original['predecessor_id'] != self.predecessor_id:
                raise ValidationError({'predecessor': 'An existing instrument cannot be reparented.'})
        self.validate_lineage()

    def validate_lineage(self):
        seen = {self.pk} if self.pk else set()
        ancestor_id = self.predecessor_id
        while ancestor_id is not None:
            if ancestor_id in seen:
                raise ValidationError({'predecessor': 'Renewal lineage cannot contain a cycle.'})
            seen.add(ancestor_id)
            ancestor = Instrument.objects.filter(pk=ancestor_id).values('institution_id', 'predecessor_id').first()
            if not ancestor or ancestor['institution_id'] != self.institution_id:
                raise ValidationError({'predecessor': 'All linked instruments must belong to the same institution.'})
            ancestor_id = ancestor['predecessor_id']

    @property
    def is_superseded(self):
        return self.superseded_at is not None

    @property
    def is_current(self):
        return self.status == self.Status.ACCEPTED and not self.is_superseded and not self.is_released

    @property
    def is_released(self):
        return self.released_at is not None

    @property
    def has_active_release(self):
        return self.release_requests.filter(status__in=['PENDING', 'APPROVED']).exists()

    @property
    def amount(self):
        return Decimal(self.amount_paise) / 100


class Document(models.Model):
    class Kind(models.TextChoices):
        FDR = 'FDR', 'FDR supporting document'
        RELEASE_EVIDENCE = 'RELEASE_EVIDENCE', 'Release completion evidence'

    instrument = models.ForeignKey(Instrument, on_delete=models.PROTECT, related_name='documents')
    kind = models.CharField(max_length=20, choices=Kind, default=Kind.FDR)
    file = models.FileField(upload_to=document_path)
    original_name = models.CharField(max_length=255)
    size_bytes = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return f'{self.original_name} (document #{self.pk})'


class ReleaseRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending authority decision'
        APPROVED = 'APPROVED', 'Release authorized; completion pending'
        REJECTED = 'REJECTED', 'Rejected'
        COMPLETED = 'COMPLETED', 'Release completion recorded'

    instrument = models.ForeignKey(Instrument, on_delete=models.PROTECT, related_name='release_requests')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     related_name='release_requests')
    reason = models.TextField(max_length=2000)
    status = models.CharField(max_length=12, choices=Status, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    decision_reason = models.TextField(blank=True, max_length=2000)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.PROTECT, related_name='release_decisions')
    decided_at = models.DateTimeField(null=True, blank=True)
    completion_notes = models.TextField(blank=True, max_length=2000)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.PROTECT, related_name='release_completions')
    completed_at = models.DateTimeField(null=True, blank=True)
    completion_evidence = models.ForeignKey(Document, null=True, blank=True, on_delete=models.PROTECT,
                                             related_name='release_completions')

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['instrument'], condition=Q(status__in=['PENDING', 'APPROVED']),
                                    name='one_open_release_per_instrument'),
            models.CheckConstraint(
                condition=Q(status='PENDING', decided_by__isnull=True, decided_at__isnull=True, decision_reason='') |
                          (Q(status__in=['APPROVED', 'REJECTED', 'COMPLETED'], decided_by__isnull=False,
                             decided_at__isnull=False) & ~Q(decision_reason='')),
                name='release_decision_consistent'),
            models.CheckConstraint(
                condition=(Q(status='COMPLETED', completed_by__isnull=False, completed_at__isnull=False,
                             completion_evidence__isnull=False) & ~Q(completion_notes='')) |
                          Q(status__in=['PENDING', 'APPROVED', 'REJECTED'], completed_by__isnull=True,
                            completed_at__isnull=True, completion_evidence__isnull=True, completion_notes=''),
                name='release_completion_consistent'),
            models.CheckConstraint(condition=Q(decided_by__isnull=True) | ~Q(decided_by=F('requested_by')),
                                   name='release_no_self_decision'),
            models.CheckConstraint(condition=Q(completed_by__isnull=True) | ~Q(completed_by=F('requested_by')),
                                   name='release_no_self_completion'),
        ]

    def clean(self):
        super().clean()
        if self.completion_evidence_id and self.instrument_id:
            document = self.completion_evidence
            if document.instrument_id != self.instrument_id or document.kind != Document.Kind.RELEASE_EVIDENCE:
                raise ValidationError({'completion_evidence': 'Use release evidence belonging to this instrument.'})


class ReviewObservation(models.Model):
    class Severity(models.TextChoices):
        WARNING = 'WARNING', 'Warning (does not block acceptance)'
        BLOCKING = 'BLOCKING', 'Blocking (must be resolved before acceptance)'

    instrument = models.ForeignKey(Instrument, on_delete=models.PROTECT, related_name='observations')
    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name='observations')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                 related_name='authored_observations')
    page_number = models.PositiveIntegerField(null=True, blank=True)
    severity = models.CharField(max_length=10, choices=Severity, default=Severity.BLOCKING)
    comment = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    resolution = models.TextField(blank=True, max_length=2000)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.PROTECT, related_name='resolved_observations')
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at', 'pk']
        constraints = [
            models.CheckConstraint(condition=Q(page_number__isnull=True) | Q(page_number__gte=1),
                                   name='observation_page_positive'),
            models.CheckConstraint(
                condition=(Q(resolved_at__isnull=True, resolved_by__isnull=True, resolution='') |
                           (Q(resolved_at__isnull=False, resolved_by__isnull=False) & ~Q(resolution=''))),
                name='observation_resolution_consistent'),
        ]

    def clean(self):
        super().clean()
        if self.document_id and self.instrument_id and self.document.instrument_id != self.instrument_id:
            raise ValidationError({'document': 'Choose a document attached to this instrument.'})

    @property
    def is_resolved(self):
        return self.resolved_at is not None


class AuditEvent(models.Model):
    instrument = models.ForeignKey(Instrument, on_delete=models.PROTECT, related_name='audit_events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=40)
    reason = models.TextField(blank=True)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']
