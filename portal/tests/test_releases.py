from datetime import date
import hashlib
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from portal import releases, services
from portal.forms import RenewalForm
from portal.deadlines import dashboard_counts
from portal.models import Document, Instrument, ReleaseRequest
from portal.permissions import AUTHORITY_GROUP, OFFICER_GROUP, role
from .common import PortalTestCase
from .pdf_fixture import sample_pdf


class ReleaseTests(PortalTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.authority = get_user_model().objects.create_user(username='authority')
        group, _ = Group.objects.get_or_create(name=AUTHORITY_GROUP)
        cls.authority.groups.add(group)

    def accepted(self, owner=None, **overrides):
        owner = owner or self.a
        self.client.force_login(owner)
        self.assertEqual(self.client.post(reverse('instrument_create'),
            self.payload(document=self.pdf(), **overrides)).status_code, 302)
        instrument = Instrument.objects.latest('pk')
        self.client.post(reverse('instrument_submit', args=[instrument.pk]), {'version': instrument.version})
        instrument.refresh_from_db()
        self.client.force_login(self.officer)
        self.assertEqual(self.client.post(reverse('instrument_review', args=[instrument.pk]), {
            'version': instrument.version, 'decision': 'accept', 'reason': 'Manually reviewed synthetic FDR.',
        }).status_code, 302)
        instrument.refresh_from_db()
        return instrument

    def request(self, instrument, owner=None):
        self.client.force_login(owner or self.a)
        instrument.refresh_from_db()
        self.assertEqual(self.client.post(reverse('release_request', args=[instrument.pk]), {
            'version': instrument.version, 'reason': 'Please assess this synthetic release request.',
            'status': 'APPROVED', 'requested_by': self.authority.pk,
        }).status_code, 302)
        instrument.refresh_from_db()
        return instrument.release_requests.latest('pk')

    def decision(self, instrument, release, user=None, **changes):
        self.client.force_login(user or self.authority)
        instrument.refresh_from_db()
        data = {'version': instrument.version, 'decision': 'approve', 'reason': 'Authorized after human assessment.'}
        data.update(changes)
        return self.client.post(reverse('release_decision', args=[instrument.pk, release.pk]), data)

    def completion(self, instrument, release, user=None, with_document=True, **changes):
        self.client.force_login(user or self.authority)
        instrument.refresh_from_db()
        data = {'version': instrument.version, 'notes': 'Manually checked the attached synthetic discharge evidence.'}
        if with_document:
            data['document'] = self.pdf('completion-evidence.pdf')
        data.update(changes)
        return self.client.post(reverse('release_completion', args=[instrument.pk, release.pk]), data)

    def approved(self, instrument):
        release = self.request(instrument)
        self.assertEqual(self.decision(instrument, release).status_code, 302)
        release.refresh_from_db()
        return release

    def test_request_is_pending_with_server_set_actor_and_audit(self):
        instrument = self.accepted()
        release = self.request(instrument)
        self.assertEqual(release.status, 'PENDING')
        self.assertEqual(release.requested_by, self.a)
        self.assertTrue(instrument.is_current)
        self.assertIsNone(instrument.released_at)
        audit = instrument.audit_events.get(action='RELEASE_REQUESTED')
        self.assertEqual(audit.actor, self.a)
        self.assertEqual(audit.before['release_requests'], [])
        self.assertEqual(audit.after['release_requests'][0]['status'], 'PENDING')

    def test_approval_is_authorization_only_and_keeps_maturity_monitoring(self):
        instrument = self.accepted(maturity_date='2026-10-22')
        release = self.approved(instrument)
        self.assertEqual(release.status, 'APPROVED')
        self.assertEqual(release.decided_by, self.authority)
        self.assertIsNotNone(release.decided_at)
        self.assertIsNone(release.completed_at)
        instrument.refresh_from_db()
        self.assertTrue(instrument.is_current)
        self.assertIsNone(instrument.released_at)
        self.assertEqual(dashboard_counts(Instrument.objects.all(), date(2026, 10, 23))['matured'], 1)
        output = StringIO()
        call_command('due_actions', as_of='2026-10-23', stdout=output)
        self.assertIn(instrument.reference + '\t', output.getvalue())
        self.assertContains(self.client.get(reverse('instrument_detail', args=[instrument.pk])),
                            'Release authorized; completion pending.')

    def test_completion_requires_new_pdf_and_preserves_original_document_and_decision(self):
        instrument = self.accepted()
        original = instrument.documents.get()
        release = self.approved(instrument)
        decision_time, decision_reason = release.decided_at, release.decision_reason
        self.assertEqual(self.completion(instrument, release).status_code, 302)
        instrument.refresh_from_db()
        release.refresh_from_db()
        self.assertTrue(instrument.is_released)
        self.assertFalse(instrument.is_current)
        self.assertEqual(instrument.status, 'ACCEPTED')
        self.assertEqual(release.status, 'COMPLETED')
        self.assertEqual(release.completed_at, instrument.released_at)
        self.assertEqual(release.completed_by, self.authority)
        self.assertEqual((release.decided_at, release.decision_reason), (decision_time, decision_reason))
        evidence = release.completion_evidence
        self.assertEqual(evidence.kind, Document.Kind.RELEASE_EVIDENCE)
        self.assertEqual(evidence.instrument, instrument)
        self.assertEqual(evidence.uploaded_by, self.authority)
        self.assertEqual(evidence.sha256, hashlib.sha256(sample_pdf()).hexdigest())
        self.assertNotEqual(evidence.file.name, original.file.name)
        self.assertTrue(original.file.storage.exists(original.file.name))
        self.assertEqual(instrument.documents.count(), 2)
        audit = instrument.audit_events.get(action='RELEASE_COMPLETED')
        self.assertEqual(audit.before['release_requests'][0]['status'], 'APPROVED')
        self.assertEqual(audit.after['release_requests'][0]['completion_evidence_id'], evidence.pk)
        self.assertEqual(audit.after['released_at'], instrument.released_at.isoformat())

    def test_rejection_keeps_current_record_and_allows_a_new_separate_request(self):
        instrument = self.accepted()
        release = self.request(instrument)
        self.assertEqual(self.decision(instrument, release, decision='reject', reason='Required evidence is missing.').status_code, 302)
        release.refresh_from_db()
        instrument.refresh_from_db()
        self.assertEqual(release.status, 'REJECTED')
        self.assertTrue(instrument.is_current)
        self.assertEqual(self.completion(instrument, release).status_code, 409)
        new = self.request(instrument)
        self.assertNotEqual(new.pk, release.pk)
        self.assertEqual(instrument.release_requests.count(), 2)
        release.refresh_from_db()
        self.assertEqual(release.decision_reason, 'Required evidence is missing.')

    def test_only_one_open_request_and_database_guard(self):
        instrument = self.accepted()
        release = self.request(instrument)
        self.client.force_login(self.a)
        response = self.client.post(reverse('release_request', args=[instrument.pk]), {
            'version': instrument.version, 'reason': 'Duplicate.',
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(instrument.release_requests.count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReleaseRequest.objects.create(instrument=instrument, requested_by=self.a, reason='Duplicate direct DB row.')
        self.decision(instrument, release)
        self.client.force_login(self.a)
        instrument.refresh_from_db()
        self.assertEqual(self.client.post(reverse('release_request', args=[instrument.pk]), {
            'version': instrument.version, 'reason': 'Second open request.',
        }).status_code, 409)

    def test_request_needs_reason_and_current_accepted_instrument(self):
        instrument = self.draft()
        self.assertEqual(self.client.post(reverse('release_request', args=[instrument.pk]), {
            'version': instrument.version, 'reason': 'Not accepted.',
        }).status_code, 409)
        instrument = self.accepted(reference='ACCEPTED')
        self.client.force_login(self.a)
        for reason in (' ', 'x' * 2001):
            self.assertEqual(self.client.post(reverse('release_request', args=[instrument.pk]), {
                'version': instrument.version, 'reason': reason,
            }).status_code, 400)
        self.assertFalse(ReleaseRequest.objects.exists())

    def test_institution_and_officer_cannot_decide_or_complete(self):
        instrument = self.accepted()
        release = self.request(instrument)
        for user in (self.a, self.b, self.officer):
            self.assertEqual(self.decision(instrument, release, user=user).status_code, 403)
            self.assertEqual(self.completion(instrument, release, user=user).status_code, 403)

    def test_authority_cannot_submit_requests_or_perform_officer_review(self):
        instrument = self.accepted()
        self.client.force_login(self.authority)
        self.assertEqual(self.client.post(reverse('release_request', args=[instrument.pk]), {
            'version': instrument.version, 'reason': 'Authority request.',
        }).status_code, 403)
        self.assertEqual(self.client.post(reverse('instrument_review', args=[instrument.pk]), {}).status_code, 403)
        self.assertEqual(self.client.get(reverse('instrument_create')).status_code, 403)

    def test_self_decision_and_completion_denied_after_role_change(self):
        instrument = self.accepted()
        release = self.request(instrument)
        self.a.groups.clear()
        self.a.groups.add(Group.objects.get(name=AUTHORITY_GROUP))
        self.assertEqual(self.decision(instrument, release, user=self.a).status_code, 403)
        self.assertEqual(self.decision(instrument, release).status_code, 302)
        self.assertEqual(self.completion(instrument, release, user=self.a).status_code, 403)
        instrument.refresh_from_db()
        self.assertFalse(instrument.is_released)

    def test_authority_role_fails_closed_when_mixed_and_cannot_read_private_drafts(self):
        instrument = self.draft()
        self.client.force_login(self.authority)
        self.assertEqual(self.client.get(reverse('instrument_detail', args=[instrument.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('document_download', args=[instrument.documents.get().pk])).status_code, 404)
        self.authority.groups.add(Group.objects.get(name=OFFICER_GROUP))
        self.assertIsNone(role(self.authority))
        self.assertEqual(self.client.get(reverse('release_queue')).status_code, 403)

    def test_institution_scope_and_forged_request_parent_are_enforced(self):
        instrument = self.accepted()
        release = self.request(instrument)
        other = self.accepted(owner=self.b, reference='PRIVATE-OTHER')
        other_release = self.request(other, owner=self.b)
        self.client.force_login(self.b)
        self.assertEqual(self.client.post(reverse('release_request', args=[instrument.pk]), {
            'version': instrument.version, 'reason': 'Foreign institution.',
        }).status_code, 404)
        self.assertNotContains(self.client.get(reverse('release_queue')), instrument.reference)
        self.client.force_login(self.authority)
        self.assertEqual(self.client.post(reverse('release_decision', args=[instrument.pk, other_release.pk]), {
            'version': instrument.version, 'decision': 'approve', 'reason': 'Wrong parent.',
        }).status_code, 404)
        self.assertEqual(self.client.post(reverse('release_completion', args=[other.pk, release.pk]), {}).status_code, 404)

    def test_decisions_need_reason_and_cannot_be_replayed_or_overwritten(self):
        instrument = self.accepted()
        release = self.request(instrument)
        for reason in ('', ' ', 'x' * 2001):
            self.assertEqual(self.decision(instrument, release, reason=reason).status_code, 400)
        self.assertEqual(self.decision(instrument, release).status_code, 302)
        release.refresh_from_db()
        before = release.decided_at
        self.assertEqual(self.decision(instrument, release, decision='reject', reason='Overwrite.').status_code, 409)
        release.refresh_from_db()
        self.assertEqual(release.decided_at, before)
        self.assertEqual(release.status, 'APPROVED')
        self.assertEqual(instrument.audit_events.filter(action='RELEASE_APPROVED').count(), 1)

    def test_pending_or_rejected_requests_cannot_be_completed(self):
        instrument = self.accepted()
        release = self.request(instrument)
        self.assertEqual(self.completion(instrument, release).status_code, 409)
        self.assertEqual(self.decision(instrument, release, decision='reject').status_code, 302)
        self.assertEqual(self.completion(instrument, release).status_code, 409)

    def test_completion_requires_notes_and_file_and_rejects_invalid_pdf(self):
        instrument = self.accepted()
        release = self.approved(instrument)
        self.assertEqual(self.completion(instrument, release, with_document=False).status_code, 400)
        self.assertEqual(self.completion(instrument, release, notes=' ').status_code, 400)
        from django.core.files.uploadedfile import SimpleUploadedFile
        invalid = SimpleUploadedFile('fake.pdf', b'not a PDF', content_type='application/pdf')
        self.assertEqual(self.completion(instrument, release, document=invalid).status_code, 400)
        with override_settings(MAX_UPLOAD_BYTES=20):
            self.assertEqual(self.completion(instrument, release).status_code, 400)
        self.assertEqual(instrument.documents.count(), 1)
        instrument.refresh_from_db()
        self.assertIsNone(instrument.released_at)

    def test_existing_or_foreign_document_id_cannot_replace_new_evidence_upload(self):
        instrument = self.accepted()
        other = self.accepted(owner=self.b, reference='OTHER')
        release = self.approved(instrument)
        self.assertEqual(self.completion(instrument, release, with_document=False,
                                        completion_evidence=other.documents.get().pk).status_code, 400)
        self.assertEqual(self.completion(instrument, release, completion_evidence=other.documents.get().pk,
                                        completed_by=self.a.pk, released_at='2000-01-01').status_code, 302)
        release.refresh_from_db()
        self.assertEqual(release.completed_by, self.authority)
        self.assertEqual(release.completion_evidence.instrument, instrument)
        self.assertNotEqual(release.completion_evidence_id, other.documents.get().pk)

    def test_evidence_download_is_protected_and_returns_original_bytes(self):
        instrument = self.accepted()
        release = self.approved(instrument)
        self.completion(instrument, release)
        release.refresh_from_db()
        path = reverse('document_download', args=[release.completion_evidence_id])
        for user in (self.a, self.officer, self.authority):
            self.client.force_login(user)
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), sample_pdf())
            self.assertIn('no-store', response['Cache-Control'])
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(path).status_code, 302)

    def test_completed_release_leaves_current_monitoring_but_keeps_history(self):
        instrument = self.accepted(maturity_date='2026-10-22')
        release = self.approved(instrument)
        self.completion(instrument, release)
        counts = dashboard_counts(Instrument.objects.all(), date(2026, 10, 23))
        self.assertEqual((counts['all'], counts['accepted'], counts['matured']), (1, 0, 0))
        output = StringIO()
        call_command('due_actions', as_of='2026-10-23', stdout=output)
        self.assertNotIn(instrument.reference + '\t', output.getvalue())
        self.client.force_login(self.a)
        page = self.client.get(reverse('instrument_detail', args=[instrument.pk]))
        self.assertContains(page, 'Release completion recorded')
        self.assertContains(page, 'Not independently bank-verified')
        self.assertContains(page, 'RELEASE_APPROVED')
        self.assertContains(page, 'RELEASE_COMPLETED')
        self.assertContains(self.client.get(reverse('instrument_list')), instrument.reference)

    def test_completed_release_cannot_be_replayed_requested_or_renewed(self):
        instrument = self.accepted()
        release = self.approved(instrument)
        self.completion(instrument, release)
        instrument.refresh_from_db()
        original_time, original_version = instrument.released_at, instrument.version
        self.assertEqual(self.completion(instrument, release).status_code, 409)
        instrument.refresh_from_db()
        self.assertEqual((instrument.released_at, instrument.version), (original_time, original_version))
        self.assertEqual(instrument.audit_events.filter(action='RELEASE_COMPLETED').count(), 1)
        self.client.force_login(self.a)
        self.assertEqual(self.client.post(reverse('release_request', args=[instrument.pk]), {
            'version': instrument.version, 'reason': 'Already completed.',
        }).status_code, 409)
        self.assertEqual(self.client.get(reverse('instrument_renew', args=[instrument.pk])).status_code, 409)

    def test_pending_and_authorized_release_block_renewal_in_view_and_service(self):
        instrument = self.accepted()
        release = self.request(instrument)
        for status in ('PENDING', 'APPROVED'):
            if status == 'APPROVED':
                self.decision(instrument, release)
            self.client.force_login(self.a)
            self.assertEqual(self.client.get(reverse('instrument_renew', args=[instrument.pk])).status_code, 409)
            self.assertEqual(self.client.post(reverse('instrument_renew', args=[instrument.pk]),
                                             self.payload(predecessor_version=instrument.version)).status_code, 409)
        self.assertFalse(Instrument.objects.filter(predecessor=instrument).exists())

    def test_renewal_service_rechecks_release_even_if_view_was_already_open(self):
        instrument = self.accepted()
        self.request(instrument)
        form = RenewalForm(self.payload(predecessor_version=instrument.version))
        self.assertTrue(form.is_valid(), form.errors)
        with self.assertRaisesMessage(services.WorkflowError, 'release blocks this renewal'):
            services.save_draft(self.a, form.cleaned_data, predecessor_id=instrument.pk)
        self.assertFalse(Instrument.objects.filter(predecessor=instrument).exists())

    def test_successor_acceptance_rechecks_conflicting_release(self):
        instrument = self.accepted()
        self.client.force_login(self.a)
        response = self.client.post(reverse('instrument_renew', args=[instrument.pk]), self.payload(
            reference='PROPOSED-SUCCESSOR', predecessor_version=instrument.version, document=self.pdf()))
        self.assertEqual(response.status_code, 302)
        child = Instrument.objects.get(predecessor=instrument)
        self.client.post(reverse('instrument_submit', args=[child.pk]), {'version': child.version})
        child.refresh_from_db()
        # Deliberate out-of-band inconsistent row: supported request creation rejects this situation.
        ReleaseRequest.objects.create(instrument=instrument, requested_by=self.a, reason='Out-of-band request.')
        self.client.force_login(self.officer)
        response = self.client.post(reverse('instrument_review', args=[child.pk]), {
            'version': child.version, 'decision': 'accept', 'reason': 'Recheck conflicting workflows.',
        })
        self.assertEqual(response.status_code, 409)
        instrument.refresh_from_db()
        child.refresh_from_db()
        self.assertIsNone(instrument.superseded_at)
        self.assertEqual(child.status, 'SUBMITTED')

    def test_rejected_request_unblocks_renewal_and_renewal_blocks_new_release(self):
        instrument = self.accepted()
        release = self.request(instrument)
        self.decision(instrument, release, decision='reject')
        self.client.force_login(self.a)
        instrument.refresh_from_db()
        self.assertEqual(self.client.post(reverse('instrument_renew', args=[instrument.pk]),
            self.payload(reference='RENEWAL', predecessor_version=instrument.version)).status_code, 302)
        instrument.refresh_from_db()
        self.assertEqual(self.client.post(reverse('release_request', args=[instrument.pk]), {
            'version': instrument.version, 'reason': 'Conflicting release.',
        }).status_code, 409)

    def test_stale_requests_decisions_and_completions_have_no_effect(self):
        instrument = self.accepted()
        self.client.force_login(self.a)
        self.assertEqual(self.client.post(reverse('release_request', args=[instrument.pk]), {
            'version': instrument.version - 1, 'reason': 'Stale request.',
        }).status_code, 409)
        release = self.request(instrument)
        self.assertEqual(self.decision(instrument, release, version=instrument.version - 1).status_code, 409)
        release.refresh_from_db()
        self.assertEqual(release.status, 'PENDING')
        self.decision(instrument, release)
        instrument.refresh_from_db()
        files = set(Path(self.storage_dir).rglob('*.pdf'))
        self.assertEqual(self.completion(instrument, release, version=instrument.version - 1).status_code, 409)
        self.assertEqual(set(Path(self.storage_dir).rglob('*.pdf')), files)
        self.assertEqual(instrument.documents.count(), 1)

    def test_request_and_decision_roll_back_with_audit_failure(self):
        instrument = self.accepted()
        version = instrument.version
        self.client.force_login(self.a)
        with patch('portal.releases.event', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('release_request', args=[instrument.pk]), {
                    'version': version, 'reason': 'Release with failed audit.',
                })
        instrument.refresh_from_db()
        self.assertEqual(instrument.version, version)
        self.assertFalse(ReleaseRequest.objects.exists())
        release = self.request(instrument)
        version = instrument.version
        with patch('portal.releases.event', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.decision(instrument, release)
        release.refresh_from_db()
        instrument.refresh_from_db()
        self.assertEqual(release.status, 'PENDING')
        self.assertEqual(instrument.version, version)

    def test_completion_audit_failure_rolls_back_both_records_and_removes_file(self):
        instrument = self.accepted()
        release = self.approved(instrument)
        instrument.refresh_from_db()
        version = instrument.version
        files = set(Path(self.storage_dir).rglob('*.pdf'))
        with patch('portal.releases.event', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.completion(instrument, release)
        instrument.refresh_from_db()
        release.refresh_from_db()
        self.assertEqual(instrument.version, version)
        self.assertIsNone(instrument.released_at)
        self.assertEqual(release.status, 'APPROVED')
        self.assertIsNone(release.completion_evidence_id)
        self.assertEqual(instrument.documents.count(), 1)
        self.assertEqual(set(Path(self.storage_dir).rglob('*.pdf')), files)

    def test_release_queue_filters_roles_and_empty_results(self):
        instrument = self.accepted()
        release = self.request(instrument)
        for user in (self.a, self.officer, self.authority):
            self.client.force_login(user)
            page = self.client.get(reverse('release_queue'))
            self.assertContains(page, instrument.reference)
            self.assertIn('no-store', page['Cache-Control'])
        self.decision(instrument, release)
        page = self.client.get(reverse('release_queue'))
        self.assertNotContains(page, instrument.reference)
        self.assertContains(self.client.get(reverse('release_queue'), {'status': 'APPROVED'}), instrument.reference)
        self.assertEqual(self.client.get(reverse('release_queue'), {'status': 'UNKNOWN'}).status_code, 400)
        self.client.force_login(self.b)
        self.assertNotContains(self.client.get(reverse('release_queue')), instrument.reference)

    def test_post_login_and_csrf_required_for_all_release_actions(self):
        instrument = self.accepted()
        release = self.request(instrument)
        paths = [reverse('release_request', args=[instrument.pk]),
                 reverse('release_decision', args=[instrument.pk, release.pk]),
                 reverse('release_completion', args=[instrument.pk, release.pk])]
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 405)
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.authority)
        for path in paths:
            self.assertEqual(browser.post(path, {}).status_code, 403)
        self.client.logout()
        for path in paths:
            self.assertEqual(self.client.post(path, {}).status_code, 302)
        self.assertEqual(self.client.get(reverse('release_queue')).status_code, 302)

    def test_database_rejects_inconsistent_completion_self_decision_and_dual_lifecycle(self):
        instrument = self.accepted()
        release = self.request(instrument)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReleaseRequest.objects.filter(pk=release.pk).update(status='COMPLETED')
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReleaseRequest.objects.filter(pk=release.pk).update(
                status='APPROVED', decided_by=self.a, decided_at=timezone.now(), decision_reason='Self approval.')
        self.decision(instrument, release)
        self.completion(instrument, release)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Instrument.objects.filter(pk=instrument.pk).update(superseded_at=timezone.now())

    def test_completion_evidence_cannot_satisfy_fdr_submission_requirement(self):
        instrument = self.draft(with_document=False)
        Document.objects.create(instrument=instrument, file='test-only-placeholder.pdf',
            kind=Document.Kind.RELEASE_EVIDENCE, original_name='evidence.pdf',
            size_bytes=1, sha256='0' * 64, uploaded_by=self.authority)
        self.assertEqual(self.client.post(reverse('instrument_submit', args=[instrument.pk]),
                                         {'version': instrument.version}).status_code, 409)

    def test_model_validation_rejects_wrong_instrument_or_fdr_as_evidence(self):
        instrument = self.accepted()
        other = self.accepted(owner=self.b, reference='OTHER')
        release = ReleaseRequest(instrument=instrument, requested_by=self.a, reason='Test.',
                                  completion_evidence=other.documents.get())
        with self.assertRaises(ValidationError):
            release.clean()
        release.completion_evidence = instrument.documents.get()
        with self.assertRaises(ValidationError):
            release.clean()

    def test_authority_seed_is_opt_in_idempotent_and_preserves_existing_credentials(self):
        self.authority.delete()
        hashes = list(get_user_model().objects.order_by('pk').values_list('pk', 'password'))
        with TemporaryDirectory(prefix='release-seed-') as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            original = root / 'data' / 'demo-credentials.txt'
            original.write_text('existing private credentials - do not change')
            with override_settings(BASE_DIR=root, DEBUG=True):
                call_command('seed_demo', authority_only=True, generate_password=True, stdout=StringIO())
                credentials = (root / 'data' / 'authority-credentials.txt').read_text()
                password = credentials.split('authority: ', 1)[1].strip()
                authority = get_user_model().objects.get(username='authority')
                self.assertTrue(authority.check_password(password))
                self.assertEqual(role(authority), 'authority')
                with patch('portal.management.commands.seed_demo.getpass', side_effect=AssertionError('No prompt')):
                    call_command('seed_demo', authority_only=True, generate_password=True, stdout=StringIO())
                self.assertEqual(original.read_text(), 'existing private credentials - do not change')
                self.assertEqual((root / 'data' / 'authority-credentials.txt').read_text(), credentials)
        self.assertEqual(list(get_user_model().objects.exclude(username='authority').order_by('pk')
                              .values_list('pk', 'password')), hashes)
