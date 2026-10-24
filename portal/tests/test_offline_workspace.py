"""The offline handover must run the workspace without Node or private files."""
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.test import SimpleTestCase

from scripts import build_offline_demo
from scripts.setup_offline import verify_package


class OfflineWorkspaceTests(SimpleTestCase):
    def test_apps_and_built_workspace_are_bundled_without_private_dependencies(self):
        with TemporaryDirectory(prefix='yash-package-') as folder:
            root = Path(folder)
            expected = ('ai/migrations/0001_initial.py', 'verification/migrations/0001_initial.py',
                        'notifications/migrations/0001_initial.py', 'ai/ocr_worker.py',
                        'frontend/src/main.tsx', 'frontend/package.json',
                        'frontend/dist/records/index.html', 'frontend/dist/records/assets/pdf.worker.js')
            private = ('frontend/node_modules/private.txt', 'frontend/.env',
                       'frontend/test-results/private.txt', 'planning/private.pdf',
                       'data/demo-credentials.txt', '.env', 'ai/__pycache__/private.pyc')
            for name in (*build_offline_demo.FILES, *expected, *private):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('Synthetic fixture', encoding='utf-8')
            with patch.object(build_offline_demo, 'ROOT', root), patch.object(
                    build_offline_demo, 'check_wheels', return_value=[]), patch('sys.stdout', new=StringIO()):
                destination = build_offline_demo.build(root / 'unused')
            verify_package(destination)
            with ZipFile(destination.with_suffix('.zip')) as archive:
                names = {Path(name).relative_to(destination.name).as_posix() for name in archive.namelist()}
            self.assertTrue(set(expected).issubset(names))
            self.assertFalse(set(private).intersection(names))

    def test_missing_frontend_build_fails_before_creating_package(self):
        with TemporaryDirectory(prefix='yash-unbuilt-') as folder:
            root = Path(folder)
            (root / 'frontend').mkdir()
            with patch.object(build_offline_demo, 'ROOT', root):
                with self.assertRaisesMessage(ValueError, 'Build the frontend first'):
                    build_offline_demo.build(root / 'unused')
            self.assertFalse((root / 'dist').exists())
