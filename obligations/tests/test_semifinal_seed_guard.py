"""CI must explicitly opt into a disposable SQLite release rehearsal."""
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class RehearsalSeedGuardTests(SimpleTestCase):
    @override_settings(DEBUG=True, SETTINGS_MODULE='config.settings')
    def test_custom_profile_requires_explicit_disposable_confirmation(self):
        with self.assertRaises(CommandError):
            call_command('seed_semifinal_release')
        # Reach the existing seed implementation only after explicit confirmation.
        with patch('obligations.management.commands.seed_semifinal_release.Instrument.objects.get',
                   side_effect=LookupError('synthetic source not seeded')) as source:
            with self.assertRaises(LookupError):
                call_command('seed_semifinal_release', confirm_disposable=True)
            source.assert_called_once_with(reference='PS7-RELEASE-READY')

    @override_settings(DEBUG=False)
    def test_confirmation_cannot_bypass_debug_guard(self):
        with self.assertRaises(CommandError):
            call_command('seed_semifinal_release', confirm_disposable=True)

    @override_settings(DEBUG=True, SETTINGS_MODULE='config.rehearsal_settings')
    def test_postgres_is_refused_even_with_confirmation(self):
        with patch.dict(settings.DATABASES['default'], ENGINE='django.db.backends.postgresql'):
            with self.assertRaises(CommandError):
                call_command('seed_semifinal_release', confirm_disposable=True)
