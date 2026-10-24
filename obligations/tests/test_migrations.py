from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase

from portal.models import Institution, Instrument
from scripts import build_offline_demo
from scripts.setup_offline import verify_package


class InitialMigrationTests(TransactionTestCase):
    def test_upgrade_and_reverse_preserve_existing_portal_data(self):
        user = get_user_model().objects.create_user(username='synthetic-migration-user')
        institution = Institution.objects.create(code='SYNTHETIC-MIGRATION', name='Synthetic migration')
        item = Instrument.objects.create(institution=institution, created_by=user,
            reference='SYNTHETIC-FDR', bank='Synthetic bank', amount_paise=50000025,
            issue_date=date(2026, 1, 1), maturity_date=date(2027, 1, 1))
        # Use the original schema while obligations (and dependent portal
        # migrations) are reversed. Current models may reference removed columns.
        legacy_apps = MigrationExecutor(connection).loader.project_state(
            [('portal', '0004_release_workflow')]).apps
        LegacyInstrument = legacy_apps.get_model('portal', 'Instrument')
        before = list(LegacyInstrument.objects.filter(pk=item.pk).values())
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        for target in [[('obligations', None)], latest, [('obligations', None)], latest]:
            MigrationExecutor(connection).migrate(target)
            self.assertEqual(list(LegacyInstrument.objects.filter(pk=item.pk).values()), before)
            self.assertTrue(Institution.objects.filter(pk=institution.pk).exists())
        apps = MigrationExecutor(connection).loader.project_state(latest).apps
        for name in ['InstitutionProfile', 'ProgrammeApproval', 'RuleSet', 'DepositObligation']:
            self.assertEqual(apps.get_model('obligations', name).objects.count(), 0)


class OfflineSourceTests(SimpleTestCase):
    def test_package_contains_registered_app_and_migration_but_no_private_planning(self):
        with TemporaryDirectory(prefix='s1-package-') as folder:
            root = Path(folder)
            for name in build_offline_demo.FOLDERS:
                (root / name).mkdir()
            for name in build_offline_demo.FILES:
                (root / name).write_text('Synthetic package fixture', encoding='utf-8')
            # Create the registered app independently of the packager allowlist.
            app = root / 'obligations'
            (app / 'migrations').mkdir(parents=True, exist_ok=True)
            (app / 'models.py').write_text('# Synthetic model fixture')
            (app / 'migrations/0001_initial.py').write_text('# Synthetic migration fixture')
            (root / 'planning').mkdir()
            (root / 'planning/private.pdf').write_bytes(b'private fixture')
            (root / 'data').mkdir()
            (root / 'data/private.sqlite3').write_bytes(b'private fixture')
            with patch.object(build_offline_demo, 'ROOT', root), patch.object(
                    build_offline_demo, 'check_wheels', return_value=[]), patch('sys.stdout', new=StringIO()):
                destination = build_offline_demo.build(root / 'unused-wheels')
            verify_package(destination)
            with ZipFile(destination.with_suffix('.zip')) as archive:
                names = {Path(name).relative_to(destination.name).as_posix() for name in archive.namelist()}
            self.assertIn('obligations/models.py', names)
            self.assertIn('obligations/migrations/0001_initial.py', names)
            self.assertFalse(any(name.startswith(('planning/', 'data/')) for name in names))
