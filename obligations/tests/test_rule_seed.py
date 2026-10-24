from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase

from obligations.models import DepositObligation, InstitutionProfile, ProgrammeApproval, RuleSet
from obligations.rules import rule_snapshot
from portal.models import Institution, Instrument


class DraftRuleSeedTests(TestCase):
    def seed(self, **overrides):
        output = StringIO()
        call_command('seed_obligation_rules', **(dict(effective_from='2026-01-01', stdout=output) | overrides))
        return output.getvalue()

    def test_seed_is_explicit_unapproved_configuration_only(self):
        self.assertIn('DRAFT_DEMO_NOT_APPROVED', self.seed())
        rule = RuleSet.objects.get()
        self.assertEqual(rule.code, 'sd_policy_demo')
        self.assertIsNone(rule.approved_by)
        self.assertEqual(rule.effective_from, date(2026, 1, 1))
        for model in [get_user_model(), Institution, Instrument, InstitutionProfile,
                      ProgrammeApproval, DepositObligation]:
            self.assertEqual(model.objects.count(), 0)

    def test_repeat_is_idempotent_and_historical_version_remains(self):
        self.seed()
        first = RuleSet.objects.get()
        before = rule_snapshot(first, date(2026, 1, 1))
        self.assertIn('unchanged', self.seed())
        self.assertEqual(RuleSet.objects.count(), 1)
        self.seed(rule_version=2, effective_from='2027-01-01')
        first.refresh_from_db()
        self.assertEqual(rule_snapshot(first, date(2026, 1, 1)), before)
        self.assertEqual(RuleSet.objects.count(), 2)

    def test_seed_does_not_overwrite_a_changed_payload(self):
        self.seed()
        rule = RuleSet.objects.get()
        changed = rule.payload
        changed['proof_days'] = 16
        RuleSet.objects.filter(pk=rule.pk).update(payload=changed)
        with self.assertRaises(CommandError):
            self.seed()
        rule.refresh_from_db()
        self.assertEqual(rule.payload['proof_days'], 16)

    def test_seed_does_not_overwrite_changed_metadata_or_approver(self):
        self.seed()
        rule = RuleSet.objects.get()
        for field, value in [('source_clause', 'Changed'), ('effective_to', date(2026, 12, 31)),
                             ('approved_by', get_user_model().objects.create_user(username='synthetic-approver'))]:
            with self.subTest(field=field):
                old = getattr(rule, field)
                setattr(rule, field, value)
                rule.save()
                with self.assertRaises(CommandError):
                    self.seed()
                setattr(rule, field, old)
                rule.save()

    def test_invalid_dates_and_versions_write_nothing(self):
        for args in [dict(effective_from='bad'), dict(rule_version=0),
                     dict(effective_to='2025-01-01'), dict(effective_to='bad')]:
            with self.subTest(args=args), self.assertRaises(CommandError):
                self.seed(**args)
            self.assertEqual(RuleSet.objects.count(), 0)

    def test_conflicting_window_is_not_silently_rewritten(self):
        self.seed()
        with self.assertRaises(CommandError):
            self.seed(effective_from='2026-02-01')
        self.assertEqual(RuleSet.objects.get().effective_from, date(2026, 1, 1))
