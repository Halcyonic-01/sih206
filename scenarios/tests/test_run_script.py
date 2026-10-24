"""run.sh / run.ps1 behaviour that the review build depends on (K3/K8)."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.test import SimpleTestCase

from scripts import run_portal


class RunScriptTests(SimpleTestCase):
    def test_production_mode_signs_with_the_env_file_key(self):
        """Commands run by hand (deliver_bank_requests, shell) must sign links with the server's key."""
        with TemporaryDirectory() as folder:
            env_file = Path(folder) / '.env'
            env_file.write_text('DJANGO_SECRET_KEY=from-env-file-key\n', encoding='utf-8')
            environ = {key: value for key, value in os.environ.items() if key != 'DJANGO_SECRET_KEY'}
            with mock.patch.object(run_portal, 'ENV_FILE', env_file), mock.patch.dict(os.environ, environ, clear=True), \
                    mock.patch.object(run_portal, 'prod_secret', return_value='generated-key'):
                self.assertEqual(run_portal.django_env(prod=True)['DJANGO_SECRET_KEY'], 'from-env-file-key')
                env_file.write_text('DJANGO_SECRET_KEY=\n', encoding='utf-8')
                self.assertEqual(run_portal.django_env(prod=True)['DJANGO_SECRET_KEY'], 'generated-key')

    def test_scheduler_delivers_bank_requests_with_the_email_retries(self):
        with TemporaryDirectory() as folder, mock.patch.object(run_portal, 'ROOT', Path(folder)), \
                mock.patch.object(run_portal, 'background_command', return_value=1) as command:
            run_portal.scheduler_tick({}, {'next_send': 0, 'next_rules': 0})
        self.assertEqual([call.args[0] for call in command.call_args_list],
                         ['send_notifications', 'deliver_bank_requests', 'run_due_rules'])
