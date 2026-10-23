from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core import management
from django.test import Client
from django.test import override_settings
from django.urls import reverse

from portal.models import AuditEvent, Instrument
from .common import PortalTestCase


class SubmissionTests(PortalTestCase):
    def test_login_logout_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get(reverse('login'))
        self.assertEqual(page.status_code, 200)
        credentials = {'username': self.a.username, 'password': 'Testing-Only-7jS!'}
        self.assertEqual(client.post(reverse('login'), credentials).status_code, 403)
        credentials['csrfmiddlewaretoken'] = client.cookies['csrftoken'].value
        self.assertRedirects(client.post(reverse('login'), credentials), reverse('instrument_list'))
        self.assertEqual(client.get(reverse('logout')).status_code, 405)
        self.assertEqual(client.post(reverse('logout'), {}).status_code, 403)
        response = client.post(reverse('logout'), {'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertRedirects(response, reverse('login'))

    def test_new_submission_reaches_officer_and_acceptance_returns_to_institution(self):
        record = self.submitted()
        self.assertEqual(record.amount_paise, 50000025)
        self.client.force_login(self.officer)
        self.assertContains(self.client.get(reverse('instrument_list')), record.reference)
        response = self.client.post(reverse('instrument_review', args=[record.pk]), {
            'version': record.version, 'decision': 'accept', 'reason': 'Compared the PDF with declared values.',
        })
        self.assertRedirects(response, reverse('instrument_detail', args=[record.pk]))
        record.refresh_from_db()
        self.assertEqual(record.status, Instrument.Status.ACCEPTED)
        self.client.force_login(self.a)
        page = self.client.get(reverse('instrument_detail', args=[record.pk]))
        self.assertContains(page, 'Accepted for tracking')
        self.assertContains(page, 'Compared the PDF with declared values.')
        self.assertEqual(list(record.audit_events.values_list('action', flat=True)),
                         ['DRAFT_CREATED', 'SUBMITTED', 'ACCEPTED'])
        self.assertEqual(record.audit_events.last().actor, self.officer)

    def test_correction_preserves_documents_values_and_decision(self):
        record = self.submitted()
        old_doc = record.documents.get()
        self.client.force_login(self.officer)
        self.client.post(reverse('instrument_review', args=[record.pk]), {
            'version': record.version, 'decision': 'changes', 'reason': 'Correct the declared amount.',
        })
        record.refresh_from_db()
        self.client.force_login(self.a)
        self.assertContains(self.client.get(reverse('instrument_detail', args=[record.pk])), 'Correct the declared amount.')
        response = self.client.post(reverse('instrument_edit', args=[record.pk]), self.payload(
            amount='600000.00', version=record.version, document=self.pdf('replacement.pdf')))
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        change = record.audit_events.get(action='DRAFT_UPDATED')
        self.assertEqual(change.before['amount_paise'], 50000025)
        self.assertEqual(change.after['amount_paise'], 60000000)
        self.assertEqual(record.documents.count(), 2)
        self.assertTrue(old_doc.file.storage.exists(old_doc.file.name))
        self.assertEqual(self.client.post(reverse('instrument_submit', args=[record.pk]),
                                         {'version': record.version}).status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.status, Instrument.Status.SUBMITTED)
        self.assertEqual(record.audit_events.filter(action='CHANGES_REQUESTED').count(), 1)

    def test_document_required_before_submission(self):
        record = self.draft(with_document=False)
        response = self.client.post(reverse('instrument_submit', args=[record.pk]), {'version': record.version})
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, 'Upload an FDR PDF', status_code=409)
        record.refresh_from_db()
        self.assertEqual(record.status, Instrument.Status.DRAFT)

    def test_locked_records_cannot_be_edited_or_resubmitted(self):
        record = self.submitted()
        events = record.audit_events.count()
        self.assertEqual(self.client.post(reverse('instrument_edit', args=[record.pk]),
                                         self.payload(version=record.version)).status_code, 409)
        self.assertEqual(self.client.post(reverse('instrument_submit', args=[record.pk]),
                                         {'version': record.version}).status_code, 409)
        self.assertEqual(record.audit_events.count(), events)

    def test_review_requires_reason_and_submitted_state(self):
        record = self.submitted()
        self.client.force_login(self.officer)
        url = reverse('instrument_review', args=[record.pk])
        response = self.client.post(url, {'version': record.version, 'decision': 'accept', 'reason': '   '})
        self.assertEqual(response.status_code, 400)
        record.refresh_from_db()
        self.assertEqual(record.status, Instrument.Status.SUBMITTED)
        self.client.post(url, {'version': record.version, 'decision': 'accept', 'reason': 'Checked.'})
        record.refresh_from_db()
        self.assertEqual(self.client.post(url, {'version': record.version, 'decision': 'changes',
                                               'reason': 'Repeated.'}).status_code, 409)
        self.assertEqual(record.audit_events.filter(action='ACCEPTED').count(), 1)

    def test_stale_edits_submissions_and_reviews_are_rejected(self):
        record = self.draft()
        url = reverse('instrument_edit', args=[record.pk])
        original_version = record.version
        self.client.post(url, self.payload(version=original_version, bank='Updated Bank'))
        response = self.client.post(url, self.payload(version=original_version, bank='Stale Bank'))
        self.assertEqual(response.status_code, 409)
        record.refresh_from_db()
        self.assertEqual(record.bank, 'Updated Bank')
        self.assertEqual(self.client.post(reverse('instrument_submit', args=[record.pk]),
                                         {'version': original_version}).status_code, 409)
        self.client.post(reverse('instrument_submit', args=[record.pk]), {'version': record.version})
        record.refresh_from_db()
        self.client.force_login(self.officer)
        self.assertEqual(self.client.post(reverse('instrument_review', args=[record.pk]), {
            'version': record.version - 1, 'decision': 'accept', 'reason': 'Stale review.',
        }).status_code, 409)
        record.refresh_from_db()
        self.assertEqual(record.status, Instrument.Status.SUBMITTED)

    def test_amount_and_date_validation(self):
        self.client.force_login(self.a)
        for changes in ({'amount': '0'}, {'amount': '-1'}, {'amount': '1.001'},
                        {'maturity_date': '2025-01-01'}, {'reference': ''}):
            with self.subTest(changes=changes):
                response = self.client.post(reverse('instrument_create'), self.payload(**changes))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
        self.assertFalse(Instrument.objects.exists())

    def test_transition_rolls_back_if_audit_write_fails(self):
        record = self.draft()
        with patch('portal.services.event', side_effect=RuntimeError('simulated audit failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('instrument_submit', args=[record.pk]), {'version': record.version})
        record.refresh_from_db()
        self.assertEqual(record.status, Instrument.Status.DRAFT)
        self.assertEqual(record.version, 1)
        self.assertFalse(AuditEvent.objects.filter(action='SUBMITTED').exists())

    def test_actions_require_post(self):
        record = self.submitted()
        self.assertEqual(self.client.get(reverse('instrument_submit', args=[record.pk])).status_code, 405)
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(reverse('instrument_review', args=[record.pk])).status_code, 405)

    def test_seed_does_not_modify_existing_accounts(self):
        existing_hash = self.a.password
        with patch('portal.management.commands.seed_demo.getpass', side_effect=AssertionError('Must not prompt')):
            management.call_command('seed_demo', verbosity=0)
        self.a.refresh_from_db()
        self.assertEqual(self.a.password, existing_hash)
        self.assertEqual(get_user_model().objects.count(), 3)

    def test_generated_seed_creates_only_missing_accounts_and_preserves_passwords(self):
        get_user_model().objects.filter(pk=self.officer.pk).delete()
        with TemporaryDirectory(prefix='fdr-seed-') as directory:
            (Path(directory) / 'data').mkdir()
            with override_settings(BASE_DIR=Path(directory), DEBUG=True):
                management.call_command('seed_demo', generate_password=True, verbosity=0)
                credentials_path = Path(directory) / 'data' / 'demo-credentials.txt'
                saved = credentials_path.read_text()
                self.assertIn('officer:', saved)
                self.assertNotIn('institution_a:', saved)
                password = saved.split('officer: ', 1)[1].strip()
                self.assertTrue(get_user_model().objects.get(username='officer').check_password(password))
                management.call_command('seed_demo', generate_password=True, verbosity=0)
                self.assertEqual(credentials_path.read_text(), saved)
        self.a.refresh_from_db()
        self.assertTrue(self.a.check_password('Testing-Only-7jS!'))
