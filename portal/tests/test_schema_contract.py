"""Keep integrated feature endpoints in the published, strictly valid API contract."""
import json
import os
from pathlib import Path
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class IntegratedSchemaTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        result = subprocess.run(
            [sys.executable, 'manage.py', 'spectacular', '--validate', '--fail-on-warn',
             '--format', 'openapi-json'], cwd=Path(settings.BASE_DIR),
            env={**os.environ, 'DATABASE_BACKEND': 'sqlite'},
            capture_output=True, text=True, timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        if result.returncode:
            raise AssertionError(f'Strict schema validation failed: {result.stderr}')
        cls.schema = json.loads(result.stdout)

    def test_feature_routes_have_responses_and_unique_operation_ids(self):
        paths = self.schema['paths']
        for path in ('/api/instruments/', '/api/instruments/{id}/', '/api/dashboard/',
                     '/api/verification/statements/', '/api/documents/{id}/ai-extract/',
                     '/api/documents/{id}/ocr/', '/api/releases', '/api/releases/{id}',
                     '/api/clearance-tasks', '/api/public/verify/{token}',
                     '/api/obligations/{id}/proof-receipts'):
            self.assertIn(path, list(paths))
        ids = [operation['operationId'] for path in paths.values()
               for method, operation in path.items()
               if method in ('get', 'post', 'patch', 'put', 'delete')]
        self.assertEqual(len(ids), len(set(ids)))

    def test_record_actions_use_the_correct_upload_and_renewal_inputs(self):
        paths = self.schema['paths']
        upload = paths['/api/instruments/{id}/documents/']['post']['requestBody']['content']
        self.assertIn('multipart/form-data', upload)
        ref = upload['multipart/form-data']['schema']['$ref'].rsplit('/', 1)[-1]
        component = self.schema['components']['schemas'][ref]
        self.assertEqual(component['properties']['document']['format'], 'binary')
        self.assertIn('kind', component['required'])
        renew = paths['/api/instruments/{id}/renew/']['post']['requestBody']['content']['application/json']['schema']
        ref = renew['$ref'].rsplit('/', 1)[-1]
        self.assertIn('maturity_date', self.schema['components']['schemas'][ref]['properties'])
        patch = paths['/api/instruments/{id}/']['patch']['requestBody']['content']['application/json']['schema']
        ref = patch['$ref'].rsplit('/', 1)[-1]
        self.assertIn('version', self.schema['components']['schemas'][ref]['required'])

    def test_downloads_and_no_body_ocr_are_documented(self):
        paths = self.schema['paths']
        for path in ('/api/documents/{id}/download/', '/api/releases/{id}/letter'):
            self.assertIn('application/pdf', paths[path]['get']['responses']['200']['content'])
        self.assertNotIn('requestBody', paths['/api/documents/{id}/ocr/']['post'])
        statement = paths['/api/verification/statements/']['post']['requestBody']['content']['multipart/form-data']['schema']
        self.assertIn('versions', statement['properties'])

    def test_clearance_contract_includes_required_protected_evidence(self):
        paths = self.schema['paths']
        root = '/api/releases/{id}/clearances/{unit}'
        decision = paths[root]['post']['requestBody']['content']['application/json']['schema']
        self.assertIn('evidence_id', decision['required'])
        upload = paths[root + '/evidence']['post']['requestBody']['content']['multipart/form-data']['schema']
        self.assertIn('document', upload['required'])
        self.assertEqual(upload['properties']['document']['format'], 'binary')
        self.assertIn('201', paths[root + '/evidence']['post']['responses'])
        download = paths[root + '/evidence/{evidence_id}']['get']
        self.assertIn('application/pdf', download['responses']['200']['content'])
        self.assertTrue(download['security'])
