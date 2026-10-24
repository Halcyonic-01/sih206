from datetime import date, datetime, timedelta, timezone as dt_timezone
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from access.models import UnitAssignment
from notifications.models import Notification
from notifications.rules import DEFAULTS, load_config, run_rules, working_days_after
from obligations.models import DepositObligation, InstitutionProfile, RuleSet
from portal.models import AuditEvent, Institution, Instrument, ReleaseRequest, UserProfile
from portal.permissions import AUTHORITY_GROUP, CLEARANCE_GROUP, INSTITUTION_GROUP, OFFICER_GROUP

MATURITY = date(2026, 12, 1)


def days_from_maturity(offset):
    return MATURITY + timedelta(days=offset)


class RulesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.institution = Institution.objects.create(code='A', name='Fictional A')
        cls.other = Institution.objects.create(code='B', name='Fictional B')
        cls.inst_user = User.objects.create_user(username='inst_a', password='x', email='inst-a@example.org')
        cls.inst_user.groups.add(Group.objects.create(name=INSTITUTION_GROUP))
        UserProfile.objects.create(user=cls.inst_user, institution=cls.institution)
        cls.officer = User.objects.create_user(username='officer', password='x', email='officer@example.org')
        cls.officer.groups.add(Group.objects.create(name=OFFICER_GROUP))
        cls.authority = User.objects.create_user(username='authority', password='x')
        cls.authority.groups.add(Group.objects.create(name=AUTHORITY_GROUP))
        clearance = Group.objects.create(name=CLEARANCE_GROUP)
        cls.pgrc = User.objects.create_user(username='pgrc', password='x')
        cls.pgrc.groups.add(clearance)
        UnitAssignment.objects.create(user=cls.pgrc, unit='PGRC')
        cls.vigilance = User.objects.create_user(username='vig', password='x')
        cls.vigilance.groups.add(clearance)
        UnitAssignment.objects.create(user=cls.vigilance, unit='VIGILANCE')

    def instrument(self, status=Instrument.Status.ACCEPTED, maturity=MATURITY, institution=None, reference='FDR-1', **extra):
        return Instrument.objects.create(
            institution=institution or self.institution, reference=reference, bank='Fictional Bank',
            amount_paise=5_000_000, issue_date=date(2026, 1, 1), maturity_date=maturity, status=status,
            created_by=self.inst_user, **extra)

    def run_on(self, as_of, **kwargs):
        return run_rules(as_of, **kwargs)

    def keys(self, template=None):
        rows = Notification.objects.filter(channel='IN_APP')
        if template:
            rows = rows.filter(template_id=template)
        return sorted(set(rows.values_list('idempotency_key', flat=True)))

    def recipients(self, key):
        return set(Notification.objects.filter(idempotency_key=key, channel='IN_APP')
                   .values_list('recipient__username', flat=True))


class MaturityReminderTests(RulesTestCase):
    def setUp(self):
        self.fdr = self.instrument()
        self.key = lambda t: f'instrument:{self.fdr.pk}:maturity:T-{t}:{MATURITY}'

    def test_boundaries_fire_once_at_each_threshold(self):
        expectations = [(-91, None), (-90, 90), (-61, None), (-60, 60), (-31, None), (-30, 30), (-8, None),
                        (-7, 7), (-1, None), (0, None)]
        sent = set()
        for offset, threshold in expectations:
            with self.subTest(offset=offset):
                self.run_on(days_from_maturity(offset))
                if threshold:
                    sent.add(threshold)
                    self.assertIn(self.key(threshold), self.keys('maturity_reminder'))
                self.assertEqual(len(self.keys('maturity_reminder')), len(sent))

    def test_institution_only_at_90_and_60_then_officer_joins_at_30_and_7(self):
        for offset in (-90, -60, -30, -7):
            self.run_on(days_from_maturity(offset))
        self.assertEqual(self.recipients(self.key(90)), {'inst_a'})
        self.assertEqual(self.recipients(self.key(60)), {'inst_a'})
        self.assertEqual(self.recipients(self.key(30)), {'inst_a', 'officer'})
        self.assertEqual(self.recipients(self.key(7)), {'inst_a', 'officer'})

    def test_contact_email_from_the_aicte_profile_gets_an_email(self):
        InstitutionProfile.objects.create(
            institution=self.institution, aicte_id='AICTE-1', trust_name='Trust', institution_type='PRIVATE',
            region='North', state='Delhi', contact_email='registrar@college.example')
        self.run_on(days_from_maturity(-30))
        emails = Notification.objects.filter(channel='EMAIL', idempotency_key=self.key(30))
        self.assertEqual(set(emails.values_list('recipient_email', flat=True)),
                         {'inst-a@example.org', 'registrar@college.example', 'officer@example.org'})

    def test_second_run_the_same_day_adds_nothing(self):
        first = self.run_on(days_from_maturity(-30))
        count = Notification.objects.count()
        second = self.run_on(days_from_maturity(-30))
        self.assertGreater(first.created, 0)
        self.assertEqual((second.created, Notification.objects.count()), (0, count))

    def test_missed_runs_catch_up_with_one_reminder_showing_real_days_left(self):
        self.run_on(days_from_maturity(-20))
        self.assertEqual(self.keys('maturity_reminder'), [self.key(30)])
        self.assertIn('matures in 20 days', Notification.objects.first().subject)
        self.run_on(days_from_maturity(-19))
        self.assertEqual(len(self.keys('maturity_reminder')), 1)

    def test_only_current_records_are_reminded(self):
        self.fdr.delete()
        self.instrument(status=Instrument.Status.SUBMITTED, reference='S')
        self.instrument(status=Instrument.Status.DRAFT, reference='D')
        self.instrument(status=Instrument.Status.ACCEPTED, reference='SUP', superseded_at=datetime(2026, 11, 1, tzinfo=dt_timezone.utc))
        self.instrument(status=Instrument.Status.ACCEPTED, reference='REL', released_at=datetime(2026, 11, 1, tzinfo=dt_timezone.utc))
        self.run_on(days_from_maturity(-30))
        self.assertEqual(Notification.objects.count(), 0)

    def test_a_record_with_an_active_release_is_left_alone(self):
        ReleaseRequest.objects.create(instrument=self.fdr, requested_by=self.inst_user, reason='Release.')
        self.run_on(days_from_maturity(-30))
        self.run_on(days_from_maturity(3))
        self.assertEqual(Notification.objects.count(), 0)

    def test_no_renewal_reminder_when_the_obligation_term_ends_first(self):
        term = SimpleNamespace(term_end=MATURITY - timedelta(days=1))
        with mock.patch.object(Instrument, 'obligation', create=True, new=term):
            self.run_on(days_from_maturity(-30))
        self.assertEqual(Notification.objects.count(), 0)
        later = SimpleNamespace(term_end=MATURITY + timedelta(days=400))
        with mock.patch.object(Instrument, 'obligation', create=True, new=later):
            self.run_on(days_from_maturity(-30))
        self.assertEqual(len(self.keys('maturity_reminder')), 1)


class OverdueAndPenaltyTests(RulesTestCase):
    def setUp(self):
        self.fdr = self.instrument()

    def test_overdue_at_plus_one_and_penalty_review_at_plus_thirty(self):
        overdue = f'instrument:{self.fdr.pk}:renewal-overdue:{MATURITY}'
        penalty = f'instrument:{self.fdr.pk}:penalty-review:{MATURITY}'
        for offset, has_overdue, has_penalty in [(0, False, False), (1, True, False), (29, True, False),
                                                 (30, True, True), (45, True, True)]:
            with self.subTest(offset=offset):
                self.run_on(days_from_maturity(offset))
                keys = self.keys()
                self.assertEqual(overdue in keys, has_overdue)
                self.assertEqual(penalty in keys, has_penalty)
        self.assertEqual(self.recipients(overdue), {'inst_a', 'officer', 'authority'})
        self.assertEqual(self.recipients(penalty), {'officer'})
        self.assertEqual(Notification.objects.filter(idempotency_key=overdue, channel='IN_APP').count(), 3)

    def test_renewed_record_is_not_overdue(self):
        self.fdr.superseded_at = datetime(2026, 11, 20, tzinfo=dt_timezone.utc)
        self.fdr.save()
        self.run_on(days_from_maturity(5))
        self.assertEqual(Notification.objects.count(), 0)


class RuleSetConfigTests(RulesTestCase):
    def rule(self, payload, version=1, **kwargs):
        return RuleSet.objects.create(code='escalation-matrix', version=version, effective_from=date(2026, 1, 1),
                                      payload=payload, source_clause='test', source_document='test', **kwargs)

    def test_defaults_when_no_ruleset(self):
        config = load_config(date(2026, 10, 24))
        self.assertEqual(config['maturity_reminder_days'], [90, 60, 30, 7])
        self.assertEqual(config['_source'], 'built-in defaults')

    def test_ruleset_overrides_known_keys_and_ignores_unknown_ones(self):
        self.rule({'maturity_reminder_days': [45, 10], 'sla': {'submission_working_days': 3}, 'bogus': 1})
        config = load_config(date(2026, 10, 24))
        self.assertEqual(config['maturity_reminder_days'], [45, 10])
        self.assertEqual(config['sla']['submission_working_days'], 3)
        self.assertEqual(config['sla']['correction_days'], DEFAULTS['sla']['correction_days'])
        self.assertNotIn('bogus', config)
        self.assertEqual(config['_source'], 'escalation-matrix v1')

    def test_newest_effective_version_wins_and_expired_rules_are_ignored(self):
        self.rule({'penalty_review_after_days': 10}, version=1)
        self.rule({'penalty_review_after_days': 20}, version=2)
        self.rule({'penalty_review_after_days': 5}, version=3, effective_to=date(2026, 6, 1))
        self.assertEqual(load_config(date(2026, 10, 24))['penalty_review_after_days'], 20)

    def test_run_uses_configured_thresholds(self):
        fdr = self.instrument()
        self.rule({'maturity_reminder_days': [45, 10]})
        self.run_on(days_from_maturity(-45))
        self.assertEqual(self.keys('maturity_reminder'), [f'instrument:{fdr.pk}:maturity:T-45:{MATURITY}'])


class ProofDueTests(RulesTestCase):
    def setUp(self):
        self.intimation = date(2026, 11, 1)
        self.obligation = DepositObligation.objects.create(
            institution=self.institution, status='DUE', required_paise=1_000_000, intimation_date=self.intimation)

    def key(self, day):
        return f'obligation:{self.obligation.pk}:proof-due:day{day}:{self.intimation}'

    def test_reminders_at_days_7_12_and_15(self):
        for offset, expected in [(6, []), (7, [7]), (11, [7]), (12, [7, 12]), (14, [7, 12]), (15, [7, 12, 15]),
                                 (40, [7, 12, 15])]:
            with self.subTest(day=offset):
                self.run_on(self.intimation + timedelta(days=offset))
                self.assertEqual(self.keys('proof_due_reminder'), sorted(self.key(day) for day in expected))
        self.assertEqual(self.recipients(self.key(15)), {'inst_a'})
        self.assertIn('day 15 of 15', Notification.objects.get(idempotency_key=self.key(15), channel='IN_APP').subject)

    def test_settled_unknown_or_unannounced_obligations_are_ignored(self):
        for status in ('MET', 'RELEASED', 'EXTENDED', 'FORFEITED'):
            DepositObligation.objects.filter(pk=self.obligation.pk).update(status=status, required_paise=1)
            self.run_on(self.intimation + timedelta(days=20))
        DepositObligation.objects.filter(pk=self.obligation.pk).update(status='DUE', intimation_date=None)
        self.run_on(self.intimation + timedelta(days=20))
        self.assertEqual(Notification.objects.count(), 0)


class SlaTests(RulesTestCase):
    def submitted(self, on, reference='SUB-1'):
        fdr = self.instrument(status=Instrument.Status.SUBMITTED, reference=reference)
        event = AuditEvent.objects.create(instrument=fdr, actor=self.inst_user, action='SUBMITTED')
        AuditEvent.objects.filter(pk=event.pk).update(created_at=datetime(on.year, on.month, on.day, 6, tzinfo=dt_timezone.utc))
        return fdr

    def test_submission_waiting_over_seven_working_days_alerts_the_supervisor(self):
        monday = date(2026, 11, 2)
        fdr = self.submitted(monday)
        key = f'instrument:{fdr.pk}:sla-submission:{monday}'
        for as_of, breached in [(date(2026, 11, 10), False), (date(2026, 11, 11), False),  # 7 working days
                                (date(2026, 11, 12), True), (date(2026, 11, 20), True)]:
            with self.subTest(as_of=as_of):
                self.run_on(as_of)
                self.assertEqual(key in self.keys(), breached)
        self.assertEqual(self.recipients(key), {'authority'})
        self.assertEqual(Notification.objects.filter(idempotency_key=key, channel='IN_APP').count(), 1)

    def test_working_day_counting_skips_weekends_and_holidays(self):
        self.assertEqual(working_days_after(date(2026, 11, 6), date(2026, 11, 9)), 1)   # Fri -> Mon
        self.assertEqual(working_days_after(date(2026, 11, 6), date(2026, 11, 8)), 0)   # Fri -> Sun
        self.assertEqual(working_days_after(date(2026, 11, 2), date(2026, 11, 11)), 7)
        self.assertEqual(working_days_after(date(2026, 11, 2), date(2026, 11, 11), ['2026-11-04']), 6)
        self.assertEqual(working_days_after(date(2026, 11, 2), date(2026, 11, 2)), 0)

    def test_holidays_in_the_ruleset_delay_a_breach(self):
        RuleSet.objects.create(code='escalation-matrix', version=1, effective_from=date(2026, 1, 1),
                               payload={'holidays': ['2026-11-04', '2026-11-05']}, source_clause='t',
                               source_document='t')
        fdr = self.submitted(date(2026, 11, 2))
        self.run_on(date(2026, 11, 13))  # 7 working days once Wed 4 and Thu 5 Nov are holidays
        self.assertNotIn(f'instrument:{fdr.pk}:sla-submission:2026-11-02', self.keys())
        self.run_on(date(2026, 11, 16))
        self.assertIn(f'instrument:{fdr.pk}:sla-submission:2026-11-02', self.keys())

    def test_corrections_alert_the_institution_at_15_days_and_the_officer_at_30(self):
        fdr = self.instrument(status=Instrument.Status.CHANGES_REQUESTED, reference='CR')
        event = AuditEvent.objects.create(instrument=fdr, actor=self.officer, action='CHANGES_REQUESTED')
        AuditEvent.objects.filter(pk=event.pk).update(created_at=datetime(2026, 11, 2, 6, tzinfo=dt_timezone.utc))
        key = lambda limit: f'instrument:{fdr.pk}:sla-correction:{limit}:2026-11-02'  # noqa: E731
        self.run_on(date(2026, 11, 16))
        self.assertEqual(self.keys('sla_correction_pending'), [])
        self.run_on(date(2026, 11, 17))
        self.assertEqual(self.keys('sla_correction_pending'), [key(15)])
        self.assertEqual(self.recipients(key(15)), {'inst_a'})
        self.run_on(date(2026, 12, 2))
        self.assertEqual(self.recipients(key(30)), {'officer'})

    def test_clearance_tasks_alert_the_unit_then_the_head(self):
        task = {'id': 7, 'unit': 'PGRC', 'opened_on': date(2026, 11, 2), 'reference': 'FDR-1', 'case_id': 1}
        provider = lambda as_of: [task]  # noqa: E731
        key = lambda limit: f'clearance:7:sla:{limit}:2026-11-02'  # noqa: E731
        self.run_on(date(2026, 11, 11), clearance_provider=provider)   # 7 working days: not yet
        self.assertEqual(self.keys('sla_clearance_pending'), [])
        self.run_on(date(2026, 11, 12), clearance_provider=provider)
        self.assertEqual(self.recipients(key(7)), {'pgrc'})              # only the PGRC unit, not vigilance
        self.run_on(date(2026, 11, 20), clearance_provider=provider)     # 14 working days: the head
        self.run_on(date(2026, 11, 23), clearance_provider=provider)
        self.assertEqual(self.recipients(key(14)), {'authority'})

    def test_no_open_clearance_tasks_means_no_clearance_alerts(self):
        from notifications.rules import open_clearance_tasks
        self.assertEqual(open_clearance_tasks(date(2026, 11, 20)), [])


class CommandTests(RulesTestCase):
    def call(self, *args):
        out = StringIO()
        call_command('run_due_rules', *args, stdout=out)
        return out.getvalue()

    def test_scenario_4_reminder_at_t_minus_30(self):
        self.instrument()
        output = self.call('--as-of', '2026-11-01')
        self.assertIn('maturity-reminder: FDR-1 T-30 (30 days left)', output)
        self.assertIn('Queued 4 notification(s)', output)   # institution user + officer, in-app and email each
        self.assertEqual(Notification.objects.filter(channel='EMAIL').count(), 2)
        self.assertIn('already sent', self.call('--as-of', '2026-11-01'))
        self.assertEqual(Notification.objects.count(), 4)

    def test_dry_run_writes_nothing(self):
        self.instrument()
        output = self.call('--as-of', '2026-11-01', '--dry-run')
        self.assertIn('dry run', output)
        self.assertEqual(Notification.objects.count(), 0)

    def test_institution_filter_and_validation(self):
        self.instrument()
        self.instrument(institution=self.other, reference='FDR-B')
        self.call('--as-of', '2026-11-01', '--institution', 'B')
        self.assertEqual(self.keys('maturity_reminder'), [
            f'instrument:{Instrument.objects.get(reference="FDR-B").pk}:maturity:T-30:{MATURITY}'])
        with self.assertRaises(CommandError):
            self.call('--institution', 'NOPE')
        with self.assertRaises(CommandError):
            self.call('--as-of', '01-11-2026')

    def test_one_failing_rule_group_does_not_stop_the_others(self):
        self.instrument()
        err = StringIO()
        with mock.patch('notifications.rules.proof_rules', side_effect=RuntimeError('boom')):
            with self.assertRaises(CommandError):
                call_command('run_due_rules', '--as-of', '2026-11-01', stdout=StringIO(), stderr=err)
        self.assertIn('proof: RuntimeError: boom', err.getvalue())
        self.assertEqual(len(self.keys('maturity_reminder')), 1)  # maturity group still ran

    def test_only_option(self):
        self.instrument()
        self.call('--as-of', '2026-11-01', '--only', 'proof')
        self.assertEqual(Notification.objects.count(), 0)
