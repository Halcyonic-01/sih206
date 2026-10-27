from datetime import datetime, timedelta, timezone

from notifications.models import AlertAction, Notification
from notifications.rules import run_rules
from portal.models import Instrument

from .test_rules import MATURITY, RulesTestCase, days_from_maturity

OVERDUE = lambda: days_from_maturity(3)
SUPERSEDED = datetime(2026, 12, 4, tzinfo=timezone.utc)


class AlertLifecycleTests(RulesTestCase):
    def setUp(self):
        self.fdr = self.instrument()

    def alerts(self, **filters):
        return AlertAction.objects.filter(**filters)

    def test_an_overdue_renewal_opens_exactly_one_action_however_often_the_rules_run(self):
        for _ in range(3):
            run_rules(OVERDUE())
        alert = self.alerts(rule='renewal-overdue').get()
        self.assertEqual((alert.status, alert.instrument_id, alert.reference), ('OPEN', self.fdr.pk, 'FDR-1'))
        self.assertEqual(alert.opened_on, OVERDUE())
        self.assertEqual(alert.key, f'instrument:{self.fdr.pk}:renewal-overdue:{MATURITY}')

    def test_reminders_before_maturity_do_not_open_actions(self):
        run_rules(days_from_maturity(-20))
        self.assertFalse(AlertAction.objects.exists())

    def test_the_action_clears_itself_when_the_condition_ends(self):
        run_rules(OVERDUE())
        Instrument.objects.filter(pk=self.fdr.pk).update(superseded_at=SUPERSEDED)  # renewed: no longer current
        result = run_rules(OVERDUE())
        alert = self.alerts(rule='renewal-overdue').get()
        self.assertEqual(alert.status, 'RESOLVED')
        self.assertIn('Condition cleared', alert.resolved_reason)
        self.assertTrue(any('resolved because the condition cleared' in line for line in result.lines))

    def test_a_restricted_run_never_resolves_other_groups_or_institutions(self):
        run_rules(OVERDUE())
        run_rules(OVERDUE(), only=['proof'])                       # a different group: nothing to resolve here
        self.assertEqual(self.alerts(rule='renewal-overdue').get().status, 'OPEN')
        run_rules(OVERDUE(), dry_run=True)
        self.assertEqual(self.alerts(rule='renewal-overdue').get().status, 'OPEN')

    def test_a_failed_group_leaves_actions_alone(self):
        from unittest import mock
        run_rules(OVERDUE())
        with mock.patch('notifications.rules.maturity_rules', side_effect=RuntimeError('boom')):
            result = run_rules(OVERDUE(), only=['maturity'])
        self.assertTrue(result.errors)
        self.assertEqual(self.alerts(rule='renewal-overdue').get().status, 'OPEN')

    def test_a_resolved_action_reopens_when_the_same_condition_returns(self):
        run_rules(OVERDUE())
        Instrument.objects.filter(pk=self.fdr.pk).update(superseded_at=SUPERSEDED)
        run_rules(OVERDUE())
        Instrument.objects.filter(pk=self.fdr.pk).update(superseded_at=None)
        run_rules(OVERDUE() + timedelta(days=1))
        alert = self.alerts(rule='renewal-overdue').get()
        self.assertEqual((alert.status, alert.escalation_level, alert.note), ('OPEN', 0, ''))

    def test_an_unacknowledged_action_escalates_once_to_the_regional_head_and_authority(self):
        run_rules(OVERDUE())
        run_rules(OVERDUE() + timedelta(days=6))
        self.assertEqual(self.alerts().get().escalation_level, 0)
        result = run_rules(OVERDUE() + timedelta(days=7))
        self.assertEqual(self.alerts().get().escalation_level, 1)
        key = f'alert:{self.alerts().get().pk}:escalated:1'
        self.assertEqual(self.recipients(key), {'officer', 'authority'})
        run_rules(OVERDUE() + timedelta(days=30))
        self.assertEqual(Notification.objects.filter(idempotency_key=key, channel='IN_APP').count(), 2)  # once per person
        self.assertTrue(any('alert-escalation' in line for line in result.lines))

    def test_an_acknowledged_action_does_not_escalate(self):
        run_rules(OVERDUE())
        AlertAction.objects.update(status='ACKNOWLEDGED', acknowledged_by=self.officer)
        run_rules(OVERDUE() + timedelta(days=20))
        self.assertEqual(self.alerts().get().escalation_level, 0)

    def test_the_escalation_limit_comes_from_the_rule_set(self):
        from datetime import date
        from obligations.models import RuleSet
        RuleSet.objects.create(code='escalation-matrix', version=1, effective_from=date(2026, 1, 1), source_clause='draft',
                               source_document='synthetic', payload={'alert_escalation_days': 2})
        run_rules(OVERDUE())
        run_rules(OVERDUE() + timedelta(days=2))
        self.assertEqual(self.alerts().get().escalation_level, 1)


class AlertApiTests(RulesTestCase):
    def setUp(self):
        self.fdr = self.instrument()
        run_rules(OVERDUE())
        self.alert = AlertAction.objects.get(rule='renewal-overdue')

    def post(self, user, note='Calling the institution today.', alert=None):
        self.client.force_login(user)
        return self.client.post(f'/api/alerts/{(alert or self.alert).pk}/acknowledge/', {'note': note}, content_type='application/json')

    def test_an_officer_takes_charge_with_a_note(self):
        response = self.post(self.officer)
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual((body['status'], body['acknowledged_by'], body['note']), ('ACKNOWLEDGED', 'officer', 'Calling the institution today.'))
        self.assertFalse(body['can_acknowledge'])
        from access.models import AccessLog
        self.assertTrue(AccessLog.objects.filter(action='ALERT_ACKNOWLEDGED', user=self.officer).exists())

    def test_a_second_acknowledgement_is_a_conflict_and_a_note_is_required(self):
        self.assertEqual(self.post(self.officer, note='  ').status_code, 400)
        self.assertEqual(self.post(self.officer, note='x' * 1001).status_code, 400)
        self.assertEqual(self.post(self.officer).status_code, 200)
        self.assertEqual(self.post(self.authority).status_code, 409)

    def test_institutions_and_other_institutions_cannot_acknowledge(self):
        self.assertEqual(self.post(self.inst_user).status_code, 403)
        other = self.instrument(institution=self.other, reference='FDR-B')
        run_rules(OVERDUE())
        foreign = AlertAction.objects.get(instrument=other, rule='renewal-overdue')
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group
        from portal.models import UserProfile
        from portal.permissions import INSTITUTION_GROUP
        user_b = get_user_model().objects.create_user(username='inst_b', password='x')
        user_b.groups.add(Group.objects.get(name=INSTITUTION_GROUP))
        UserProfile.objects.create(user=user_b, institution=self.other)
        self.client.force_login(user_b)
        self.assertEqual(self.client.get('/api/alerts/').json()['results'][0]['reference'], 'FDR-B')
        self.assertEqual(len(self.client.get('/api/alerts/').json()['results']), 1)
        self.assertEqual(self.post(self.inst_user, alert=foreign).status_code, 403)

    def test_an_officer_outside_the_region_does_not_see_the_action(self):
        from access.models import RegionAssignment
        RegionAssignment.objects.create(user=self.officer, region='South')
        self.client.force_login(self.officer)
        results = self.client.get('/api/alerts/').json()['results']
        # No institution profile means no region: a regional officer sees nothing outside an assigned region.
        self.assertEqual([r for r in results if r['reference'] == 'FDR-1'], [])

    def test_the_dashboard_carries_the_open_actions(self):
        self.client.force_login(self.officer)
        body = self.client.get('/api/dashboard/').json()
        self.assertEqual([a['reference'] for a in body['alerts']], ['FDR-1'])
        self.assertTrue(body['alerts'][0]['can_acknowledge'])
