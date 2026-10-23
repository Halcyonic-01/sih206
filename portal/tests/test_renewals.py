from datetime import date
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, override_settings
from django.urls import reverse

from portal import services
from portal.deadlines import dashboard_counts, due_actions
from portal.models import Instrument, UserProfile
from portal.permissions import INSTITUTION_GROUP, OFFICER_GROUP
from .common import PortalTestCase


class RenewalTests(PortalTestCase):
    def accepted(self, owner=None, **overrides):
        owner = owner or self.a
        self.client.force_login(owner)
        response = self.client.post(reverse('instrument_create'), self.payload(document=self.pdf(), **overrides))
        self.assertEqual(response.status_code, 302)
        instrument = Instrument.objects.latest('pk')
        self.assertEqual(self.client.post(reverse('instrument_submit', args=[instrument.pk]),
                                         {'version': instrument.version}).status_code, 302)
        self.client.force_login(self.officer)
        self.assertEqual(self.decide(instrument).status_code, 302)
        instrument.refresh_from_db()
        return instrument

    def renewal_payload(self, parent, **overrides):
        parent.refresh_from_db()
        return self.payload(reference=f'SUCCESSOR-{parent.pk}', amount='600000.00',
                            issue_date='2026-10-23', maturity_date='2027-10-23',
                            predecessor_version=parent.version, **overrides)

    def renewal(self, parent, owner=None, with_document=True):
        self.client.force_login(owner or self.a)
        data = self.renewal_payload(parent)
        if with_document:
            data['document'] = self.pdf('renewal.pdf')
        response = self.client.post(reverse('instrument_renew', args=[parent.pk]), data)
        self.assertEqual(response.status_code, 302)
        return Instrument.objects.get(predecessor=parent)

    def submit_successor(self, successor):
        successor.refresh_from_db()
        self.client.force_login(self.a)
        response = self.client.post(reverse('instrument_submit', args=[successor.pk]),
                                    {'version': successor.version})
        self.assertEqual(response.status_code, 302)
        successor.refresh_from_db()

    def decide(self, instrument, decision='accept'):
        instrument.refresh_from_db()
        return self.client.post(reverse('instrument_review', args=[instrument.pk]), {
            'version': instrument.version, 'decision': decision, 'reason': 'Manually reviewed the renewal documents.',
        })

    def test_new_renewal_is_linked_draft_with_independent_document_and_amount(self):
        parent = self.accepted()
        original = services.snapshot(parent)
        original_document = parent.documents.get()
        child = self.renewal(parent)
        parent.refresh_from_db()
        self.assertEqual(child.predecessor, parent)
        self.assertEqual(child.institution, parent.institution)
        self.assertEqual(child.status, 'DRAFT')
        self.assertEqual(child.amount_paise, 60000000)
        self.assertTrue(parent.is_current)
        self.assertIsNone(parent.superseded_at)
        for key in ('reference', 'bank', 'amount_paise', 'issue_date', 'maturity_date', 'document_ids'):
            self.assertEqual(services.snapshot(parent)[key], original[key])
        self.assertNotEqual(child.documents.get().file.name, original_document.file.name)
        self.assertEqual(child.audit_events.get(action='DRAFT_CREATED').after['predecessor_id'], parent.pk)
        self.assertEqual(parent.audit_events.filter(action='RENEWAL_STARTED').count(), 1)

    def test_renewal_form_prefills_only_bank_amount_and_current_parent_version(self):
        parent = self.accepted()
        self.client.force_login(self.a)
        form = self.client.get(reverse('instrument_renew', args=[parent.pk])).context['form']
        self.assertEqual(form.initial['bank'], parent.bank)
        self.assertEqual(form.initial['amount'], parent.amount)
        self.assertEqual(form.initial['predecessor_version'], parent.version)
        self.assertFalse(form.initial.get('reference'))
        self.assertFalse(form.initial.get('issue_date'))
        self.assertFalse(form.initial.get('maturity_date'))

    def test_predecessor_stays_monitored_during_draft_submission_and_corrections(self):
        parent = self.accepted(maturity_date='2026-10-22')
        child = self.renewal(parent)
        for stage in ('draft', 'submitted', 'changes'):
            if stage == 'submitted':
                self.submit_successor(child)
            elif stage == 'changes':
                self.client.force_login(self.officer)
                self.assertEqual(self.decide(child, 'changes').status_code, 302)
            parent.refresh_from_db()
            self.assertTrue(parent.is_current)
            self.assertEqual([row['instrument'].pk for row in due_actions(Instrument.objects.all(), date(2026, 10, 23))],
                             [parent.pk])
        self.assertEqual(child.audit_events.filter(action='CHANGES_REQUESTED').count(), 1)

    def test_acceptance_supersedes_predecessor_atomically_and_preserves_history(self):
        parent = self.accepted()
        old_document = parent.documents.get()
        child = self.renewal(parent)
        self.submit_successor(child)
        self.client.force_login(self.officer)
        self.assertEqual(self.decide(child).status_code, 302)
        parent.refresh_from_db()
        child.refresh_from_db()
        self.assertTrue(parent.is_superseded)
        self.assertFalse(parent.is_current)
        self.assertEqual(parent.status, 'ACCEPTED')
        self.assertTrue(child.is_current)
        self.assertTrue(old_document.file.storage.exists(old_document.file.name))
        superseded = parent.audit_events.get(action='SUPERSEDED')
        self.assertEqual(superseded.actor, self.officer)
        self.assertEqual(superseded.after['accepted_successor_id'], child.pk)
        self.assertIsNone(superseded.before['superseded_at'])
        self.assertEqual(superseded.after['superseded_at'], parent.superseded_at.isoformat())
        self.assertEqual(child.audit_events.get(action='ACCEPTED').after['predecessor_id'], parent.pk)
        self.assertContains(self.client.get(reverse('instrument_detail', args=[parent.pk])), 'Superseded')

    def test_repeated_acceptance_does_not_repeat_supersession(self):
        parent = self.accepted()
        child = self.renewal(parent)
        self.submit_successor(child)
        self.client.force_login(self.officer)
        self.assertEqual(self.decide(child).status_code, 302)
        parent.refresh_from_db()
        original_version, original_time = parent.version, parent.superseded_at
        self.assertEqual(self.decide(child).status_code, 409)
        parent.refresh_from_db()
        self.assertEqual((parent.version, parent.superseded_at), (original_version, original_time))
        self.assertEqual(parent.audit_events.filter(action='SUPERSEDED').count(), 1)

    def test_creator_of_original_cannot_approve_colleagues_successor_after_role_change(self):
        parent = self.accepted()
        colleague = get_user_model().objects.create_user(username='colleague')
        colleague.groups.add(Group.objects.get(name=INSTITUTION_GROUP))
        UserProfile.objects.create(user=colleague, institution=self.institution_a)
        child = self.renewal(parent, owner=colleague)
        self.submit_successor(child)
        self.a.groups.clear()
        self.a.groups.add(Group.objects.get(name=OFFICER_GROUP))
        self.client.force_login(self.a)
        self.assertEqual(self.decide(child).status_code, 403)
        parent.refresh_from_db()
        self.assertTrue(parent.is_current)

    def test_acceptance_rechecks_predecessor_current_state(self):
        parent = self.accepted()
        child = self.renewal(parent)
        self.submit_successor(child)
        # Simulate an out-of-band administrative change to the old record.
        from django.utils import timezone
        Instrument.objects.filter(pk=parent.pk).update(superseded_at=timezone.now())
        self.client.force_login(self.officer)
        self.assertEqual(self.decide(child).status_code, 409)
        child.refresh_from_db()
        self.assertEqual(child.status, 'SUBMITTED')
        self.assertFalse(child.audit_events.filter(action='ACCEPTED').exists())

    def test_pending_private_successor_is_not_exposed_to_officer(self):
        parent = self.accepted()
        child = self.renewal(parent)
        self.client.force_login(self.officer)
        page = self.client.get(reverse('instrument_detail', args=[parent.pk]))
        self.assertIsNone(page.context['successor'])
        self.assertNotContains(page, child.reference)
        self.assertNotContains(page, f'href="/instruments/{child.pk}/"')
        self.assertEqual(self.client.get(reverse('instrument_detail', args=[child.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('document_download', args=[child.documents.get().pk])).status_code, 404)

    def test_bidirectional_links_visible_to_authorized_users_after_submission(self):
        parent = self.accepted()
        child = self.renewal(parent)
        self.submit_successor(child)
        for user in (self.a, self.officer):
            self.client.force_login(user)
            page = self.client.get(reverse('instrument_detail', args=[parent.pk]))
            self.assertEqual(page.context['successor'].pk, child.pk)
            self.assertContains(page, f'data-lineage="successor" href="/instruments/{child.pk}/"')
            page = self.client.get(reverse('instrument_detail', args=[child.pk]))
            self.assertEqual(page.context['predecessor'].pk, parent.pk)
            self.assertContains(page, f'data-lineage="predecessor" href="/instruments/{parent.pk}/"')

    def test_competing_proposal_and_replay_are_rejected(self):
        parent = self.accepted()
        child = self.renewal(parent)
        self.assertEqual(self.client.get(reverse('instrument_renew', args=[parent.pk])).status_code, 409)
        response = self.client.post(reverse('instrument_renew', args=[parent.pk]), self.renewal_payload(parent))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Instrument.objects.filter(predecessor=parent).count(), 1)
        self.assertEqual(parent.audit_events.filter(action='RENEWAL_STARTED').count(), 1)
        self.assertEqual(child.status, 'DRAFT')

    def test_stale_predecessor_version_rejected_without_child_or_file(self):
        parent = self.accepted()
        self.client.force_login(self.a)
        data = self.renewal_payload(parent)
        data['predecessor_version'] -= 1
        data['document'] = self.pdf('stale-renewal.pdf')
        files = set(Path(self.storage_dir).rglob('*.pdf'))
        response = self.client.post(reverse('instrument_renew', args=[parent.pk]), data)
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Instrument.objects.filter(predecessor=parent).exists())
        self.assertEqual(set(Path(self.storage_dir).rglob('*.pdf')), files)

    def test_only_accepted_current_instruments_can_start_renewal(self):
        parent = self.draft()
        self.assertEqual(self.client.get(reverse('instrument_renew', args=[parent.pk])).status_code, 409)
        self.client.post(reverse('instrument_submit', args=[parent.pk]), {'version': parent.version})
        self.assertEqual(self.client.get(reverse('instrument_renew', args=[parent.pk])).status_code, 409)
        parent = self.accepted(reference='CURRENT')
        child = self.renewal(parent)
        self.submit_successor(child)
        self.client.force_login(self.officer)
        self.decide(child)
        self.client.force_login(self.a)
        self.assertEqual(self.client.get(reverse('instrument_renew', args=[parent.pk])).status_code, 409)

    def test_cross_institution_and_officer_creation_are_forbidden(self):
        parent = self.accepted()
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(reverse('instrument_renew', args=[parent.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('instrument_renew', args=[parent.pk]),
                                         self.renewal_payload(parent)).status_code, 404)
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(reverse('instrument_renew', args=[parent.pk])).status_code, 403)

    def test_parent_institution_and_lifecycle_cannot_be_forged_in_renewal_form(self):
        parent = self.accepted()
        other = self.accepted(owner=self.b, reference='OTHER-PARENT')
        self.client.force_login(self.a)
        response = self.client.post(reverse('instrument_renew', args=[parent.pk]), self.renewal_payload(
            parent, predecessor=other.pk, predecessor_id=other.pk, institution=self.institution_b.pk,
            superseded_at='2026-10-23T00:00:00Z', status='ACCEPTED'))
        self.assertEqual(response.status_code, 302)
        child = Instrument.objects.get(predecessor=parent)
        self.assertEqual(child.institution, self.institution_a)
        self.assertEqual(child.status, 'DRAFT')
        self.assertIsNone(child.superseded_at)

    def test_edit_cannot_reparent_successor_and_original_documents_are_not_reused(self):
        parent = self.accepted()
        other = self.accepted(reference='OTHER-PARENT')
        child = self.renewal(parent, with_document=False)
        self.assertFalse(child.documents.exists())
        self.assertEqual(self.client.post(reverse('instrument_submit', args=[child.pk]),
                                         {'version': child.version}).status_code, 409)
        response = self.client.post(reverse('instrument_edit', args=[child.pk]), self.payload(
            reference=child.reference, amount='600000.00', version=child.version,
            document=self.pdf(), predecessor=other.pk, predecessor_id=other.pk))
        self.assertEqual(response.status_code, 302)
        child.refresh_from_db()
        self.assertEqual(child.predecessor_id, parent.pk)

    def test_blocking_scrutiny_on_successor_prevents_supersession(self):
        parent = self.accepted()
        child = self.renewal(parent)
        self.submit_successor(child)
        self.client.force_login(self.officer)
        self.client.post(reverse('observation_add', args=[child.pk]), {
            'version': child.version, 'document': child.documents.get().pk, 'page_number': 1,
            'severity': 'BLOCKING', 'comment': 'Recheck successor amount.',
        })
        self.assertEqual(self.decide(child).status_code, 409)
        parent.refresh_from_db()
        self.assertTrue(parent.is_current)

    def test_failed_acceptance_audit_rolls_back_both_instruments_and_events(self):
        parent = self.accepted()
        child = self.renewal(parent)
        self.submit_successor(child)
        parent.refresh_from_db()
        parent_version, child_version = parent.version, child.version
        parent_events, child_events = parent.audit_events.count(), child.audit_events.count()
        actual_event = services.event

        def fail_child_acceptance(*args, **kwargs):
            if args[2] == 'ACCEPTED':
                raise RuntimeError('simulated child audit failure after predecessor event')
            return actual_event(*args, **kwargs)

        self.client.force_login(self.officer)
        with patch('portal.services.event', side_effect=fail_child_acceptance):
            with self.assertRaises(RuntimeError):
                self.decide(child)
        parent.refresh_from_db()
        child.refresh_from_db()
        self.assertTrue(parent.is_current)
        self.assertEqual(parent.version, parent_version)
        self.assertEqual(child.status, 'SUBMITTED')
        self.assertEqual(child.version, child_version)
        self.assertEqual(parent.audit_events.count(), parent_events)
        self.assertEqual(child.audit_events.count(), child_events)

    def test_failed_creation_audit_rolls_back_parent_child_and_new_file(self):
        parent = self.accepted()
        original_version = parent.version
        self.client.force_login(self.a)
        files = set(Path(self.storage_dir).rglob('*.pdf'))
        actual_event = services.event

        def fail_parent_event(*args, **kwargs):
            if args[2] == 'RENEWAL_STARTED':
                raise RuntimeError('simulated parent audit failure')
            return actual_event(*args, **kwargs)

        with patch('portal.services.event', side_effect=fail_parent_event):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('instrument_renew', args=[parent.pk]),
                                 self.renewal_payload(parent, document=self.pdf()))
        parent.refresh_from_db()
        self.assertEqual(parent.version, original_version)
        self.assertFalse(Instrument.objects.filter(predecessor=parent).exists())
        self.assertEqual(set(Path(self.storage_dir).rglob('*.pdf')), files)

    def test_superseded_instrument_cannot_be_edited_submitted_or_renewed(self):
        parent = self.accepted()
        child = self.renewal(parent)
        self.submit_successor(child)
        self.client.force_login(self.officer)
        self.decide(child)
        parent.refresh_from_db()
        self.client.force_login(self.a)
        for route in ('instrument_edit', 'instrument_renew'):
            self.assertEqual(self.client.get(reverse(route, args=[parent.pk])).status_code, 409)
        self.assertEqual(self.client.post(reverse('instrument_submit', args=[parent.pk]),
                                         {'version': parent.version}).status_code, 409)

    def test_database_blocks_self_link_fork_and_superseding_draft(self):
        parent = self.accepted()
        child = self.renewal(parent)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Instrument.objects.filter(pk=parent.pk).update(predecessor_id=parent.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Instrument.objects.create(institution=parent.institution, created_by=self.a,
                reference='FORK', bank=parent.bank, amount_paise=1, issue_date=parent.issue_date,
                maturity_date=parent.maturity_date, predecessor=parent)
        from django.utils import timezone
        with self.assertRaises(IntegrityError), transaction.atomic():
            Instrument.objects.filter(pk=child.pk).update(superseded_at=timezone.now())

    def test_model_validation_rejects_cross_institution_links_cycles_and_reparenting(self):
        parent = self.accepted()
        other = self.accepted(owner=self.b, reference='OTHER')
        child = Instrument(institution=self.institution_a, created_by=self.a, predecessor=other,
                           reference='INVALID', bank='Bank', amount_paise=1,
                           issue_date=parent.issue_date, maturity_date=parent.maturity_date)
        with self.assertRaises(ValidationError):
            child.validate_lineage()
        parent.predecessor_id = parent.pk
        with self.assertRaises(ValidationError):
            parent.validate_lineage()
        parent.refresh_from_db()
        child = self.renewal(parent)
        child.predecessor = other
        with self.assertRaises(ValidationError):
            child.full_clean()
        # Deliberate direct-DB corruption in this isolated test: the app exposes no reparent route.
        Instrument.objects.filter(pk=parent.pk).update(predecessor=child)
        parent.refresh_from_db()
        with self.assertRaises(ValidationError):
            parent.validate_lineage()

    @override_settings(DEBUG=True)
    def test_current_dashboard_counts_once_and_report_excludes_superseded_predecessor(self):
        parent = self.accepted(maturity_date='2026-10-22')
        child = self.renewal(parent)
        self.client.post(reverse('instrument_edit', args=[child.pk]), self.payload(
            reference=child.reference, amount='600000.00', version=child.version,
            maturity_date='2026-10-30'))
        self.submit_successor(child)
        self.client.force_login(self.officer)
        self.assertEqual(self.decide(child).status_code, 302)
        counts = dashboard_counts(Instrument.objects.all(), date(2026, 10, 23))
        self.assertEqual(counts['all'], 2)
        self.assertEqual(counts['accepted'], 1)
        self.assertEqual(counts['matured'], 0)
        self.assertEqual(counts['approaching'], 1)
        output = StringIO()
        call_command('due_actions', as_of='2026-10-23', stdout=output)
        self.assertNotIn(parent.reference + '\t', output.getvalue())
        self.assertIn(child.reference + '\t', output.getvalue())
        for category, count in [('all', 2), ('accepted', 1), ('approaching', 1), ('matured', 0)]:
            page = self.client.get(reverse('instrument_list'), {'category': category, 'as_of': '2026-10-23'})
            self.assertEqual(page.context['record_count'], count)

    def test_linear_chain_can_renew_the_current_successor(self):
        parent = self.accepted()
        child = self.renewal(parent)
        self.submit_successor(child)
        self.client.force_login(self.officer)
        self.decide(child)
        grandchild = self.renewal(child)
        self.submit_successor(grandchild)
        self.client.force_login(self.officer)
        self.assertEqual(self.decide(grandchild).status_code, 302)
        for instrument in (parent, child):
            instrument.refresh_from_db()
            self.assertTrue(instrument.is_superseded)
        grandchild.refresh_from_db()
        self.assertTrue(grandchild.is_current)
        self.assertEqual(grandchild.predecessor_id, child.pk)
        self.assertEqual(child.predecessor_id, parent.pk)

    def test_creation_requires_login_csrf_and_valid_input(self):
        parent = self.accepted()
        url = reverse('instrument_renew', args=[parent.pk])
        self.client.logout()
        self.assertEqual(self.client.post(url, {}).status_code, 302)
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.a)
        self.assertEqual(browser.post(url, self.renewal_payload(parent)).status_code, 403)
        self.client.force_login(self.a)
        invalid = self.renewal_payload(parent)
        invalid['amount'] = '-1'
        page = self.client.post(url, invalid)
        self.assertEqual(page.status_code, 200)
        self.assertIn('amount', page.context['form'].errors)
        self.assertFalse(Instrument.objects.filter(predecessor=parent).exists())
