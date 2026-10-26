from unittest.mock import MagicMock

from django.apps import apps
from django.test import SimpleTestCase

from audit import append_only


def editor(vendor):
    schema_editor = MagicMock()
    schema_editor.connection.vendor = vendor
    schema_editor.quote_name.side_effect = lambda name: f'"{name}"'
    return schema_editor


class AppendOnlyTriggerSqlTests(SimpleTestCase):
    def test_sqlite_is_left_to_the_application_guards(self):
        for action in (append_only.install, append_only.remove):
            schema_editor = editor('sqlite')
            action(apps, schema_editor)
            schema_editor.execute.assert_not_called()

    def test_postgresql_gets_one_function_and_a_trigger_per_evidence_table(self):
        schema_editor = editor('postgresql')
        append_only.install(apps, schema_editor)
        statements = [call.args[0] for call in schema_editor.execute.call_args_list]
        self.assertIn('CREATE OR REPLACE FUNCTION "forbid_append_only_change"()', statements[0])
        # The % signs in RAISE are PostgreSQL placeholders: the driver must not try to fill them.
        self.assertIsNone(schema_editor.execute.call_args_list[0].kwargs['params'])
        created = [s for s in statements if s.startswith('CREATE TRIGGER')]
        self.assertEqual(len(created), 4)
        for table in ('portal_auditevent', 'audit_auditseal', 'access_accesslog', 'verification_verificationevidence'):
            self.assertTrue(any(f'ON "{table}"' in s and 'BEFORE UPDATE OR DELETE' in s and 'FOR EACH ROW' in s
                                for s in created), table)

    def test_remove_drops_the_triggers_then_the_function(self):
        schema_editor = editor('postgresql')
        append_only.remove(apps, schema_editor)
        statements = [call.args[0] for call in schema_editor.execute.call_args_list]
        self.assertEqual(len([s for s in statements if s.startswith('DROP TRIGGER')]), 4)
        self.assertTrue(statements[-1].startswith('DROP FUNCTION'))

    def test_report_flags_missing_triggers_and_powerful_roles(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [None, ('O',), ('O',), ('O',), (True,), (4,)]
        findings = append_only.report(cursor, 'portal_app', apps)
        self.assertEqual([ok for ok, _ in findings], [False, True, True, True, False, False])
        self.assertIn('MISSING', findings[0][1])
        self.assertIn('superuser', findings[4][1])
        self.assertIn('owns 4 of the 4', findings[5][1])
