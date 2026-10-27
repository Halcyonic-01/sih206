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
                         ['send_weekly_digests', 'send_notifications', 'deliver_bank_requests', 'run_due_rules'])

    def test_weekly_digest_checked_even_after_daily_rules_have_run(self):
        with TemporaryDirectory() as folder, mock.patch.object(run_portal, 'ROOT', Path(folder)), \
                mock.patch.object(run_portal, 'background_command', return_value=0) as command:
            state = {'next_send': 0, 'next_rules': 0}
            run_portal.scheduler_tick({}, state)
            command.reset_mock()
            state['next_send'] = 0
            run_portal.scheduler_tick({}, state)
            self.assertEqual(command.call_args_list, [
                mock.call('send_weekly_digests', {}, '--queue'),
                mock.call('send_notifications', {}), mock.call('deliver_bank_requests', {})])

    def test_background_command_passes_digest_queue_argument_without_shell(self):
        result = mock.Mock(returncode=0, stdout='disabled', stderr='')
        with mock.patch.object(run_portal.subprocess, 'run', return_value=result) as runner, \
                mock.patch.object(run_portal, 'say'):
            self.assertEqual(run_portal.background_command('send_weekly_digests', {}, '--queue'), 0)
        self.assertEqual(runner.call_args.args[0][-2:], ['send_weekly_digests', '--queue'])
        self.assertNotIn('shell', runner.call_args.kwargs)


class SeededDatabaseTests(SimpleTestCase):
    """Saved demo passwords belong to one database; switching databases must say so instead of failing sign-in."""

    def test_identity_never_contains_the_password(self):
        identity = run_portal.database_identity({'DATABASE_URL': 'postgresql://user:secret-pass@db.example.org:5432/app',
                                                 'DATABASE_SCHEMA': 'portal_app'})
        self.assertEqual(identity, 'postgresql db.example.org/app schema portal_app')
        self.assertNotIn('secret', identity)
        self.assertEqual(run_portal.database_identity({}), 'sqlite data/portal.sqlite3')
        self.assertEqual(run_portal.database_identity({'DATABASE_URL': 'postgresql://u:p@h/db',
                                                       'DATABASE_BACKEND': 'sqlite'}), 'sqlite data/portal.sqlite3')

    def test_switching_database_warns_and_first_run_records_the_current_one(self):
        with TemporaryDirectory() as folder:
            data = Path(folder)
            credentials, seeded = data / 'demo-credentials.txt', data / '.seeded-database'
            credentials.write_text('officer: x\n', encoding='utf-8')
            with mock.patch.object(run_portal, 'CREDENTIALS', credentials), \
                    mock.patch.object(run_portal, 'SEEDED_FOR', seeded), \
                    mock.patch.object(run_portal, 'say') as say, \
                    mock.patch.object(run_portal, 'database_identity', return_value='sqlite data/portal.sqlite3'):
                run_portal.check_seeded_database()
                self.assertEqual(seeded.read_text().strip(), 'sqlite data/portal.sqlite3')
                say.assert_not_called()
                seeded.write_text('postgresql other/db schema portal_app\n', encoding='utf-8')
                run_portal.check_seeded_database()
            self.assertIn('Signing in with them will fail', say.call_args.args[0])
