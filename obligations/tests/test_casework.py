"""Owned release integration with explicitly fake TRUSTED ports only in tests."""
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import OperationalError
from django.test import override_settings
from django.urls import resolve
from django.utils import timezone

from casework import services
from casework import ai_summary
from ai.models import AiRun
from obligations.catalogue import draft_payload
from obligations.models import DepositObligation, IssuedLetter, MasterAudit, ReleaseCase, RuleSet
from obligations.services import DependencyUnavailable
from access.models import UnitAssignment
from access.models import AccessLog
from notifications.models import Notification
from portal.permissions import CLEARANCE_GROUP
from portal import releases, services as portal_services
from portal.models import Document, ReleaseRequest
from portal.services import WorkflowError
from portal.tests.common import PortalTestCase


def synthetic_facts(*, actor, instrument, obligation, path, declarations):
    fixture = Path(__file__).resolve().parents[2] / 'docs/s5/scenarios.json'
    result = deepcopy(json.loads(fixture.read_text())['defaults'])
    for doc in result['documents'].values():
        doc['institution_id'], doc['instrument_id'] = instrument.institution_id, instrument.pk
    result['case']['mode'] = 'FDR'
    return result


@override_settings(ROOT_URLCONF='obligations.test_urls', SAKSHAM_RELEASE_FACTS=synthetic_facts,
    SAKSHAM_CLEARANCE_EVIDENCE=lambda *a: True,
    SAKSHAM_COMPLETION_VALIDATOR=lambda upload: True, SAKSHAM_PUBLIC_BASE_URL='https://demo.invalid')
class CaseworkTests(PortalTestCase):
    def setUp(self):
        self.authority = get_user_model().objects.create_user(username='synthetic-authority')
        self.authority.groups.add(Group.objects.create(name='Authority'))
        clearance_group, _ = Group.objects.get_or_create(name=CLEARANCE_GROUP)
        self.clearance = {}
        for unit in ['PGRC', 'VIGILANCE', 'GRANTS']:
            user = get_user_model().objects.create_user(username=f'synthetic-{unit.lower()}')
            user.groups.add(clearance_group)
            UnitAssignment.objects.create(user=user, unit=unit)
            self.clearance[unit] = user
        self.instrument = self.submitted()
        self.instrument = portal_services.review(self.officer, self.instrument.pk, self.instrument.version, 'accept', 'Synthetic scrutiny')
        self.rule = RuleSet.objects.create(code='case-demo', version=1, effective_from=date(2026,1,1),
            payload=draft_payload(), source_document='Synthetic', source_clause='6.46')
        self.obligation = DepositObligation.objects.create(institution=self.institution_a,
            rule_version=self.rule, required_paise=1000,
            term_start=date(2016,1,1), term_end=timezone.localdate()-timedelta(days=1))
        # Y1's real relationship is now present: fixtures must satisfy the live scope guard.
        self.instrument.obligation = self.obligation
        self.instrument.save(update_fields=['obligation'])

    def case(self):
        self.instrument.refresh_from_db()
        return services.request_case(self.a, instrument_id=self.instrument.pk, obligation_id=self.obligation.pk,
            instrument_version=self.instrument.version, path='TERM_COMPLETE', declarations={}, reason='Synthetic request',
            template_ref='SYNTHETIC-NONCANONICAL-TEMPLATE-6')

    def ready(self, case):
        for unit in ['PGRC','VIGILANCE','GRANTS']:
            case = services.decide_clearance(self.clearance[unit], case.pk, unit, case.version, 'CLEARED',
                'Reviewed synthetic clearance', 'SYNTH-EVIDENCE-' + unit)
        return services.review_penalties(self.officer, case.pk, case.version, 'Reviewed no penalty applicable')

    def approve(self, case):
        case.release.instrument.refresh_from_db()
        return services.decide(self.authority, case.pk, case.version,
            case.release.instrument.version, 'approve', 'Independent synthetic authorization')

    def test_request_default_missing_port_has_no_partial_request_or_audit(self):
        before = self.instrument.version
        with override_settings(SAKSHAM_RELEASE_FACTS=None), self.assertRaises(DependencyUnavailable):
            self.case()
        self.instrument.refresh_from_db()
        self.assertEqual(self.instrument.version, before)
        self.assertFalse(ReleaseRequest.objects.exists())
        self.assertFalse(ReleaseCase.objects.exists())

    def test_default_router_discovers_owned_release_routes(self):
        """The production router, rather than only the old test harness, owns these paths."""
        with override_settings(ROOT_URLCONF='config.urls'):
            match = resolve('/api/releases')
            self.assertEqual(match.func.cls.__name__, 'Cases')
            match = resolve('/api/public/verify/' + 'x' * 43)
            self.assertEqual(match.func.cls.__name__, 'PublicVerify')

    def test_request_cannot_bypass_scope_or_renewal_conflict(self):
        with self.assertRaises(Exception) as denied:
            services.request_case(self.b, instrument_id=self.instrument.pk, obligation_id=self.obligation.pk,
                instrument_version=self.instrument.version, path='TERM_COMPLETE', declarations={}, reason='Foreign',
                template_ref='SYNTHETIC-NONCANONICAL-TEMPLATE-6')
        from django.http import Http404
        self.assertIsInstance(denied.exception, Http404)
        case = self.case()
        self.instrument.refresh_from_db()
        with self.assertRaises(WorkflowError):
            self.case()
        with self.assertRaises(WorkflowError):
            portal_services.save_draft(self.a, {}, predecessor_id=self.instrument.pk)
        self.assertEqual(ReleaseCase.objects.count(), 1)

    def test_open_clearance_unknown_penalty_and_legacy_bypass_blocked(self):
        case = self.case()
        with self.assertRaises(WorkflowError):
            self.approve(case)
        with self.assertRaises(WorkflowError):
            releases.decide_release(self.authority, self.instrument.pk, case.release_id,
                case.release.instrument.version, 'approve', 'Try old service')
        case.release.refresh_from_db()
        self.assertEqual(case.release.status, 'PENDING')

    def test_clearance_denied_stale_and_missing_evidence_preserve_state(self):
        case = self.case()
        with self.assertRaises(PermissionDenied):
            services.decide_clearance(self.a, case.pk, 'PGRC', case.version, 'CLEARED', 'Denied', 'SYNTH-X')
        with self.assertRaises(WorkflowError):
            services.decide_clearance(self.clearance['PGRC'], case.pk, 'PGRC', 999, 'CLEARED', 'Stale', 'SYNTH-X')
        with override_settings(SAKSHAM_CLEARANCE_EVIDENCE=None), self.assertRaises(DependencyUnavailable):
            services.decide_clearance(self.clearance['PGRC'], case.pk, 'PGRC', case.version, 'CLEARED', 'Unknown evidence', 'SYNTH-X')
        self.assertEqual(case.clearances.get(unit='PGRC').status, 'OPEN')

    def test_requester_and_clearance_decider_cannot_be_authority(self):
        case = self.ready(self.case())
        for actor in [self.a, self.clearance['PGRC']]:
            actor.groups.clear()
            actor.groups.add(Group.objects.get(name='Authority'))
            with self.assertRaises(PermissionDenied):
                services.decide(actor, case.pk, case.version, case.release.instrument.version, 'approve', 'Conflict')

    def test_penalty_propose_confirm_and_explicit_review(self):
        case = self.case()
        case = services.review_penalties(self.officer, case.pk, case.version, 'Synthetic proposal',
            kind='premature_encashment', base_paise=10000)
        penalty = case.penalties.get()
        self.assertEqual(penalty.amount_paise, 1000)
        self.assertEqual(penalty.status, 'PROPOSED')
        with self.assertRaises(WorkflowError):
            services.review_penalties(self.officer, case.pk, case.version, 'Not confirmed')
        case = services.review_penalties(self.officer, case.pk, case.version, 'Officer confirms proposal', confirm_id=penalty.pk)
        self.assertFalse(case.penalty_review_complete)
        case = services.review_penalties(self.officer, case.pk, case.version, 'Review complete')
        self.assertTrue(case.penalty_review_complete)

    def test_approval_alone_keeps_monitoring_and_stale_replay_fails(self):
        case = self.ready(self.case())
        old_version = case.version
        case = self.approve(case)
        case.release.instrument.refresh_from_db()
        self.assertTrue(case.release.instrument.is_current)
        self.assertEqual(case.release.status, 'APPROVED')
        with self.assertRaises(WorkflowError):
            services.decide(self.authority, case.pk, old_version, case.release.instrument.version, 'approve', 'Replay')

    def test_letter_failure_rolls_back_then_pdf_and_public_revoke(self):
        case = self.approve(self.ready(self.case()))
        before = case.version
        with patch('casework.services.render_letter', side_effect=OSError('storage error')), self.assertRaises(OSError):
            services.issue(self.authority, case.pk, before, 'Generate demo letter')
        case.refresh_from_db()
        self.assertEqual(case.version, before)
        self.assertFalse(IssuedLetter.objects.exists())
        with patch('casework.services.secrets.token_urlsafe', return_value='s' * 43):
            letter = services.issue(self.authority, case.pk, before, 'Generate demo letter')
        self.assertTrue(bytes(letter.pdf).startswith(b'%PDF'))
        self.assertEqual(hashlib.sha256(bytes(letter.pdf)).hexdigest(), letter.sha256)
        public = services.public_record('s' * 43)
        self.assertEqual(set(public), {'serial','issue_date','institution_name','kind','status'})
        self.assertEqual(public['status'], 'ISSUED')
        case.refresh_from_db()
        services.revoke(self.authority, case.pk, case.version, 'Synthetic revocation')
        self.assertEqual(services.public_record('s' * 43)['status'], 'REVOKED')
        self.assertIsNone(services.public_record('bad'))

    def test_completion_requires_new_parser_evidence_and_preserves_original(self):
        case = self.approve(self.ready(self.case()))
        services.issue(self.authority, case.pk, case.version, 'Issue synthetic NOC')
        case.refresh_from_db()
        case.release.instrument.refresh_from_db()
        with override_settings(SAKSHAM_COMPLETION_VALIDATOR=None), self.assertRaises(DependencyUnavailable):
            services.complete(self.authority, case.pk, case.version, case.release.instrument.version, 'Complete', self.pdf())
        original_ids = list(Document.objects.values_list('pk', flat=True))
        case = services.complete(self.authority, case.pk, case.version, case.release.instrument.version,
            'Synthetic original handover reviewed', self.pdf('synthetic-completion.pdf'))
        self.assertEqual(case.release.status, 'COMPLETED')
        self.assertFalse(case.release.instrument.is_current)
        self.assertTrue(Document.objects.filter(pk__in=original_ids).exists())
        self.assertEqual(Document.objects.count(), len(original_ids) + 1)

    def test_audit_failure_rolls_back_case_request(self):
        with patch('casework.services.record', side_effect=OperationalError('injected')), self.assertRaises(OperationalError):
            self.case()
        self.assertFalse(ReleaseRequest.objects.exists())
        self.assertFalse(ReleaseCase.objects.exists())

    def test_notification_outbox_is_transactional_and_idempotent(self):
        self.case()
        rows = Notification.objects.filter(template_id__in=['release_requested', 'clearance_assigned'])
        self.assertEqual(rows.filter(template_id='release_requested').count(), 1)
        self.assertEqual(rows.filter(template_id='clearance_assigned').count(), 3)
        self.assertEqual(len({row.idempotency_key for row in rows}), 4)

    def test_api_own_detail_scope_invalid_stale_and_default_missing_dependency(self):
        case = self.case()
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(f'/api/releases/{case.pk}').status_code, 404)
        self.client.force_login(self.clearance['PGRC'])
        response = self.client.post(f'/api/releases/{case.pk}/clearances/PGRC',
            json.dumps({'version': 999, 'status': 'CLEARED', 'reason': 'Stale', 'evidence_ref': 'SYNTH-X'}), content_type='application/json')
        self.assertEqual(response.status_code, 409)
        response = self.client.get(f'/api/releases/{case.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['actions']['can_approve'])
        with override_settings(SAKSHAM_RELEASE_FACTS=None):
            response = self.client.get(f'/api/releases/{case.pk}')
        self.assertEqual(response.json()['readiness']['outcome'], 'CONTEXT_UNAVAILABLE')

    @override_settings(AI_ENABLED=False)
    def test_ai_summary_is_scoped_advisory_and_disabled_without_provider(self):
        case = self.case()
        with patch('casework.ai_summary.call_model') as provider:
            result = ai_summary.summarize(self.clearance['PGRC'], case.pk, case.version)
        self.assertEqual(result['status'], 'disabled')
        self.assertTrue(result['advisory'])
        self.assertEqual(result['label'], 'AI-generated: verify before use')
        provider.assert_not_called()
        self.assertEqual(AiRun.objects.get(operation='RELEASE_SUMMARY').status, 'DISABLED')
        with self.assertRaises(Exception):
            ai_summary.summarize(self.b, case.pk, case.version)

    @override_settings(AI_ENABLED=True)
    def test_ai_summary_caches_by_case_version_and_never_changes_case(self):
        case = self.case()
        before_status, before_version = case.release.status, case.version
        output = {'summary': 'One clearance remains open.', 'risk_flags': [
            {'field': 'clearances[0].status', 'severity': 'warning', 'message': 'Manual clearance is pending.'}]}
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'synthetic-only'}), \
                patch('casework.ai_summary.call_model', return_value=output) as provider:
            first = ai_summary.summarize(self.clearance['PGRC'], case.pk, case.version)
            second = ai_summary.summarize(self.clearance['PGRC'], case.pk, case.version)
        self.assertEqual(first['status'], 'success')
        self.assertFalse(first['cached'])
        self.assertTrue(second['cached'])
        self.assertEqual(len(first['risk_flags']), 1)
        provider.assert_called_once()
        case.refresh_from_db()
        case.release.refresh_from_db()
        self.assertEqual((case.release.status, case.version), (before_status, before_version))

    @override_settings(AI_ENABLED=True)
    def test_ai_summary_rejects_invalid_output_and_stale_version(self):
        case = self.case()
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'synthetic-only'}), \
                patch('casework.ai_summary.call_model', return_value={'summary': 'Bad', 'risk_flags': [{}]}):
            result = ai_summary.summarize(self.clearance['PGRC'], case.pk, case.version)
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(AiRun.objects.get(operation='RELEASE_SUMMARY').status, 'FAILED')
        with self.assertRaises(WorkflowError):
            ai_summary.summarize(self.clearance['PGRC'], case.pk, case.version + 1)

    @override_settings(AI_ENABLED=False)  # independent of a developer's local .env
    def test_ai_summary_api_is_specific_route_and_requires_current_version(self):
        case = self.case()
        self.client.force_login(self.clearance['PGRC'])
        response = self.client.post(f'/api/releases/{case.pk}/ai-summary', json.dumps({'version': case.version}),
            content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], 'disabled')
        response = self.client.post(f'/api/releases/{case.pk}/ai-summary', json.dumps({'version': case.version + 1}),
            content_type='application/json')
        self.assertEqual(response.status_code, 409, response.content)

    def test_full_owned_api_release_journey_and_public_disclosure(self):
        def post(path, data, status=200):
            response = self.client.post('/api/' + path, json.dumps(data), content_type='application/json')
            self.assertEqual(response.status_code, status, response.content)
            return response.json()
        self.client.force_login(self.a)
        current = post('releases', {'instrument_id': self.instrument.pk, 'obligation_id': self.obligation.pk,
            'instrument_version': self.instrument.version, 'path':'TERM_COMPLETE', 'declarations':{},
            'reason':'Synthetic API request', 'template_ref':'SYNTHETIC-NONCANONICAL-TEMPLATE-6'}, 201)
        pk = current['id']
        for unit in ['PGRC','VIGILANCE','GRANTS']:
            self.client.force_login(self.clearance[unit])
            current = post(f'releases/{pk}/clearances/{unit}', {'version':current['version'],
                'status':'CLEARED', 'reason':'Reviewed synthetic evidence', 'evidence_ref':'SYNTH-'+unit})
        self.client.force_login(self.officer)
        current = post(f'releases/{pk}/penalties', {'version':current['version'], 'reason':'Review complete; no penalties'})
        self.client.force_login(self.authority)
        current = post(f'releases/{pk}/approve', {'version':current['version'],
            'instrument_version':current['instrument_version'], 'reason':'Independent review complete'})
        self.assertTrue(current['monitoring_active'])
        with patch('casework.services.secrets.token_urlsafe', return_value='t'*43):
            current = post(f'releases/{pk}/issue', {'version':current['version'], 'reason':'Generate unsigned demo letter'})
        self.assertEqual(self.client.get(f'/api/releases/{pk}/letter').status_code, 200)
        self.assertTrue(AccessLog.objects.filter(action=AccessLog.NOC_VIEW, object_type='issuedletter').exists())
        from django.test import Client
        public = Client().get('/api/public/verify/' + 't'*43)
        self.assertEqual(public.status_code, 200)
        self.assertEqual(set(public.json()), {'serial','issue_date','institution_name','kind','status'})
        response = self.client.post(f'/api/releases/{pk}/complete', {'version':current['version'],
            'instrument_version':current['instrument_version'], 'notes':'Synthetic handover evidenced',
            'document':self.pdf('synthetic-new-evidence.pdf')})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], 'COMPLETED')
        self.assertFalse(response.json()['monitoring_active'])
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(f'/api/releases/{pk}/letter').status_code, 404)

    def test_public_identity_is_frozen_and_queue_is_unit_scoped(self):
        open_case = self.case()
        self.client.force_login(self.clearance['PGRC'])
        response = self.client.get('/api/clearance-tasks')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['case_id'], open_case.pk)
        case = self.approve(self.ready(open_case))
        with patch('casework.services.secrets.token_urlsafe', return_value='f'*43):
            services.issue(self.authority, case.pk, case.version, 'Synthetic issuance')
        case.refresh_from_db()
        from portal.models import Institution
        Institution.objects.filter(pk=self.institution_a.pk).update(name='Later corrected identity')
        self.assertEqual(services.public_record('f'*43)['institution_name'], 'Fictional A')
        self.client.force_login(self.clearance['VIGILANCE'])
        response = self.client.post(f'/api/releases/{case.pk}/clearances/PGRC', json.dumps({
            'version': case.version, 'status': 'CLEARED', 'reason': 'Wrong unit', 'evidence_ref': 'SYNTH-X'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_rule_mutation_requires_reassessment(self):
        case = self.ready(self.case())
        payload = deepcopy(self.rule.payload)
        payload['proof_days'] = 16
        self.rule.payload = payload
        self.rule.save(update_fields=['payload'])
        with self.assertRaises(WorkflowError):
            self.approve(case)
        case.release.refresh_from_db()
        self.assertEqual(case.release.status, 'PENDING')

    def test_rejection_is_recorded_without_completion_and_replay_blocked(self):
        case = self.ready(self.case())
        case = services.decide(self.authority, case.pk, case.version, case.release.instrument.version,
                                'reject', 'Synthetic rejection reason')
        self.assertEqual(case.release.status, 'REJECTED')
        case.release.instrument.refresh_from_db()
        self.assertTrue(case.release.instrument.is_current)
        with self.assertRaises(WorkflowError):
            services.decide(self.authority, case.pk, case.version, case.release.instrument.version,
                            'reject', 'Replay')

    def test_failed_legacy_completion_removes_new_file_and_rolls_back_all_state(self):
        case = self.approve(self.ready(self.case()))
        services.issue(self.authority, case.pk, case.version, 'Synthetic issuance')
        case.refresh_from_db()
        case.release.instrument.refresh_from_db()
        files = {p for p in Path(self.storage_dir).rglob('*') if p.is_file()}
        before_audit = MasterAudit.objects.count()
        with patch('portal.releases.event', side_effect=OperationalError('injected after file')), self.assertRaises(OperationalError):
            services.complete(self.authority, case.pk, case.version, case.release.instrument.version,
                              'Evidence reviewed', self.pdf('synthetic-rollback.pdf'))
        case.release.refresh_from_db()
        self.assertEqual(case.release.status, 'APPROVED')
        self.assertEqual(MasterAudit.objects.count(), before_audit)
        self.assertEqual({p for p in Path(self.storage_dir).rglob('*') if p.is_file()}, files)
