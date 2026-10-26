"""Real PDF validation, case/unit isolation, rollback and legacy compatibility."""
import hashlib
import json
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import OperationalError
from django.test import override_settings

from access.models import AccessLog
from casework import services
from obligations.models import ClearanceEvidence, MasterAudit
from portal.tests.common import PortalTestCase
from . import test_casework as fixtures


@override_settings(ROOT_URLCONF='config.urls', SAKSHAM_RELEASE_FACTS=fixtures.synthetic_facts,
    SAKSHAM_CLEARANCE_EVIDENCE=lambda *a: True)
class ClearanceEvidenceTests(PortalTestCase):
    setUp = fixtures.CaseworkTests.setUp
    case = fixtures.CaseworkTests.case

    def upload(self, case, unit='PGRC', version=None):
        return services.upload_clearance_evidence(self.clearance[unit], case.pk, unit,
            case.version if version is None else version, self.pdf('synthetic-clearance.pdf'))

    def test_real_pdf_decision_and_protected_view(self):
        case, item = self.upload(self.case())
        self.assertEqual(item.page_count, 1)
        self.assertEqual(item.sha256, hashlib.sha256(bytes(item.pdf)).hexdigest())
        self.assertEqual(case.clearances.get(unit='PGRC').status, 'OPEN')
        case = services.decide_clearance(self.clearance['PGRC'], case.pk, 'PGRC', case.version,
            'CLEARED', 'Reviewed synthetic file', 'PGRC/2026/TEST', item.pk)
        task = case.clearances.get(unit='PGRC')
        self.assertEqual(task.evidence_id, item.pk)
        self.assertIsNotNone(task.decided_at)
        self.client.force_login(self.authority)
        detail = self.client.get(f'/api/releases/{case.pk}').json()
        row = next(t for t in detail['clearances'] if t['unit'] == 'PGRC')
        self.assertEqual(row['evidence']['sha256'], item.sha256)
        self.assertEqual(row['reviewer'], self.clearance['PGRC'].username)
        response = self.client.get(row['evidence']['download_path'])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('no-store', response['Cache-Control'])
        self.assertTrue(AccessLog.objects.filter(object_type='clearanceevidence', object_id=item.pk).exists())
        self.assertIn(item.sha256, str(MasterAudit.objects.filter(entity='releasecase').latest('pk').after))

    def test_api_allowed_denied_stale_invalid_and_read_scope(self):
        case = self.case()
        base = f'/api/releases/{case.pk}/clearances/PGRC/evidence'
        self.client.force_login(self.clearance['PGRC'])
        response = self.client.post(base, {'version': case.version, 'document': self.pdf()})
        self.assertEqual(response.status_code, 201, response.content)
        saved = response.json()
        view = saved['evidence']['download_path']
        self.assertEqual(self.client.get(base).json()['version'], saved['version'])
        self.assertEqual(self.client.post(base, {'version': case.version, 'document': self.pdf()}).status_code, 409)
        self.assertEqual(self.client.post(base, {'version': saved['version'], 'document': SimpleUploadedFile(
            'bad.pdf', b'%PDF-not-readable\n%%EOF', content_type='application/pdf')}).status_code, 400)
        for actor in [self.a, self.b, self.clearance['VIGILANCE']]:
            self.client.force_login(actor)
            self.assertIn(self.client.get(view).status_code, [403, 404])
            self.assertIn(self.client.post(base, {'version': saved['version'], 'document': self.pdf()}).status_code, [403, 404])
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(view).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(view).status_code, 401)
        self.assertEqual(ClearanceEvidence.objects.count(), 1)

    def test_missing_foreign_or_stale_evidence_cannot_decide(self):
        case, item = self.upload(self.case(), unit='VIGILANCE')
        self.client.force_login(self.clearance['PGRC'])
        url = f'/api/releases/{case.pk}/clearances/PGRC'
        data = {'version': case.version, 'status': 'CLEARED', 'reason': 'Synthetic review', 'evidence_ref': 'PGRC/TEST'}
        self.assertEqual(self.client.post(url, json.dumps(data), content_type='application/json').status_code, 400)
        data['evidence_id'] = item.pk
        self.assertEqual(self.client.post(url, json.dumps(data), content_type='application/json').status_code, 404)
        case.refresh_from_db()
        self.assertEqual(case.clearances.get(unit='PGRC').status, 'OPEN')

    def test_upload_audit_failure_rolls_back_blob_and_version(self):
        case = self.case()
        before = case.version
        with patch('casework.services.record', side_effect=OperationalError('injected')):
            with self.assertRaises(OperationalError):
                self.upload(case)
        case.refresh_from_db()
        self.assertEqual(case.version, before)
        self.assertFalse(ClearanceEvidence.objects.exists())

    def test_api_database_and_access_log_failures_are_safe_and_atomic(self):
        case = self.case()
        self.client.force_login(self.clearance['PGRC'])
        path = f'/api/releases/{case.pk}/clearances/PGRC/evidence'
        with patch('casework.services.record', side_effect=OperationalError('private injected detail')):
            response = self.client.post(path, {'version': case.version, 'document': self.pdf()})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'private injected detail', response.content)
        self.assertFalse(ClearanceEvidence.objects.exists())
        case, item = self.upload(case)
        with patch('casework.api.log_access', side_effect=OperationalError('private log failure')):
            response = self.client.get(path + f'/{item.pk}')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'%PDF', response.content)

    def test_append_only_and_integrity_failure(self):
        case, item = self.upload(self.case())
        with self.assertRaises(ValidationError):
            item.save()
        with self.assertRaises(ValidationError):
            item.delete()
        ClearanceEvidence.objects.filter(pk=item.pk).update(pdf=b'corrupted')
        self.client.force_login(self.authority)
        url = f'/api/releases/{case.pk}/clearances/PGRC/evidence/{item.pk}'
        self.assertEqual(self.client.get(url).status_code, 503)

    def test_legacy_reference_only_requires_attestation_not_history_rewrite(self):
        case = self.case()
        task = case.clearances.get(unit='PGRC')
        task.status, task.decided_by, task.reason, task.evidence_ref = 'CLEARED', self.clearance['PGRC'], 'Old review', 'OLD/REF'
        task.save()
        self.client.force_login(self.authority)
        detail = self.client.get(f'/api/releases/{case.pk}').json()
        row = next(t for t in detail['clearances'] if t['unit'] == 'PGRC')
        self.assertEqual(row['evidence_state'], 'REFERENCE_ONLY')
        self.assertFalse(detail['actions']['can_approve'])
        case, item = self.upload(case)
        services.decide_clearance(self.clearance['PGRC'], case.pk, 'PGRC', case.version,
            'CLEARED', 'Re-attested original decision against synthetic PDF', 'PGRC/NEW', item.pk)
        task.refresh_from_db()
        self.assertEqual(task.evidence_id, item.pk)

