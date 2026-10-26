"""P1-1: second signature above an amount, approval bound to what was approved, separate completer."""
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from casework import governance, services
from notifications.models import Notification
from obligations.models import RuleSet
from portal.models import Document, Instrument
from portal.services import WorkflowError
from portal.tests.common import PortalTestCase
from portal.tests.pdf_fixture import sample_pdf
from .test_casework import CaseworkTests, synthetic_facts

CRORE = 1_000_000_000  # paise


class PolicyLookupTests(PortalTestCase):
    def test_default_draft_asks_for_two_signatures_from_one_crore(self):
        today = date(2026, 10, 25)
        self.assertEqual(governance.policy_for(CRORE - 1, today)['required_signatures'], 1)
        policy = governance.policy_for(CRORE, today)
        self.assertEqual((policy['required_signatures'], policy['threshold_paise']), (2, CRORE))
        self.assertEqual((policy['source'], policy['label']), ('built-in draft', 'DRAFT_DEMO_NOT_APPROVED'))

    def test_a_ruleset_replaces_the_default_and_ignores_malformed_levels(self):
        RuleSet.objects.create(code='release-approval', version=1, effective_from=date(2026, 1, 1), source_clause='draft',
                               source_document='synthetic', payload={'label': 'DRAFT_DEMO_NOT_APPROVED', 'approval_levels': [
                                   {'min_amount_paise': 5_000, 'signatures': 2}, {'min_amount_paise': 'x', 'signatures': 2},
                                   {'min_amount_paise': 10, 'signatures': 9}]})
        today = date(2026, 10, 25)
        self.assertEqual(governance.policy_for(4_999, today)['required_signatures'], 1)
        self.assertEqual(governance.policy_for(5_000, today)['required_signatures'], 2)
        self.assertEqual(governance.policy_for(5_000, today)['source'], 'ruleset release-approval v1')


@override_settings(ROOT_URLCONF='obligations.test_urls', SAKSHAM_RELEASE_FACTS=synthetic_facts,
                   SAKSHAM_CLEARANCE_EVIDENCE=lambda *a: True, SAKSHAM_COMPLETION_VALIDATOR=lambda upload: True,
                   SAKSHAM_PUBLIC_BASE_URL='https://demo.invalid')
class GovernanceFlowTests(PortalTestCase):
    setUp = CaseworkTests.setUp
    case = CaseworkTests.case
    ready = CaseworkTests.ready

    def second_authority(self):
        user = get_user_model().objects.create_user(username='synthetic-authority-2')
        user.groups.add(Group.objects.get(name='Authority'))
        return user

    def high_value_case(self):
        Instrument.objects.filter(pk=self.instrument.pk).update(amount_paise=2 * CRORE)
        return self.ready(self.case())

    def sign(self, user, case):
        case.release.instrument.refresh_from_db()
        return services.decide(user, case.pk, case.version, case.release.instrument.version, 'approve', 'Synthetic authorisation')

    def complete(self, user, case):
        case.release.instrument.refresh_from_db()
        return services.complete(user, case.pk, case.version, case.release.instrument.version, 'Synthetic completion',
                                 SimpleUploadedFile('done.pdf', sample_pdf(), content_type='application/pdf'))

    def test_a_small_release_needs_one_signature_and_stores_the_fingerprint(self):
        case = self.ready(self.case())
        self.assertEqual(case.approval_policy['required_signatures'], 1)
        case = self.sign(self.authority, case)
        self.assertEqual(case.release.status, 'APPROVED')
        self.assertEqual(case.basis_fingerprint, governance.fingerprint(case))
        self.assertTrue(governance.basis_matches(case))

    def test_a_large_release_needs_two_different_authority_users(self):
        case = self.high_value_case()
        second = self.second_authority()
        self.assertEqual(case.approval_policy['required_signatures'], 2)
        case = self.sign(self.authority, case)
        self.assertEqual(case.release.status, 'PENDING')                    # one signature is not an authorisation
        self.assertEqual(len(case.approvals), 1)
        self.assertEqual(case.basis_fingerprint, '')
        self.assertTrue(Notification.objects.filter(template_id='release_second_signature').exists())
        with self.assertRaisesMessage(PermissionDenied, 'different authority user'):
            self.sign(self.authority, case)
        case.refresh_from_db()
        case = self.sign(second, case)
        self.assertEqual(case.release.status, 'APPROVED')
        self.assertEqual([a['actor_id'] for a in case.approvals], [self.authority.pk, second.pk])
        self.assertTrue(governance.basis_matches(case))

    def test_changing_the_case_after_the_first_signature_voids_it(self):
        case = self.high_value_case()
        self.sign(self.authority, case)
        Document.objects.create(instrument=self.instrument, kind='AFFIDAVIT_6', original_name='late.pdf', size_bytes=4,
                                sha256='a' * 64, uploaded_by=self.a, file='late.pdf')
        case.refresh_from_db()
        restarted = self.sign(self.second_authority(), case)
        self.assertEqual(restarted.release.status, 'PENDING')              # the second user's click became a first signature
        self.assertEqual(len(restarted.approvals), 1)
        self.assertNotEqual(restarted.approvals[0]['actor_id'], self.authority.pk)
        from obligations.models import MasterAudit
        self.assertTrue(MasterAudit.objects.filter(entity='releasecase', entity_id=case.pk,
                                                   action='CASE_SIGNATURE_VOIDED_AND_RESTARTED').exists())

    def test_an_authorisation_does_not_cover_documents_added_afterwards(self):
        case = self.sign(self.authority, self.ready(self.case()))
        Document.objects.create(instrument=self.instrument, kind='AFFIDAVIT_6', original_name='after.pdf', size_bytes=4,
                                sha256='b' * 64, uploaded_by=self.a, file='after.pdf')
        case.refresh_from_db()
        self.assertFalse(governance.basis_matches(case))
        with self.assertRaisesMessage(WorkflowError, 'no longer covers it'):
            services.issue(self.authority, case.pk, case.version, 'Issue letter')
        with self.assertRaisesMessage(WorkflowError, 'no longer covers it'):
            self.complete(self.authority, case)

    def test_release_evidence_added_by_completion_itself_does_not_break_the_basis(self):
        case = self.sign(self.authority, self.ready(self.case()))
        case = services.get_case(self.authority, case.pk)
        services.issue(self.authority, case.pk, case.version, 'Issue letter')
        case = services.get_case(self.authority, case.pk)
        self.assertTrue(governance.basis_matches(case))
        self.assertEqual(self.complete(self.authority, case).release.status, 'COMPLETED')

    def test_the_authoriser_cannot_complete_when_separation_is_on(self):
        case = self.sign(self.authority, self.ready(self.case()))
        case = services.get_case(self.authority, case.pk)
        services.issue(self.authority, case.pk, case.version, 'Issue letter')
        case = services.get_case(self.authority, case.pk)
        with override_settings(RELEASE_REQUIRE_DIFFERENT_COMPLETER=True):
            with self.assertRaisesMessage(PermissionDenied, 'cannot also record its completion'):
                self.complete(self.authority, case)
            self.assertEqual(self.complete(self.second_authority(), case).release.status, 'COMPLETED')

    def test_the_case_api_reports_the_approval_state(self):
        from casework.api import case_json
        case = self.high_value_case()
        shown = case_json(self.authority, case)['approval']
        self.assertEqual((shown['required_signatures'], shown['signatures_given'], shown['signed_by_me']), (2, 0, False))
        self.assertTrue(shown['second_signature_required'])
        case = self.sign(self.authority, case)
        mine, other = case_json(self.authority, case), case_json(self.second_authority(), case)
        self.assertTrue(mine['approval']['signed_by_me'])
        self.assertFalse(mine['actions']['can_approve'])          # you cannot sign twice
        self.assertEqual(other['approval']['signatures_given'], 1)


del CaseworkTests  # imported only for its fixtures; keep the loader from running its tests a second time here
