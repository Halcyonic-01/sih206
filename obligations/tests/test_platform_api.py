"""S2 acceptance through normal platform routes, session auth and middleware."""
from datetime import date
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, OperationalError
from django.test import Client, override_settings
from django.urls import resolve

from access.models import AccessLog
from obligations.catalogue import draft_payload
from obligations.models import DepositObligation, InstitutionProfile, MasterAudit, ProgrammeApproval, RuleSet
from obligations.services import DependencyUnavailable
from portal.models import Institution
from portal.tests.common import PortalTestCase


@override_settings(ROOT_URLCONF='config.urls')
class PlatformApiTests(PortalTestCase):
    def setUp(self):
        self.client.force_login(self.officer)
        for institution in [self.institution_a, self.institution_b]:
            InstitutionProfile.objects.create(institution=institution, aicte_id='SYNTH-'+institution.code,
                trust_name='Synthetic trust', institution_type='PRIVATE', region='North',
                state='Delhi', contact_email='synthetic@example.invalid')
        self.rule = RuleSet.objects.create(code='platform-synthetic', version=1,
            effective_from=date(2026, 1, 1), source_document='Synthetic', source_clause='Synthetic',
            payload=draft_payload())
        self.obligation = DepositObligation.objects.create(institution=self.institution_a,
            required_paise=10000, rule_version=self.rule)
        self.approval = ProgrammeApproval.objects.create(institution=self.institution_a,
            programme='MANAGEMENT', level='PG', approved_on=date(2026, 1, 1),
            loa_ref='SYNTH-LOA', land_tenure='OWNED', building_tenure='OWNED')

    def send(self, method, path, data, client=None, **extra):
        return getattr(client or self.client, method)('/api/'+path,
            data=json.dumps(data), content_type='application/json', **extra)

    def payload(self, **overrides):
        return dict(code='SYNTH-NEW', name='Synthetic new', aicte_id='SYNTH-NEW',
            trust_name='Synthetic trust', institution_type='PRIVATE', region='North',
            state='Delhi', contact_email='new@example.invalid', reason='Reviewed synthetic setup') | overrides

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status, response.content)
        self.assertEqual(response.json()['code'], code)
        self.assertIsInstance(response.json()['detail'], str)
        self.assertNotIn('error', response.json())
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('X-Request-ID', response)

    def test_registered_default_routes_and_no_future_endpoints(self):
        for path in ['institutions', f'institutions/{self.institution_a.pk}',
            f'institutions/{self.institution_a.pk}/programme-approvals',
            f'programme-approvals/{self.approval.pk}',
            f'institutions/{self.institution_a.pk}/obligations',
            f'obligations/{self.obligation.pk}', 'calculator', 'rules']:
            self.assertTrue(resolve('/api/'+path).func.view_class.__module__.startswith('obligations.api.'))
        for path in ['releases', 'kpis', 'reports/pending_verifications']:
            self.assertEqual(resolve('/api/'+path).func.view_class.__name__, 'NotFoundView')

    def test_signed_out_requests_use_shared_401_envelope(self):
        client = Client()
        for path in ['institutions', f'institutions/{self.institution_a.pk}',
            f'programme-approvals/{self.approval.pk}', f'obligations/{self.obligation.pk}', 'rules']:
            self.assert_error(client.get('/api/'+path), 401, 'not_authenticated')
        self.assert_error(self.send('post', 'calculator', {}, client), 401, 'not_authenticated')

    def test_roles_are_explicit_and_unknown_or_ambiguous_membership_denied(self):
        for name, expected in [('Authority', 200), ('Auditor', 403), ('Clearance', 403)]:
            user = get_user_model().objects.create_user(username='synthetic-'+name)
            user.groups.add(Group.objects.get_or_create(name=name)[0])
            self.client.force_login(user)
            response = self.client.get('/api/institutions')
            self.assertEqual(response.status_code, expected)
            self.assert_error(self.send('post', 'institutions', self.payload()), 403, 'permission_denied')
        self.officer.groups.add(Group.objects.get(name='Institution'))
        self.client.force_login(self.officer)
        self.assert_error(self.client.get('/api/institutions'), 403, 'permission_denied')

    def test_scope_precedes_lookup_and_foreign_is_identical_to_missing(self):
        self.client.force_login(self.b)
        for prefix, identity in [('institutions', self.institution_a.pk),
            ('programme-approvals', self.approval.pk), ('obligations', self.obligation.pk)]:
            foreign = self.client.get(f'/api/{prefix}/{identity}')
            missing = self.client.get(f'/api/{prefix}/999999')
            self.assert_error(foreign, 404, 'not_found')
            self.assertEqual(foreign.json(), missing.json())
            self.assert_error(self.send('patch', f'{prefix}/{identity}',
                {'version': 1, 'reason': 'Foreign mutation'}), 404, 'not_found')
        rows = self.client.get('/api/institutions').json()
        self.assertEqual([r['id'] for r in rows['results']], [self.institution_b.pk])

    def test_platform_pagination_caps_page_size_and_counts_only_scoped_records(self):
        for i in range(26):
            Institution.objects.create(code=f'SYNTH-PAGE-{i}', name='Synthetic page')
        response = self.client.get('/api/institutions')
        self.assertEqual(set(response.json()), {'count','page','page_size','total_pages','results'})
        self.assertEqual((response.json()['count'], response.json()['total_pages']), (28, 2))
        self.assertEqual(len(response.json()['results']), 25)
        self.assertEqual(self.client.get('/api/institutions?page=2').json()['page'], 2)
        self.assertEqual(self.client.get('/api/institutions?page_size=200').json()['page_size'], 100)
        self.assert_error(self.client.get('/api/institutions?page=invalid'), 404, 'not_found')
        self.client.force_login(self.a)
        self.assertEqual(self.client.get('/api/institutions').json()['count'], 1)
        for suffix in ['programme-approvals', 'obligations']:
            result = self.client.get(f'/api/institutions/{self.institution_a.pk}/{suffix}').json()
            self.assertEqual(result['total_pages'], 1)

    def test_real_session_csrf_cookie_is_required_for_writes(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.officer)
        self.assert_error(self.send('post','institutions',self.payload(),client),403,'permission_denied')
        client.get('/api/auth/csrf/')
        token = client.cookies['csrftoken'].value
        response = self.send('post','institutions',self.payload(),client,HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 201, response.content)

    def test_institution_write_requires_reason_version_and_rolls_back_audit_failure(self):
        invalid = self.send('post', 'institutions', self.payload(contact_email='invalid'))
        self.assert_error(invalid,400,'validation_error')
        self.assertIn('contact_email',invalid.json()['errors'])
        self.assertFalse(Institution.objects.filter(code='SYNTH-NEW').exists())
        created = self.send('post','institutions',self.payload()).json()
        path = f'institutions/{created["id"]}'
        for values in [{'name':'changed','reason':'Missing version'},
                       {'name':'changed','version':1}]:
            self.assert_error(self.send('patch',path,values),400,'validation_error')
        values = {'version':1,'reason':'Reviewed correction','name':'Synthetic corrected'}
        with patch('obligations.services.audit',side_effect=OperationalError('private SQL/path')):
            response=self.send('patch',path,values)
        self.assert_error(response,503,'unavailable')
        self.assertNotIn(b'private SQL',response.content)
        self.assertEqual(InstitutionProfile.objects.get(institution_id=created['id']).version,1)
        self.assertEqual(self.send('patch',path,values).json()['version'],2)
        self.assert_error(self.send('patch',path,values),409,'conflict')
        self.assertEqual(MasterAudit.objects.count(),2)

    def test_child_writes_preserve_validation_scope_reason_and_versions(self):
        for suffix, detail, values in [
            ('programme-approvals','programme-approvals',{'programme':'MANAGEMENT','level':'PG',
                'approved_on':'2026-01-01','loa_ref':'SYNTH-SECOND','land_tenure':'OWNED','building_tenure':'LEASED'}),
            ('obligations','obligations',{'basis':'APPROVAL','required_paise':12345,'rule_version_id':self.rule.pk})]:
            path=f'institutions/{self.institution_a.pk}/{suffix}'
            self.assert_error(self.send('post',path,values),400,'validation_error')
            response=self.send('post',path,values|{'reason':'Reviewed create'})
            self.assertEqual(response.status_code,201,response.content)
            row=response.json()
            change={'version':1,'reason':'Reviewed edit',**values}
            self.assertEqual(self.send('patch',f'{detail}/{row["id"]}',change).status_code,200)
            self.assert_error(self.send('patch',f'{detail}/{row["id"]}',change),409,'conflict')
            self.assert_error(self.send('patch',f'{detail}/{row["id"]}',{'version':2,'reason':'Invalid','institution_id':2}),400,'validation_error')
            self.client.force_login(self.a)
            self.assert_error(self.send('post',path,values|{'reason':'Forbidden create'}),403,'permission_denied')
            self.assert_error(self.send('patch',f'{detail}/{row["id"]}',change),403,'permission_denied')
            self.client.force_login(self.officer)

    def test_duplicate_and_database_integrity_conflicts_use_safe_shared_errors(self):
        self.assertEqual(self.send('post','institutions',self.payload()).status_code,201)
        self.assert_error(self.send('post','institutions',self.payload()),409,'conflict')
        with patch('obligations.services.create_institution',side_effect=IntegrityError('private duplicate SQL')):
            response=self.send('post','institutions',self.payload())
        self.assert_error(response,409,'conflict')
        self.assertNotIn(b'private',response.content)

    def test_calculator_is_scoped_preview_with_draft_evidence_and_no_master_writes(self):
        body={'institution_id':self.institution_a.pk,'rule_set_id':self.rule.pk,'approvals':[
            {'programme':'MANAGEMENT','level':'PG','land_tenure':'OWNED','building_tenure':'LEASED'}]}
        before=MasterAudit.objects.count()
        result=self.send('post','calculator',body)
        self.assertEqual(result.status_code,200,result.content)
        # Management PG: 15 lakh INR = 150,000,000 paise; leased once => 300,000,000.
        self.assertEqual(result.json()['required_paise'],300000000)
        self.assertEqual(result.json()['policy_label'],'DRAFT_DEMO_NOT_APPROVED')
        self.assertEqual(MasterAudit.objects.count(),before)
        body['approvals'][0]['level']='UNKNOWN'
        self.assert_error(self.send('post','calculator',body),400,'validation_error')
        self.client.force_login(self.b)
        self.assert_error(self.send('post','calculator',body),404,'not_found')

    def test_unknown_holdings_are_not_zero_and_large_legacy_money_stays_exact(self):
        DepositObligation.objects.filter(pk=self.obligation.pk).update(required_paise=9007199254740993)
        response=self.client.get(f'/api/obligations/{self.obligation.pk}')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['required_paise'],'9007199254740993')
        assessment=response.json()['assessment']
        self.assertEqual(assessment['status'],'UNAVAILABLE')
        for field in ['coverage','findings','holdings','open_actions']:
            self.assertIsNone(assessment[field])

    def test_staff_search_logging_is_minimal_and_failure_prevents_disclosure(self):
        response=self.client.get('/api/institutions?q=SYNTH')
        self.assertEqual(response.status_code,200)
        log=AccessLog.objects.get(action=AccessLog.SEARCH)
        self.assertEqual(log.object_type,'institution')
        self.assertEqual(log.request_id,response['X-Request-ID'])
        self.assertNotIn('SYNTH',log.detail)
        with patch('obligations.api.views.log_access',side_effect=OperationalError('private log path')):
            response=self.client.get('/api/institutions')
        self.assert_error(response,503,'unavailable')
        self.assertNotIn(b'private',response.content)
        self.assertNotIn('results',response.json())

    def test_missing_dependency_and_parser_errors_use_platform_envelope(self):
        with patch('obligations.services.calculator',side_effect=DependencyUnavailable('private provider')):
            response=self.send('post','calculator',{'institution_id':self.institution_a.pk,
                'rule_set_id':self.rule.pk,'approvals':[]})
        self.assert_error(response,503,'unavailable')
        self.assertNotIn(b'private provider',response.content)
        response=self.client.post('/api/calculator','{',content_type='application/json')
        self.assert_error(response,400,'validation_error')

    def test_malformed_types_protected_fields_and_versions_do_not_mutate(self):
        for values in [self.payload(name=True), self.payload(code='X'*31),
            self.payload(actor_id=self.officer.pk)]:
            self.assert_error(self.send('post','institutions',values),400,'validation_error')
        for version in [None, True, '1', 0, -1]:
            for path in [f'institutions/{self.institution_a.pk}',
                f'programme-approvals/{self.approval.pk}', f'obligations/{self.obligation.pk}']:
                self.assert_error(self.send('patch',path,{'version':version,'reason':'Invalid version'}),
                    400,'validation_error')
        self.assertEqual(MasterAudit.objects.count(),0)
        self.assertEqual(self.client.get(f'/api/institutions/{self.institution_a.pk}').json()['version'],1)

    def test_inactive_or_unassigned_accounts_cannot_read_master_data(self):
        user=get_user_model().objects.create_user(username='synthetic-unassigned')
        self.client.force_login(user)
        self.assert_error(self.client.get('/api/institutions'),403,'permission_denied')
        self.officer.is_active=False
        self.officer.save(update_fields=['is_active'])
        self.client.force_login(self.officer)
        self.assert_error(self.client.get('/api/institutions'),401,'not_authenticated')

    def test_schema_includes_owned_routes_pagination_and_session_security(self):
        response=self.client.get('/api/schema/?format=json')
        self.assertEqual(response.status_code,200)
        schema=response.json()
        paths=schema['paths']
        for path in ['/api/institutions','/api/institutions/{id}','/api/obligations/{id}',
            '/api/programme-approvals/{id}','/api/calculator','/api/rules']:
            self.assertIn(path,paths)
        operation=paths['/api/institutions']['get']
        self.assertEqual(operation['security'],[{'sessionAuth':[]}])
        self.assertIn('401',operation['responses'])
        component=schema['components']['schemas']['InstitutionPage']
        self.assertEqual(set(component['properties']),{'count','page','page_size','total_pages','results'})
        for path in ['/api/institutions/{id}', '/api/programme-approvals/{id}', '/api/obligations/{id}']:
            reference=paths[path]['patch']['requestBody']['content']['application/json']['schema']['$ref']
            patch_request=schema['components']['schemas'][reference.rsplit('/',1)[-1]]
            self.assertEqual(set(patch_request['required']),{'version','reason'})
