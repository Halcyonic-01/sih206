"""OpenAPI descriptions for S2; validation and business rules stay in services.

Read serializers describe existing snapshot keys, not a new wire representation.
These schemas are not a substitute for strict service-side input validation.
"""
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.extensions import OpenApiSerializerExtension
from rest_framework import serializers as s
from obligations.models import DepositObligation, InstitutionProfile, ProgrammeApproval


@extend_schema_field({'oneOf': [{'type': 'integer', 'minimum': 0},
    {'type': 'string', 'pattern': '^[0-9]+$', 'description': 'Exact legacy paise beyond JavaScript safe range.'}]})
class PaiseRead(s.JSONField):
    pass


class Error(s.Serializer):
    detail = s.CharField()
    code = s.CharField()
    errors = s.DictField(child=s.ListField(child=s.CharField()), required=False)


def responses(success, *, created=False):
    return {201 if created else 200: success, **{status: Error for status in [400, 401, 403, 404, 409, 503]}}


class ProfileRead(s.ModelSerializer):
    institution_type = s.CharField(help_text='GOVERNMENT, AIDED, PRIVATE or UNIVERSITY')
    status = s.CharField(help_text='ACTIVE or INACTIVE')
    class Meta:
        model = InstitutionProfile
        fields = '__all__'


class MasterActions(s.Serializer):
    can_edit = s.BooleanField()


class InstitutionRead(s.Serializer):
    id = s.IntegerField()
    code = s.CharField()
    name = s.CharField()
    profile = ProfileRead(allow_null=True)
    version = s.IntegerField(allow_null=True)
    actions = MasterActions()


class InstitutionCreate(s.Serializer):
    code = s.CharField(max_length=30)
    name = s.CharField(max_length=200)
    aicte_id = s.CharField(max_length=50)
    trust_name = s.CharField(max_length=250)
    institution_type = s.CharField(help_text='GOVERNMENT, AIDED, PRIVATE or UNIVERSITY')
    region = s.CharField(max_length=100)
    state = s.CharField(max_length=100)
    contact_email = s.EmailField()
    status = s.CharField(help_text='ACTIVE or INACTIVE', required=False)
    reason = s.CharField(max_length=2000)


class VersionedUpdate(s.Serializer):
    version = s.IntegerField(min_value=1)

    def get_fields(self):
        fields = super().get_fields()
        for name, field in fields.items():
            field.required = name in {'version', 'reason'}
        return fields


class InstitutionUpdate(VersionedUpdate, InstitutionCreate):
    pass


class ApprovalRead(s.ModelSerializer):
    level = s.CharField(help_text='DIPLOMA, UG or PG')
    land_tenure = s.CharField(help_text='OWNED or LEASED')
    building_tenure = s.CharField(help_text='OWNED or LEASED')
    class Meta:
        model = ProgrammeApproval
        fields = '__all__'


class ApprovalCreate(s.Serializer):
    programme = s.CharField(max_length=120)
    level = s.CharField(help_text='DIPLOMA, UG or PG')
    approved_on = s.DateField()
    loa_ref = s.CharField(max_length=150)
    land_tenure = s.CharField(help_text='OWNED or LEASED')
    building_tenure = s.CharField(help_text='OWNED or LEASED')
    reason = s.CharField(max_length=2000)


class ApprovalUpdate(VersionedUpdate, ApprovalCreate):
    pass


class ObligationRead(s.ModelSerializer):
    required_paise = PaiseRead(allow_null=True)
    basis = s.CharField(help_text='UNKNOWN, APPROVAL, CONVERSION or MIGRATED')
    status = s.CharField(help_text='UNKNOWN, DUE, PARTIALLY_MET, MET, EXEMPT, EXTENDED, RELEASED or FORFEITED')

    class Meta:
        model = DepositObligation
        fields = '__all__'


class ObligationCreate(s.Serializer):
    basis = s.CharField(help_text='UNKNOWN, APPROVAL, CONVERSION or MIGRATED', required=False)
    basis_reference = s.CharField(allow_blank=True, required=False)
    rule_version_id = s.IntegerField(min_value=1, allow_null=True, required=False)
    required_paise = s.IntegerField(min_value=1, max_value=2**53-1, allow_null=True, required=False)
    term_start = s.DateField(allow_null=True, required=False)
    term_end = s.DateField(allow_null=True, required=False)
    intimation_date = s.DateField(allow_null=True, required=False)
    reason = s.CharField(max_length=2000)


class ObligationUpdate(VersionedUpdate, ObligationCreate):
    pass


class VersionedUpdateSchema(OpenApiSerializerExtension):
    """PATCH is partial in data fields, but version and reason are still required."""
    target_class = VersionedUpdate
    match_subclasses = True

    def map_serializer(self, auto_schema, direction):
        schema = auto_schema._map_serializer(self.target, direction, bypass_extensions=True)
        if direction == 'request':
            schema['required'] = ['reason', 'version']
        return schema


class ObligationDetailRead(ObligationRead):
    actions = MasterActions()
    assessment = s.JSONField(help_text='Source-dependent coverage, holdings, findings, proof assessment and suggested open actions. '
        'UNAVAILABLE has null coverage/findings/holdings/open_actions and a reason; it never asserts zero coverage.')


class CalculatorApproval(s.Serializer):
    programme = s.CharField()
    level = s.CharField(help_text='DIPLOMA, UG or PG')
    land_tenure = s.CharField(help_text='OWNED or LEASED')
    building_tenure = s.CharField(help_text='OWNED or LEASED')


class CalculatorRequest(s.Serializer):
    institution_id = s.IntegerField(min_value=1)
    rule_set_id = s.IntegerField(min_value=1)
    approvals = CalculatorApproval(many=True, max_length=100)


class CalculatorRead(s.Serializer):
    required_paise = s.IntegerField()
    multiplier = s.IntegerField()
    breakdown = s.ListField(child=s.JSONField())
    as_of = s.DateField()
    exemption_assessed = s.BooleanField()
    rule_code = s.CharField()
    rule_version = s.IntegerField()
    rule_sha256 = s.CharField()
    source_document = s.CharField()
    source_clause = s.CharField()
    policy_label = s.CharField()


class RuleRead(s.Serializer):
    id = s.IntegerField()
    code = s.CharField()
    version = s.IntegerField()
    effective_from = s.DateField()
    effective_to = s.DateField(allow_null=True)
    policy_label = s.CharField()


def paginated(name, resource):
    return type(name, (s.Serializer,), {
        'count': s.IntegerField(), 'page': s.IntegerField(), 'page_size': s.IntegerField(),
        'total_pages': s.IntegerField(), 'results': resource(many=True), '__module__': __name__})


InstitutionPage = paginated('InstitutionPage', InstitutionRead)
ApprovalPage = paginated('ApprovalPage', ApprovalRead)
ObligationPage = paginated('ObligationPage', ObligationRead)
RulePage = paginated('RulePage', RuleRead)
