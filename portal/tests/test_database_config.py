from contextlib import nullcontext
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command, CommandError
from django.db import OperationalError
from django.test import SimpleTestCase
from config.envfile import load_env_file

from config.database import database_config, private_schema
from config.legacy_notifications import has_legacy_notifications, archive_legacy_notifications
from scripts import build_offline_demo

SYNTHETIC_URL = 'postgresql://postgres.synthetic:fake%40password@aws-0-test.pooler.supabase.com:5432/postgres'


class DatabaseConfigurationTests(SimpleTestCase):
    def test_sqlite_default_explicit_offline_mode_and_tests_remain_local(self):
        for env, testing in (({}, False), ({'DATABASE_URL': SYNTHETIC_URL, 'DATABASE_BACKEND': 'sqlite'}, False),
                             ({'DATABASE_URL': SYNTHETIC_URL}, True)):
            config = database_config(Path('/synthetic'), env, testing=testing)
            self.assertEqual(config['ENGINE'], 'django.db.backends.sqlite3')
            self.assertEqual(config['NAME'], Path('/synthetic/data/portal.sqlite3'))

    def test_pooler_credentials_are_decoded_and_tls_private_schema_are_required(self):
        config = database_config(Path('.'), {'DATABASE_URL': SYNTHETIC_URL})
        self.assertEqual(config['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(config['USER'], 'postgres.synthetic')
        self.assertEqual(config['PASSWORD'], 'fake@password')
        self.assertEqual(config['OPTIONS']['sslmode'], 'require')
        self.assertEqual(config['OPTIONS']['options'], '-c search_path=portal_app')
        self.assertEqual(config['CONN_MAX_AGE'], 0)
        self.assertTrue(config['DISABLE_SERVER_SIDE_CURSORS'])

    def test_invalid_urls_do_not_expose_credentials_or_fall_back_to_sqlite(self):
        for url in ('https://user:fake-password@example.invalid', 'postgresql://user:fake-password@/db',
                    'postgresql://user:fake-password@localhost:bad/db', 'postgresql://user@localhost/db',
                    SYNTHETIC_URL+'?options=untrusted', SYNTHETIC_URL+'?sslmode=require&sslmode=disable',
                    'postgresql://[bad:fake-password/db'):
            with self.subTest(url_type=url.split(':')[0]):
                with self.assertRaises(ImproperlyConfigured) as raised:
                    database_config(Path('.'), {'DATABASE_URL': url})
                self.assertNotIn('fake-password', str(raised.exception))
        with self.assertRaises(ImproperlyConfigured):
            database_config(Path('.'), {'DATABASE_BACKEND': 'postgresql'})

    def test_plaintext_ssl_modes_and_transaction_pooler_are_rejected(self):
        for mode in ('disable', 'allow', 'prefer', ''):
            with self.assertRaises(ImproperlyConfigured):
                database_config(Path('.'), {'DATABASE_URL': SYNTHETIC_URL+'?sslmode='+mode})
        with self.assertRaisesMessage(ImproperlyConfigured, 'Session pooler'):
            database_config(Path('.'), {'DATABASE_URL': SYNTHETIC_URL.replace(':5432/', ':6543/')})

    def test_verified_certificate_and_encoded_password_supported(self):
        config = database_config(Path('.'), {'DATABASE_URL': SYNTHETIC_URL+'?sslmode=verify-full',
            'DATABASE_SSL_ROOT_CERT': '/synthetic/ca.crt', 'DATABASE_SCHEMA': 'portal_demo'})
        self.assertEqual(config['OPTIONS']['sslmode'], 'verify-full')
        self.assertEqual(config['OPTIONS']['sslrootcert'], '/synthetic/ca.crt')
        self.assertEqual(config['OPTIONS']['options'], '-c search_path=portal_demo')

    def test_system_schemas_and_search_path_injection_are_rejected(self):
        for value in ('public', 'auth', 'storage', 'pg_catalog', 'information_schema', 'a,public',
                      'a;drop schema public', '"portal"', 'Uppercase', '', 'a'*64):
            with self.assertRaises(ImproperlyConfigured):
                private_schema(value)

    def test_dotenv_preserves_literal_password_and_environment_precedence(self):
        with TemporaryDirectory() as directory, patch.dict('os.environ', {}, clear=True):
            file = Path(directory)/'.env'
            file.write_text('DATABASE_URL="postgresql://user:fake${DO_NOT_EXPAND}@localhost/db"\n', encoding='utf-8')
            load_env_file(file)
            import os
            self.assertIn('${DO_NOT_EXPAND}', os.environ['DATABASE_URL'])
            os.environ['DATABASE_URL'] = SYNTHETIC_URL
            load_env_file(file)
            self.assertEqual(os.environ['DATABASE_URL'], SYNTHETIC_URL)

    def test_offline_wheel_validation_normalizes_distribution_names(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'requirements.txt').write_text('typing-extensions==4.16.0\n', encoding='utf-8')
            for name, version in [('typing_extensions', '4.16.0'), ('pip', build_offline_demo.PIP_VERSION)]:
                with ZipFile(root/f'{name}-{version}.whl', 'w') as archive:
                    archive.writestr(f'{name}-{version}.dist-info/METADATA', f'Name: {name}\nVersion: {version}\n')
            with patch.object(build_offline_demo, 'ROOT', root):
                self.assertEqual(len(build_offline_demo.check_wheels(root)), 2)


class SupabaseCheckCommandTests(SimpleTestCase):
    def connection(self, fetchone):
        connection = MagicMock(vendor='postgresql')
        connection.ops.quote_name.side_effect = lambda value: '"'+value+'"'
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = fetchone
        cursor.fetchall.return_value = [('anon',), ('authenticated',), ('service_role',)]
        return connection, cursor

    def test_missing_connection_is_clear(self):
        with self.assertRaisesMessage(CommandError, 'DATABASE_URL'):
            call_command('check_supabase', stdout=StringIO())

    def test_connection_check_is_read_only_and_missing_schema_does_not_migrate(self):
        connection, cursor = self.connection([(False,)])
        with patch('portal.management.commands.check_supabase.connection', connection), patch(
                'portal.management.commands.check_supabase.call_command') as migrate:
            with self.assertRaisesMessage(CommandError, 'Private schema is absent'):
                call_command('check_supabase', stdout=StringIO())
            migrate.assert_not_called()
        self.assertFalse(any('CREATE' in call.args[0] for call in cursor.execute.call_args_list))

    def test_initialize_only_creates_private_schema_and_migration_is_explicit(self):
        connection, cursor = self.connection([(False,), ('portal_app',)])
        with patch('portal.management.commands.check_supabase.connection', connection), patch(
                'portal.management.commands.check_supabase.transaction.atomic', return_value=nullcontext()), patch(
                'portal.management.commands.check_supabase.call_command') as migrate:
            call_command('check_supabase', initialize=True, migrate=True, stdout=StringIO())
            migrate.assert_called_once()
        sql = '\n'.join(call.args[0] for call in cursor.execute.call_args_list)
        self.assertIn('CREATE SCHEMA IF NOT EXISTS "portal_app"', sql)
        self.assertIn('REVOKE ALL ON SCHEMA "portal_app"', sql)
        self.assertNotIn('DROP ', sql)
        self.assertNotIn('CREATE SCHEMA IF NOT EXISTS "public"', sql)

    def test_connection_errors_are_redacted(self):
        connection = MagicMock(vendor='postgresql')
        connection.cursor.side_effect = OperationalError('secret connection URI and password')
        with patch('portal.management.commands.check_supabase.connection', connection):
            with self.assertRaises(CommandError) as error:
                call_command('check_supabase', stdout=StringIO())
        self.assertNotIn('secret connection URI', str(error.exception))


class LegacyOutboxDetectionTests(SimpleTestCase):
    def connection(self, columns=None):
        from types import SimpleNamespace
        connection = MagicMock(vendor='postgresql')
        connection.introspection.get_table_list.return_value = [] if columns is None else [SimpleNamespace(name='notifications_notification')]
        connection.introspection.get_table_description.return_value = [SimpleNamespace(name=name) for name in columns or []]
        return connection

    def test_absent_and_shared_tables_need_no_bridge(self):
        self.assertFalse(has_legacy_notifications(self.connection()))
        self.assertFalse(has_legacy_notifications(self.connection(['idempotency_key', 'recipient_key', 'template_id'])))

    def test_prototype_is_detected_and_unknown_schema_is_not_modified(self):
        self.assertTrue(has_legacy_notifications(self.connection(['key', 'template', 'recipient_id'])))
        with self.assertRaisesMessage(ValueError, 'Unrecognized'):
            has_legacy_notifications(self.connection(['unrecognized']))

    def test_bridge_rejects_non_postgresql(self):
        with self.assertRaisesMessage(ValueError, 'PostgreSQL-only'):
            archive_legacy_notifications(MagicMock(vendor='sqlite'))
