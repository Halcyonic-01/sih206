import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from portal.permissions import role


class SecondAuthorityTests(TestCase):
    def run_command(self, root, *args, **settings_):
        out = StringIO()
        with override_settings(BASE_DIR=Path(root), **settings_):
            call_command('seed_second_authority', *args, stdout=out)
        return out.getvalue()

    def test_creates_an_authority_with_a_saved_random_password_that_is_never_printed(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / 'data').mkdir()
            (Path(root) / 'data' / 'authority-credentials.txt').write_text('LOCAL SYNTHETIC DEMO ONLY - DO NOT COMMIT OR SHARE\nauthority: keep-me\n')
            output = self.run_command(root, '--generate-password', DEBUG=True)
            user = get_user_model().objects.get(username='authority_second')
            self.assertEqual(role(user), 'authority')
            lines = (Path(root) / 'data' / 'authority-credentials.txt').read_text().splitlines()
            self.assertEqual(lines[1], 'authority: keep-me')                       # the earlier account's line is untouched
            password = lines[2].split(': ', 1)[1]
            self.assertTrue(user.check_password(password))
            self.assertNotIn(password, output)

    def test_an_existing_account_is_never_changed_and_nothing_is_written_twice(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / 'data').mkdir()
            self.run_command(root, '--generate-password', DEBUG=True)
            before = (Path(root) / 'data' / 'authority-credentials.txt').read_text()
            self.assertIn('already exists', self.run_command(root, '--generate-password', DEBUG=True))
            self.assertEqual((Path(root) / 'data' / 'authority-credentials.txt').read_text(), before)
            self.assertEqual(get_user_model().objects.filter(username='authority_second').count(), 1)

    def test_generated_passwords_are_refused_outside_debug(self):
        with tempfile.TemporaryDirectory() as root, self.assertRaisesMessage(CommandError, 'local DEBUG'):
            self.run_command(root, '--generate-password', DEBUG=False)
        self.assertFalse(get_user_model().objects.filter(username='authority_second').exists())

    def test_interactive_password_must_match_and_be_strong(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch('portal.management.commands.seed_second_authority.getpass', side_effect=['Strong-Pass-93!x', 'different']):
                with self.assertRaisesMessage(CommandError, 'do not match'):
                    self.run_command(root)
            with mock.patch('portal.management.commands.seed_second_authority.getpass', side_effect=['123', '123']):
                with self.assertRaises(CommandError):
                    self.run_command(root)
            with mock.patch('portal.management.commands.seed_second_authority.getpass', side_effect=['Strong-Pass-93!x'] * 2):
                self.run_command(root)
            self.assertTrue(get_user_model().objects.get(username='authority_second').check_password('Strong-Pass-93!x'))
            self.assertFalse((Path(root) / 'data' / 'authority-credentials.txt').exists())
