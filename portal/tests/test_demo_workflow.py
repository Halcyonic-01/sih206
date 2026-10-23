from io import StringIO
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings

from portal import services
from portal.deadlines import dashboard_counts
from portal.management.commands.seed_scenarios import AS_OF
from portal.models import AuditEvent, Document, Instrument, ReleaseRequest
from portal.permissions import scoped_instruments
from portal.validation import run_checks
from scripts.setup_offline import verify_package


@override_settings(DEBUG=True)
class ScenarioTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix='fdr-demo-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(settings.BASE_DIR / 'fixtures', self.root / 'fixtures')
        (self.root / 'data').mkdir()
        override = override_settings(BASE_DIR=self.root, MEDIA_ROOT=self.root / 'data' / 'documents')
        override.enable()
        self.addCleanup(override.disable)
        self.output = StringIO()
        call_command('seed_demo', generate_password=True, stdout=self.output)
        call_command('seed_demo', authority_only=True, generate_password=True, stdout=self.output)

    def seed(self):
        call_command('seed_scenarios', stdout=self.output)
        return json.loads((self.root / 'data/scenarios-v1.json').read_text())['instruments']

    def test_scenarios_cover_workflows_scope_and_exact_maturity_boundaries(self):
        ids = self.seed()
        self.assertEqual(Instrument.objects.count(), 17)
        self.assertEqual(Document.objects.count(), 18)
        item = lambda key: Instrument.objects.get(pk=ids[key])
        self.assertEqual(item('valid').status, 'SUBMITTED')
        discrepancy = item('discrepancy')
        self.assertEqual(discrepancy.status, 'CHANGES_REQUESTED')
        observation = discrepancy.observations.get()
        self.assertEqual((observation.page_number, observation.severity), (1, 'BLOCKING'))
        self.assertEqual(run_checks(item('duplicate_proposal'))[0].code, 'POSSIBLE_DUPLICATE')
        self.assertTrue(item('renewal_old').is_superseded)
        self.assertEqual(item('renewal_successor').predecessor_id, ids['renewal_old'])
        self.assertTrue(item('release_completed').is_released)
        for outcome in ('pending', 'approved', 'rejected', 'completed'):
            self.assertEqual(item('release_' + outcome).release_requests.get().status, outcome.upper())
        completion = item('release_completed').release_requests.get()
        self.assertEqual(completion.completion_evidence.kind, Document.Kind.RELEASE_EVIDENCE)
        for doc in Document.objects.all():
            self.assertTrue(Path(doc.file.path).is_file())
        owner = item('valid').created_by
        self.assertNotIn(ids['other_institution'], scoped_instruments(owner).values_list('pk', flat=True))
        self.assertEqual(dashboard_counts(scoped_instruments(owner), AS_OF),
                         {'all': 16, 'pending': 1, 'accepted': 11, 'approaching': 7, 'today': 1, 'matured': 1})

    def test_repeat_preserves_subsequent_work_and_credentials(self):
        ids = self.seed()
        item = Instrument.objects.get(pk=ids['valid'])
        from django.contrib.auth import get_user_model
        services.review(get_user_model().objects.get(username='officer'), item.pk, item.version,
                        'accept', 'Demo presenter subsequently accepted the valid record.')
        before = (Instrument.objects.count(), AuditEvent.objects.count(), ReleaseRequest.objects.count())
        credentials = (self.root / 'data/demo-credentials.txt').read_bytes()
        self.assertEqual(self.seed(), ids)
        self.assertEqual(before, (Instrument.objects.count(), AuditEvent.objects.count(), ReleaseRequest.objects.count()))
        self.assertEqual(credentials, (self.root / 'data/demo-credentials.txt').read_bytes())
        item.refresh_from_db()
        self.assertEqual(item.status, 'ACCEPTED')

    def test_failed_scenario_transaction_removes_created_documents(self):
        with patch('portal.management.commands.seed_scenarios.services.review', side_effect=RuntimeError('Injected failure')):
            with self.assertRaises(RuntimeError):
                self.seed()
        self.assertEqual(Instrument.objects.count(), 0)
        self.assertEqual(Document.objects.count(), 0)
        self.assertEqual(list((self.root / 'data/documents').rglob('*.pdf')), [])
        self.assertFalse((self.root / 'data/scenarios-v1.json').exists())

    def test_manifest_collision_and_production_fail_closed(self):
        ids = self.seed()
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            self.seed()
        (self.root / 'data/scenarios-v1.json').unlink()
        with self.assertRaises(CommandError):
            self.seed()
        self.assertEqual(Instrument.objects.count(), len(ids))


class PackageIntegrityTests(TestCase):
    def test_checksum_and_traversal_rejected(self):
        import hashlib
        with TemporaryDirectory(prefix='package-test-') as directory:
            root = Path(directory)
            file = root / 'source.py'
            file.write_bytes(b'content')
            manifest = {'format': 1, 'python': '3.12', 'files': {'source.py': hashlib.sha256(b'content').hexdigest()}}
            index = root / 'package-manifest.json'
            index.write_text(json.dumps(manifest))
            verify_package(root)
            file.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                verify_package(root)
            manifest['files'] = {'../outside.py': 'unused'}
            index.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                verify_package(root)
