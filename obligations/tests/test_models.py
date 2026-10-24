from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from obligations.models import DepositObligation, InstitutionProfile, ProgrammeApproval, RuleSet
from portal.models import Institution


class ObligationModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.institution = Institution.objects.create(code='SYNTHETIC-A', name='Synthetic college')
        cls.other = Institution.objects.create(code='SYNTHETIC-B', name='Other synthetic college')
        cls.approver = get_user_model().objects.create_user(username='synthetic-policy-reviewer')

    def profile(self, **overrides):
        fields = dict(institution=self.institution, aicte_id='SYNTHETIC-1',
                      trust_name='Synthetic trust', institution_type='PRIVATE', region='North',
                      state='Delhi', contact_email='synthetic@example.invalid')
        return InstitutionProfile(**(fields | overrides))

    def approval(self, **overrides):
        fields = dict(institution=self.institution, programme='Synthetic engineering', level='UG',
                      approved_on=date(2026, 10, 24), loa_ref='SYNTHETIC-LOA-1',
                      land_tenure='OWNED', building_tenure='LEASED')
        return ProgrammeApproval(**(fields | overrides))

    def rules(self, **overrides):
        fields = dict(code='synthetic-test-only', version=1, effective_from=date(2026, 1, 1),
                      payload={'test_only': True}, source_clause='Synthetic clause',
                      source_document='Synthetic test fixture, not an APH policy')
        return RuleSet(**(fields | overrides))

    def assert_db_rejects(self, model, fields):
        with self.assertRaises(IntegrityError), transaction.atomic():
            model.objects.create(**fields)

    def test_profile_extends_existing_identity_without_changing_it(self):
        profile = self.profile()
        profile.full_clean()
        profile.save()
        self.institution.refresh_from_db()
        self.assertEqual(self.institution.deposit_profile, profile)
        self.assertEqual(self.institution.name, 'Synthetic college')
        self.assertEqual(Institution.objects.count(), 2)

    def test_profile_aicte_id_is_unique(self):
        self.profile().save()
        with self.assertRaises(ValidationError):
            self.profile(institution=self.other).full_clean()
        self.assert_db_rejects(InstitutionProfile, dict(
            institution=self.other, aicte_id='SYNTHETIC-1'))

    def test_profile_is_one_per_institution(self):
        self.profile().save()
        self.assert_db_rejects(InstitutionProfile, dict(
            institution=self.institution, aicte_id='SYNTHETIC-2'))

    def test_profile_requires_valid_master_data(self):
        for invalid in [dict(aicte_id=''), dict(contact_email='not-email'),
                        dict(institution_type='UNSUPPORTED'), dict(region=''), dict(state='')]:
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                self.profile(**invalid).full_clean()

    def test_approval_records_land_and_building_tenure_independently(self):
        approval = self.approval()
        approval.full_clean()
        approval.save()
        self.assertEqual(self.institution.programme_approvals.get(), approval)
        self.assertEqual((approval.land_tenure, approval.building_tenure), ('OWNED', 'LEASED'))

    def test_approval_identity_unique_but_new_approval_reference_allowed(self):
        first = self.approval()
        first.save()
        with self.assertRaises(ValidationError):
            self.approval().full_clean()
        self.assert_db_rejects(ProgrammeApproval, dict(
            institution=self.institution, programme=first.programme, level=first.level,
            approved_on=first.approved_on, loa_ref=first.loa_ref, land_tenure='OWNED', building_tenure='OWNED'))
        self.approval(loa_ref='SYNTHETIC-EOA-2').save()
        self.assertEqual(self.institution.programme_approvals.count(), 2)

    def test_approval_rejects_invalid_choices_and_missing_evidence(self):
        for invalid in [dict(level='PHD'), dict(land_tenure=''), dict(building_tenure='INVALID'),
                        dict(loa_ref=''), dict(approved_on=None), dict(programme='')]:
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                self.approval(**invalid).full_clean()

    def test_rule_versions_keep_separate_payloads(self):
        first, second = self.rules(), self.rules(version=2, payload={'test_only': 'v2'})
        for rule in [first, second]:
            rule.full_clean()
            rule.save()
        first.refresh_from_db()
        self.assertEqual(first.payload, {'test_only': True})
        self.assertEqual(second.version, 2)

    def test_rule_code_and_version_are_unique(self):
        rule = self.rules()
        rule.save()
        self.assert_db_rejects(RuleSet, dict(code=rule.code, version=1, effective_from=rule.effective_from))

    def test_rule_version_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self.rules(version=0).full_clean()
        self.assert_db_rejects(RuleSet, dict(code='zero', version=0, effective_from=date(2026, 1, 1)))

    def test_rule_effective_dates_allow_open_and_inclusive_end(self):
        for end in [None, date(2026, 1, 1), date(2027, 1, 1)]:
            with self.subTest(end=end):
                self.rules(effective_to=end).full_clean()
        with self.assertRaises(ValidationError):
            self.rules(effective_to=date(2025, 12, 31)).full_clean()
        self.assert_db_rejects(RuleSet, dict(code='reversed', version=1,
                              effective_from=date(2026, 1, 1), effective_to=date(2025, 1, 1)))

    def test_rule_payload_must_be_an_object_and_source_is_required(self):
        for payload in [[], ['invalid'], 'text', 5, None]:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                self.rules(payload=payload).full_clean()
        self.rules(payload={}).full_clean()
        for field in ['source_clause', 'source_document']:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.rules(**{field: ''}).full_clean()

    def test_unknown_legacy_requirement_does_not_invent_money_or_dates(self):
        obligation = DepositObligation(institution=self.institution, basis='MIGRATED')
        obligation.full_clean()
        obligation.save()
        obligation.refresh_from_db()
        self.assertIsNone(obligation.required_paise)
        self.assertIsNone(obligation.term_start)
        self.assertIsNone(obligation.term_end)
        self.assertIsNone(obligation.rule_version)
        self.assertEqual(obligation.status, 'UNKNOWN')

    def test_obligation_records_exact_paise_and_rule_identity(self):
        rule = self.rules()
        rule.save()
        obligation = DepositObligation(institution=self.institution, basis='APPROVAL',
            basis_reference='SYNTHETIC-LOA-1', rule_version=rule, required_paise=50000025,
            term_start=date(2026, 10, 24), term_end=date(2036, 10, 24), status='DUE')
        obligation.full_clean()
        obligation.save()
        obligation.refresh_from_db()
        self.assertEqual(obligation.required_paise, 50000025)
        self.assertEqual(obligation.rule_version_id, rule.pk)

    def test_obligation_term_pair_and_order_are_enforced(self):
        for start, end in [(date(2026, 1, 1), None), (None, date(2036, 1, 1)),
                           (date(2036, 1, 1), date(2026, 1, 1))]:
            values = dict(institution=self.institution, term_start=start, term_end=end)
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValidationError):
                    DepositObligation(**values).full_clean()
                self.assert_db_rejects(DepositObligation, values)

    def test_amount_cannot_be_negative_zero_or_unknown_in_a_known_status(self):
        for amount, status in [(-1, 'UNKNOWN'), (0, 'UNKNOWN'), (0, 'DUE'),
                               (None, 'DUE'), (None, 'MET'), (None, 'EXEMPT')]:
            values = dict(institution=self.institution, required_paise=amount, status=status)
            with self.subTest(amount=amount, status=status):
                with self.assertRaises(ValidationError):
                    DepositObligation(**values).full_clean()
                self.assert_db_rejects(DepositObligation, values)

    def test_exemption_needs_complete_evidence_and_an_approver(self):
        values = dict(institution=self.institution, required_paise=0, status='EXEMPT',
                      exemption_code='SYNTHETIC', exemption_clause='Test clause',
                      exemption_reason='Synthetic exemption', exemption_approved_by=self.approver)
        exemption = DepositObligation(**values)
        exemption.full_clean()
        exemption.save()
        for field in ['exemption_code', 'exemption_clause', 'exemption_reason', 'exemption_approved_by']:
            invalid = values | {field: None if field.endswith('approved_by') else ''}
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    DepositObligation(**invalid).full_clean()
                self.assert_db_rejects(DepositObligation, invalid)

    def test_whitespace_exemption_and_metadata_on_non_exempt_row_are_invalid(self):
        for values in [dict(exemption_reason='   ', status='EXEMPT', required_paise=0),
                       dict(exemption_code='not-approved')]:
            with self.subTest(values=values), self.assertRaises(ValidationError):
                DepositObligation(institution=self.institution, **values).full_clean()

    def test_institution_rule_and_approval_actor_are_protected(self):
        rule = self.rules(approved_by=self.approver)
        rule.save()
        DepositObligation.objects.create(institution=self.institution, rule_version=rule)
        for obj in [self.institution, rule, self.approver]:
            with self.subTest(model=obj.__class__.__name__), self.assertRaises(ProtectedError):
                obj.delete()

    def test_obligations_for_two_institutions_remain_separate(self):
        first = DepositObligation.objects.create(institution=self.institution)
        second = DepositObligation.objects.create(institution=self.other)
        self.assertEqual(list(self.institution.deposit_obligations.all()), [first])
        self.assertEqual(list(self.other.deposit_obligations.all()), [second])
