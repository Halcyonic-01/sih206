from datetime import date, timedelta
from io import BytesIO
import json
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import OperationalError
from django.test import override_settings, Client
from django.utils import timezone
from openpyxl import load_workbook

from portal.tests.common import PortalTestCase
from obligations.catalogue import draft_payload
from obligations.models import CsvImport, DepositObligation, InstitutionProfile, MasterAudit, RuleSet
from obligations import imports


@override_settings(ROOT_URLCONF='obligations.test_urls')
class OwnedApiTests(PortalTestCase):
    def setUp(self):
        self.client.force_login(self.officer)
        self.rule = RuleSet.objects.create(code='owned-demo', version=1,
            effective_from=date(2026, 1, 1), payload=draft_payload(),
            source_clause='Synthetic demo', source_document='Synthetic rules')

    def send(self, method, path, data):
        return getattr(self.client, method)('/api/' + path, data=json.dumps(data), content_type='application/json')

    def profile_payload(self):
        return {'code': 'SYNTH-NEW', 'name': 'Synthetic college', 'aicte_id': 'SYNTH-NEW',
            'trust_name': 'Synthetic trust', 'institution_type': 'PRIVATE', 'region': 'North',
            'state': 'Delhi', 'contact_email': 'synth@example.invalid', 'reason': 'Synthetic setup'}

    def create_profile(self):
        response = self.send('post', 'institutions', self.profile_payload())
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_institution_create_update_and_stale_replay(self):
        row = self.create_profile()
        path = f'institutions/{row["id"]}'
        change = {'version': 1, 'reason': 'Correct synthetic name', 'name': 'Corrected synthetic name'}
        result = self.send('patch', path, change)
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(result.json()['version'], 2)
        self.assertEqual(self.send('patch', path, change).status_code, 409)
        self.assertEqual(MasterAudit.objects.count(), 2)

    def test_scope_lists_counts_and_foreign_paths(self):
        row = self.create_profile()
        self.client.force_login(self.a)
        response = self.client.get('/api/institutions')
        self.assertEqual(response.json()['count'], 1)
        self.assertEqual(self.client.get(f'/api/institutions/{row["id"]}').status_code, 404)
        self.assertEqual(self.send('patch', f'institutions/{self.institution_a.pk}', {
            'version': 1, 'reason': 'Forbidden', 'name': 'changed'}).status_code, 403)
        self.assertEqual(MasterAudit.objects.count(), 1)

    def test_invalid_create_rolls_back_identity(self):
        values = self.profile_payload()
        values['contact_email'] = 'invalid'
        self.assertEqual(self.send('post', 'institutions', values).status_code, 400)
        self.assertFalse(InstitutionProfile.objects.exists())
        from portal.models import Institution
        self.assertFalse(Institution.objects.filter(code='SYNTH-NEW').exists())

    def test_boolean_text_and_duplicate_identity_are_rejected(self):
        values = self.profile_payload()
        values['name'] = True
        self.assertEqual(self.send('post', 'institutions', values).status_code, 400)
        self.create_profile()
        self.assertEqual(self.send('post', 'institutions', self.profile_payload()).status_code, 409)

    def test_all_report_types_scope_and_invalid_kind(self):
        for kind in ['pending_verifications','upcoming_maturities','missing_documents','intervention','released_register']:
            response = self.client.get('/api/reports/' + kind)
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(response.json()['rows'], [])
        self.assertEqual(self.client.get('/api/reports/unsupported').status_code, 400)

    def test_audit_failure_rolls_back_update(self):
        row = self.create_profile()
        with patch('obligations.services.audit', side_effect=OperationalError('private sql')):
            response = self.send('patch', f'institutions/{row["id"]}', {
                'version': 1, 'name': 'lost', 'reason': 'Test rollback'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'private sql', response.content)
        profile = InstitutionProfile.objects.get()
        self.assertEqual(profile.version, 1)
        self.assertEqual(profile.institution.name, 'Synthetic college')

    def test_children_allowed_denied_invalid_and_stale(self):
        for suffix, values in [('programme-approvals', {'programme': 'MANAGEMENT', 'level': 'PG',
            'approved_on': '2026-01-01', 'loa_ref': 'SYNTH-LOA', 'land_tenure': 'OWNED', 'building_tenure': 'LEASED'}),
            ('obligations', {'basis': 'APPROVAL', 'required_paise': 10000, 'rule_version_id': self.rule.pk})]:
            path = f'institutions/{self.institution_a.pk}/{suffix}'
            response = self.send('post', path, values | {'reason': 'Synthetic create'})
            self.assertEqual(response.status_code, 201, response.content)
            pk = response.json()['id']
            detail = f'{suffix}/{pk}'
            self.assertEqual(self.client.get('/api/' + detail).status_code, 200)
            update = {next(iter(values)): next(iter(values.values())), 'version': 1, 'reason': 'Reviewed correction'}
            self.assertEqual(self.send('patch', detail, update).status_code, 200)
            self.assertEqual(self.send('patch', detail, update).status_code, 409)
            self.assertEqual(self.send('patch', detail, {'institution_id': self.institution_b.pk}).status_code, 400)
            self.client.force_login(self.b)
            self.assertEqual(self.client.get('/api/' + detail).status_code, 404)
            self.client.force_login(self.officer)

    def test_missing_link_is_unknown_not_zero(self):
        ob = DepositObligation.objects.create(institution=self.institution_a, rule_version=self.rule,
                                              required_paise=10000)
        response = self.client.get(f'/api/obligations/{ob.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['assessment']['coverage'])
        self.assertEqual(response.json()['assessment']['status'], 'UNAVAILABLE')

    def test_calculator_scoped_preview_and_invalid_input_no_writes(self):
        row = self.create_profile()
        payload = {'institution_id': row['id'], 'rule_set_id': self.rule.pk, 'approvals': [
            {'programme': 'MANAGEMENT', 'level': 'PG', 'land_tenure': 'LEASED', 'building_tenure': 'OWNED'}]}
        before = MasterAudit.objects.count()
        response = self.send('post', 'calculator', payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertGreater(response.json()['required_paise'], 0)
        self.assertEqual(MasterAudit.objects.count(), before)
        payload['approvals'][0]['level'] = 'UNKNOWN'
        self.assertEqual(self.send('post', 'calculator', payload).status_code, 400)
        self.client.force_login(self.a)
        self.assertEqual(self.send('post', 'calculator', payload).status_code, 404)

    def test_auth_csrf_ambiguous_roles_and_no_store(self):
        self.assertEqual(Client().get('/api/institutions').status_code, 403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.officer)
        self.assertEqual(client.post('/api/calculator', '{}', content_type='application/json').status_code, 403)
        self.assertIn('no-store', self.client.get('/api/institutions')['Cache-Control'])
        from django.contrib.auth.models import Group
        self.officer.groups.add(Group.objects.get(name='Institution'))
        self.assertEqual(self.client.get('/api/institutions').status_code, 403)

    def preview(self):
        path = Path(__file__).resolve().parents[2] / 'evaluation/s4/valid.csv'
        response = self.client.post('/api/imports/institutions/preview', {
            'file': SimpleUploadedFile('synthetic.csv', path.read_bytes(), content_type='text/csv')})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], 'VALID')
        return response.json()['preview_id']

    def test_csv_preview_commit_and_replay(self):
        pk = self.preview()
        response = self.send('post', f'imports/institutions/{pk}/commit', {'version': 1, 'reason': 'Import synthetic master'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()['created_ids']), 3)
        self.assertEqual(CsvImport.objects.get(pk=pk).source, b'')
        self.assertEqual(self.send('post', f'imports/institutions/{pk}/commit', {'version': 1, 'reason': 'Replay'}).status_code, 409)

    def test_csv_preview_expiry_other_actor_and_changed_context(self):
        pk = self.preview()
        self.client.force_login(self.a)
        self.assertEqual(self.send('post', f'imports/institutions/{pk}/commit', {'version': 1, 'reason': 'Forbidden'}).status_code, 403)
        self.client.force_login(self.officer)
        CsvImport.objects.filter(pk=pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.send('post', f'imports/institutions/{pk}/commit', {'version': 1, 'reason': 'Expired'}).status_code, 409)
        pk = self.preview()
        self.create_profile()
        self.assertEqual(self.send('post', f'imports/institutions/{pk}/commit', {'version': 1, 'reason': 'Changed context'}).status_code, 409)

    def test_csv_mid_commit_failure_is_atomic(self):
        pk = self.preview()
        original = imports.create_institution
        calls = []
        def fail_second(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise OperationalError('injected failure')
            return original(*args, **kwargs)
        with patch('obligations.imports.create_institution', side_effect=fail_second):
            response = self.send('post', f'imports/institutions/{pk}/commit', {'version': 1, 'reason': 'Rollback test'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(MasterAudit.objects.count(), 0)
        self.assertIsNone(CsvImport.objects.get(pk=pk).committed_at)

    def test_reports_scope_xlsx_formula_protection_and_kpi_unknowns(self):
        record = self.submitted()
        type(record).objects.filter(pk=record.pk).update(reference='=HYPERLINK("x")')
        self.client.force_login(self.officer)
        response = self.client.get('/api/reports/pending_verifications?download=xlsx')
        self.assertEqual(response.status_code, 200, response.content[:100])
        sheet = load_workbook(BytesIO(response.content)).active
        reference = sheet['C7']
        self.assertEqual(reference.data_type, 's')
        self.assertTrue(reference.value.startswith('='))
        self.client.force_login(self.b)
        self.assertEqual(self.client.get('/api/reports/pending_verifications').json()['rows'], [])
        end = timezone.now()
        response = self.client.get('/api/kpis', {'window_start': (end - timedelta(days=30)).isoformat(), 'window_end': end.isoformat()})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.json()['confirmed_share']['percentage_bps'])
