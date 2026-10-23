"""One HTTP journey joins scrutiny, renewal and release on the same lineage."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from portal.models import Document, Instrument
from portal.permissions import AUTHORITY_GROUP
from .common import PortalTestCase
from .pdf_fixture import sample_pdf


class CompleteJourneyTests(PortalTestCase):
    def post_action(self, name, item, values, *extra):
        item.refresh_from_db()
        return self.client.post(reverse(name, args=[item.pk, *extra]), {'version': item.version, **values})

    def test_correction_to_accepted_successor_to_evidence_backed_release(self):
        authority = get_user_model().objects.create_user(username='journey_authority')
        authority.groups.add(Group.objects.get_or_create(name=AUTHORITY_GROUP)[0])
        self.client.force_login(self.a)
        mismatch = SimpleUploadedFile('amount.pdf', sample_pdf('SYNTHETIC INR 600000.00'), content_type='application/pdf')
        self.assertEqual(self.client.post(reverse('instrument_create'),
                         self.payload(document=mismatch)).status_code, 302)
        parent = Instrument.objects.get()
        original = parent.documents.get()
        self.assertEqual(self.post_action('instrument_submit', parent, {}).status_code, 302)
        self.client.force_login(self.officer)
        self.assertEqual(self.post_action('observation_add', parent, {
            'document': original.pk, 'page_number': 1, 'severity': 'BLOCKING',
            'comment': 'Page 1 says INR 600000; declared amount is INR 500000.25.',
        }).status_code, 302)
        observation = parent.observations.get()
        self.assertEqual(self.post_action('instrument_review', parent, {
            'decision': 'changes', 'reason': 'Correct declared amount against page 1.',
        }).status_code, 302)
        self.client.force_login(self.a)
        parent.refresh_from_db()
        self.assertEqual(self.client.post(reverse('instrument_edit', args=[parent.pk]), self.payload(
            amount='600000.00', version=parent.version, document=self.pdf('corrected.pdf'))).status_code, 302)
        self.assertEqual(self.post_action('instrument_submit', parent, {}).status_code, 302)
        self.client.force_login(self.officer)
        self.assertEqual(self.post_action('instrument_review', parent, {
            'decision': 'accept', 'reason': 'Attempt before explicit observation resolution.',
        }).status_code, 409)
        self.assertEqual(self.post_action('observation_resolve', parent, {
            'resolution': 'Manually rechecked original page 1 against corrected declaration.',
        }, observation.pk).status_code, 302)
        self.assertEqual(self.post_action('instrument_review', parent, {
            'decision': 'accept', 'reason': 'Human review completed for tracking.',
        }).status_code, 302)
        self.assertContains(self.client.get(reverse('instrument_detail', args=[parent.pk])), 'Page 1')
        self.client.force_login(self.a)
        parent.refresh_from_db()
        self.assertEqual(self.client.post(reverse('instrument_renew', args=[parent.pk]), self.payload(
            reference='JOURNEY-SUCCESSOR', amount='600000.00', predecessor_version=parent.version,
            document=self.pdf('successor.pdf'))).status_code, 302)
        successor = Instrument.objects.get(predecessor=parent)
        self.assertEqual(self.post_action('instrument_submit', successor, {}).status_code, 302)
        self.client.force_login(self.officer)
        self.assertEqual(self.post_action('instrument_review', successor, {
            'decision': 'accept', 'reason': 'Manually reviewed successor.',
        }).status_code, 302)
        parent.refresh_from_db()
        self.assertTrue(parent.is_superseded)
        self.client.force_login(self.a)
        self.assertEqual(self.post_action('release_request', successor, {'reason': 'Synthetic discharge request.'}).status_code, 302)
        release = successor.release_requests.get()
        self.client.force_login(authority)
        self.assertEqual(self.post_action('release_decision', successor, {
            'decision': 'approve', 'reason': 'Human authority assessment.',
        }, release.pk).status_code, 302)
        successor.refresh_from_db()
        self.assertTrue(successor.is_current)
        self.assertEqual(self.post_action('release_completion', successor, {
            'notes': 'Missing file attempt.',
        }, release.pk).status_code, 400)
        self.assertEqual(self.post_action('release_completion', successor, {
            'notes': 'Manually inspected synthetic completion evidence.', 'document': self.pdf('completion.pdf'),
        }, release.pk).status_code, 302)
        successor.refresh_from_db()
        release.refresh_from_db()
        self.assertTrue(successor.is_released)
        self.assertEqual(release.status, 'COMPLETED')
        self.assertEqual(release.completion_evidence.kind, Document.Kind.RELEASE_EVIDENCE)
        current = self.client.get(reverse('instrument_list'), {'category': 'accepted'})
        self.assertEqual(list(current.context['instruments']), [])
        self.assertEqual(Document.objects.count(), 4)
        for doc in Document.objects.all():
            response = self.client.get(reverse('document_download', args=[doc.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF-'))
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(reverse('instrument_detail', args=[parent.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('document_download', args=[original.pk])).status_code, 404)
