from datetime import date
from django.test import override_settings
from obligations.coverage import coverage
from obligations.models import DepositObligation, RuleSet
from portal.tests.common import PortalTestCase


@override_settings(ROOT_URLCONF='config.urls')
class CoverageTests(PortalTestCase):
    def obligation(self):
        return DepositObligation.objects.create(institution=self.institution_a, required_paise=60_000_000,
            status='DUE', term_start=date(2026, 1, 1), term_end=date(2036, 1, 1))

    def test_unknown_unapproved_policy_is_never_claimed_sufficient(self):
        obligation = self.obligation()
        self.assertFalse(coverage(obligation, date(2026, 10, 24))['known'])
        self.assertIsNone(coverage(obligation, date(2026, 10, 24))['shortfall_paise'])

    def test_reviewed_requirement_scoping_amount_and_term_gap(self):
        obligation = self.obligation()
        obligation.rule_version = RuleSet.objects.create(code='synthetic-only', version=1,
            effective_from=date(2026, 1, 1), approved_by=self.officer,
            source_clause='SYNTHETIC TEST', source_document='Synthetic test fixture, not a regulatory policy')
        obligation.save()
        item = self.draft()
        item.obligation, item.status = obligation, 'ACCEPTED'
        item.save()
        result = coverage(obligation, date(2026, 10, 24))
        self.assertEqual(result['shortfall_paise'], 9_999_975)
        self.assertTrue(result['term_gap'])
        item.released_at = __import__('django.utils.timezone', fromlist=['now']).now()
        item.save()
        self.assertEqual(coverage(obligation, date(2026, 10, 24))['held_paise'], 0)
        self.client.force_login(self.b)
        path = f'/api/institutions/{self.institution_a.pk}/obligations'
        self.assertEqual(self.client.get(path).status_code, 404)
        self.client.force_login(self.a)
        self.assertEqual(len(self.client.get(path).json()['results']), 1)
