from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse

from portal.models import AuditEvent, Instrument, ReviewObservation
from portal.permissions import OFFICER_GROUP
from .common import PortalTestCase


class ObservationTests(PortalTestCase):
    def observation_payload(self, record, **overrides):
        record.refresh_from_db()
        data = {'version': record.version, 'document': record.documents.first().pk,
                'page_number': 1, 'severity': 'BLOCKING',
                'comment': 'Amount mismatch: declared INR 500000.25; document page 1 reads INR 600000.00.'}
        data.update(overrides)
        return data

    def add(self, record, **overrides):
        self.client.force_login(self.officer)
        response = self.client.post(reverse('observation_add', args=[record.pk]),
                                    self.observation_payload(record, **overrides))
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        return record.observations.latest('pk')

    def resolve(self, record, observation, **overrides):
        record.refresh_from_db()
        data = {'version': record.version, 'resolution': 'Checked page 1 against the corrected declaration.'}
        data.update(overrides)
        return self.client.post(reverse('observation_resolve', args=[record.pk, observation.pk]), data)

    def decide(self, record, decision='accept'):
        record.refresh_from_db()
        return self.client.post(reverse('instrument_review', args=[record.pk]), {
            'version': record.version, 'decision': decision, 'reason': 'Compared the document and declaration.',
        })

    def test_officer_records_document_page_values_and_audit(self):
        record = self.submitted()
        observation = self.add(record, reviewer=self.a.pk, instrument=999999, resolved_by=self.a.pk)
        self.assertEqual(observation.reviewer, self.officer)
        self.assertEqual(observation.document.instrument, record)
        self.assertEqual(observation.page_number, 1)
        self.assertFalse(observation.is_resolved)
        self.assertEqual(record.version, 3)
        audit = record.audit_events.get(action='OBSERVATION_ADDED')
        self.assertEqual(audit.before['observations'], [])
        self.assertEqual(audit.after['observations'][0]['comment'], observation.comment)
        self.assertEqual(audit.after['observations'][0]['document_id'], observation.document_id)
        self.assertEqual(audit.after['observations'][0]['page_number'], 1)
        self.assertEqual(audit.actor, self.officer)
        self.assertIsNotNone(observation.created_at)
        self.client.force_login(self.a)
        page = self.client.get(reverse('instrument_detail', args=[record.pk]))
        self.assertContains(page, observation.comment)
        self.assertContains(page, 'Page 1')
        self.assertContains(page, 'blocks acceptance')
        self.assertNotContains(page, 'Record observation</button>')

    def test_unresolved_blocking_observation_blocks_acceptance_without_state_or_audit_change(self):
        record = self.submitted()
        self.add(record)
        version, events = record.version, record.audit_events.count()
        response = self.decide(record)
        self.assertContains(response, 'Resolve all blocking observations', status_code=409)
        record.refresh_from_db()
        self.assertEqual(record.status, Instrument.Status.SUBMITTED)
        self.assertEqual(record.version, version)
        self.assertEqual(record.audit_events.count(), events)

    def test_correction_resubmission_does_not_erase_or_auto_resolve_finding(self):
        record = self.submitted()
        observation = self.add(record)
        original_document = observation.document
        self.assertEqual(self.decide(record, 'changes').status_code, 302)
        record.refresh_from_db()
        self.client.force_login(self.a)
        self.assertEqual(self.client.post(reverse('instrument_edit', args=[record.pk]), self.payload(
            amount='600000.00', document=self.pdf('corrected.pdf'), version=record.version)).status_code, 302)
        record.refresh_from_db()
        self.assertEqual(self.client.post(reverse('instrument_submit', args=[record.pk]),
                                         {'version': record.version}).status_code, 302)
        self.client.force_login(self.officer)
        self.assertEqual(self.decide(record).status_code, 409)
        observation.refresh_from_db()
        self.assertFalse(observation.is_resolved)
        self.assertEqual(observation.document, original_document)
        self.assertEqual(record.documents.count(), 2)
        original_comment = observation.comment
        self.assertEqual(self.resolve(record, observation).status_code, 302)
        observation.refresh_from_db()
        self.assertEqual(observation.comment, original_comment)
        self.assertEqual(observation.resolved_by, self.officer)
        self.assertIsNotNone(observation.resolved_at)
        self.assertEqual(self.decide(record).status_code, 302)
        self.client.force_login(self.a)
        page = self.client.get(reverse('instrument_detail', args=[record.pk]))
        self.assertContains(page, original_comment)
        self.assertContains(page, observation.resolution)
        self.assertContains(page, 'Not independently bank-verified')
        audit = record.audit_events.get(action='OBSERVATION_RESOLVED')
        self.assertEqual(audit.before['observations'][0]['resolution'], '')
        self.assertEqual(audit.after['observations'][0]['resolution'], observation.resolution)
        self.assertEqual(audit.after['observations'][0]['resolved_by_id'], self.officer.pk)

    def test_warning_can_be_accepted_without_resolution_and_page_is_optional(self):
        record = self.submitted()
        observation = self.add(record, severity='WARNING', page_number='')
        self.assertIsNone(observation.page_number)
        self.assertEqual(self.decide(record).status_code, 302)
        observation.refresh_from_db()
        self.assertFalse(observation.is_resolved)

    def test_all_blocking_observations_must_be_resolved(self):
        record = self.submitted()
        first = self.add(record)
        second = self.add(record, comment='Check the issuing branch.')
        self.assertEqual(self.resolve(record, first).status_code, 302)
        self.assertEqual(self.decide(record).status_code, 409)
        self.assertEqual(self.resolve(record, second).status_code, 302)
        self.assertEqual(self.decide(record).status_code, 302)

    def test_blank_comments_invalid_pages_and_unknown_severity_rejected(self):
        record = self.submitted()
        self.client.force_login(self.officer)
        for overrides in ({'comment': '  '}, {'page_number': 0}, {'page_number': -1},
                          {'page_number': 'one'}, {'severity': 'CONFIRMED'}, {'comment': 'a' * 2001}):
            with self.subTest(overrides=overrides):
                response = self.client.post(reverse('observation_add', args=[record.pk]),
                                            self.observation_payload(record, **overrides))
                self.assertEqual(response.status_code, 400)
        self.assertFalse(ReviewObservation.objects.exists())
        self.assertEqual(record.audit_events.count(), 2)

    def test_document_choices_are_scoped_and_forged_document_reference_rejected(self):
        self.institution_b.name = 'Private Other Institute'
        self.institution_b.save(update_fields=['name'])
        record = self.submitted()
        other = self.draft(user=self.b)
        other_document = other.documents.get()
        self.client.force_login(self.officer)
        page = self.client.get(reverse('instrument_detail', args=[record.pk]))
        self.assertEqual(list(page.context['observation_form'].fields['document'].queryset),
                         list(record.documents.all()))
        response = self.client.post(reverse('observation_add', args=[record.pk]),
                                    self.observation_payload(record, document=other_document.pk))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ReviewObservation.objects.exists())
        self.assertNotContains(response, self.institution_b.name, status_code=400)

    def test_institution_cannot_add_resolve_or_read_another_institutions_observation(self):
        record = self.submitted()
        observation = self.add(record)
        for user in (self.a, self.b):
            self.client.force_login(user)
            self.assertEqual(self.client.post(reverse('observation_add', args=[record.pk]),
                                             self.observation_payload(record)).status_code, 403)
            self.assertEqual(self.resolve(record, observation).status_code, 403)
        self.assertEqual(self.client.get(reverse('instrument_detail', args=[record.pk])).status_code, 404)

    def test_cross_instrument_observation_cannot_be_resolved(self):
        record = self.submitted()
        other = self.submitted()
        observation = self.add(other)
        response = self.client.post(reverse('observation_resolve', args=[record.pk, observation.pk]),
                                    {'version': record.version, 'resolution': 'Forged target.'})
        self.assertEqual(response.status_code, 404)
        observation.refresh_from_db()
        self.assertFalse(observation.is_resolved)

    def test_resolution_requires_explanation_and_cannot_be_rewritten(self):
        record = self.submitted()
        observation = self.add(record)
        self.assertEqual(self.resolve(record, observation, resolution='  ').status_code, 400)
        self.assertEqual(self.resolve(record, observation).status_code, 302)
        observation.refresh_from_db()
        original = observation.resolution
        self.assertEqual(self.resolve(record, observation, resolution='Overwrite history.').status_code, 409)
        observation.refresh_from_db()
        self.assertEqual(observation.resolution, original)
        self.assertEqual(record.audit_events.filter(action='OBSERVATION_RESOLVED').count(), 1)

    def test_stale_observation_add_resolution_and_acceptance_fail(self):
        record = self.submitted()
        previous_version = record.version
        observation = self.add(record)
        response = self.client.post(reverse('observation_add', args=[record.pk]),
                                    self.observation_payload(record, version=previous_version))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.resolve(record, observation, version=previous_version).status_code, 409)
        current_version = record.version
        self.assertEqual(self.resolve(record, observation).status_code, 302)
        response = self.client.post(reverse('instrument_review', args=[record.pk]), {
            'version': current_version, 'decision': 'accept', 'reason': 'Stale screen.',
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(record.observations.count(), 1)

    def test_observation_mutations_require_submitted_state(self):
        record = self.submitted()
        observation = self.add(record)
        self.assertEqual(self.decide(record, 'changes').status_code, 302)
        self.assertEqual(self.resolve(record, observation).status_code, 409)
        self.assertEqual(self.client.post(reverse('observation_add', args=[record.pk]),
                                         self.observation_payload(record)).status_code, 409)

    def test_accepted_record_observations_are_locked(self):
        record = self.submitted()
        observation = self.add(record, severity='WARNING')
        self.assertEqual(self.decide(record).status_code, 302)
        self.assertEqual(self.resolve(record, observation).status_code, 409)
        self.assertEqual(self.client.post(reverse('observation_add', args=[record.pk]),
                                         self.observation_payload(record)).status_code, 409)

    def test_self_scrutiny_is_denied_after_role_change(self):
        record = self.submitted()
        self.a.groups.clear()
        self.a.groups.add(Group.objects.get(name=OFFICER_GROUP))
        self.client.force_login(self.a)
        response = self.client.post(reverse('observation_add', args=[record.pk]), self.observation_payload(record))
        self.assertEqual(response.status_code, 403)

    def test_post_authentication_and_csrf_enforced_on_both_actions(self):
        record = self.submitted()
        observation = self.add(record)
        paths = [reverse('observation_add', args=[record.pk]),
                 reverse('observation_resolve', args=[record.pk, observation.pk])]
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 405)
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.officer)
        for path in paths:
            self.assertEqual(browser.post(path, {}).status_code, 403)
        self.client.logout()
        for path in paths:
            self.assertEqual(self.client.post(path, {}).status_code, 302)

    def test_observation_and_resolution_roll_back_with_failed_audit(self):
        record = self.submitted()
        self.client.force_login(self.officer)
        with patch('portal.services.event', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('observation_add', args=[record.pk]), self.observation_payload(record))
        self.assertFalse(ReviewObservation.objects.exists())
        record.refresh_from_db()
        self.assertEqual(record.version, 2)
        observation = self.add(record)
        before = record.version
        with patch('portal.services.event', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.resolve(record, observation)
        observation.refresh_from_db()
        record.refresh_from_db()
        self.assertFalse(observation.is_resolved)
        self.assertEqual(record.version, before)
        self.assertFalse(AuditEvent.objects.filter(action='OBSERVATION_RESOLVED').exists())

    def test_model_rejects_cross_instrument_evidence_and_database_rejects_page_zero(self):
        record = self.submitted()
        other = self.draft(user=self.b)
        observation = ReviewObservation(instrument=record, document=other.documents.get(),
                                         reviewer=self.officer, severity='BLOCKING', comment='Check evidence.')
        with self.assertRaises(ValidationError):
            observation.full_clean()
        observation.document = record.documents.get()
        observation.page_number = 0
        with self.assertRaises(IntegrityError), transaction.atomic():
            observation.save()

    def test_html_in_observation_is_escaped(self):
        record = self.submitted()
        self.add(record, comment='<script>alert("unsafe")</script>')
        self.client.force_login(self.a)
        page = self.client.get(reverse('instrument_detail', args=[record.pk]))
        self.assertContains(page, '&lt;script&gt;')
        self.assertNotContains(page, '<script>alert(')
