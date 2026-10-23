import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class ConfigurationTests(SimpleTestCase):
    def load(self, **values):
        environment = {**os.environ, 'DJANGO_DEBUG': 'true', 'MAX_UPLOAD_MB': '10',
                       'BUSINESS_TIMEZONE': 'Asia/Kolkata', 'REMINDER_DAYS': '30,15,7', **values}
        return subprocess.run([sys.executable, '-c', 'import config.settings'], cwd=settings.BASE_DIR,
                              env=environment, capture_output=True, text=True, timeout=20)

    def test_invalid_limits_and_timezone_fail_at_startup(self):
        for value in ('0', '-1', 'not-an-integer'):
            result = self.load(MAX_UPLOAD_MB=value)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('MAX_UPLOAD_MB must be a positive integer', result.stderr)
        for value in ('Invalid/Zone', '', '/absolute/path'):
            result = self.load(BUSINESS_TIMEZONE=value)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('BUSINESS_TIMEZONE must be a valid IANA timezone', result.stderr)

    def test_valid_configuration_and_missing_non_debug_secret(self):
        self.assertEqual(self.load().returncode, 0)
        result = self.load(DJANGO_DEBUG='false', DJANGO_SECRET_KEY='')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Set DJANGO_SECRET_KEY', result.stderr)
