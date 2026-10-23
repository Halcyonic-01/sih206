from datetime import date, datetime, timedelta, timezone
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command, CommandError
from django.db import connection
from django.test import SimpleTestCase, override_settings
from django.test.utils import CaptureQueriesContext

from portal.deadlines import business_today, classify_maturity, due_actions, parse_as_of, reminder_days
from portal.models import Institution, Instrument
from .maturity_common import AS_OF, MaturityTestCase


class MaturityCalculationTests(SimpleTestCase):
    def test_threshold_boundaries(self):
        for offset, code, band in [(-1, 'matured', None), (0, 'today', None),
                                   (1, 'approaching', 7), (7, 'approaching', 7),
                                   (8, 'approaching', 15), (15, 'approaching', 15),
                                   (16, 'approaching', 30), (30, 'approaching', 30),
                                   (31, 'future', None)]:
            with self.subTest(offset=offset):
                result = classify_maturity(AS_OF + timedelta(days=offset), AS_OF)
                self.assertEqual((result.code, result.reminder_band, result.days_remaining), (code, band, offset))
                self.assertTrue(result.label)
                self.assertTrue(result.action)

    def test_business_date_uses_configured_timezone_at_utc_boundary(self):
        now = datetime(2026, 10, 22, 20, 0, tzinfo=timezone.utc)
        with patch('portal.deadlines.timezone.now', return_value=now):
            with override_settings(TIME_ZONE='Asia/Kolkata'):
                self.assertEqual(business_today(), date(2026, 10, 23))
            with override_settings(TIME_ZONE='UTC'):
                self.assertEqual(business_today(), date(2026, 10, 22))

    def test_leap_day_and_year_boundary_use_date_arithmetic(self):
        self.assertEqual(classify_maturity(date(2028, 3, 1), date(2028, 2, 28)).days_remaining, 2)
        self.assertEqual(classify_maturity(date(2027, 1, 1), date(2026, 12, 31)).days_remaining, 1)

    def test_as_of_is_strict_and_does_not_change_the_clock(self):
        self.assertEqual(parse_as_of('2026-10-23'), AS_OF)
        for raw in ('2026-02-30', '20261023', '2026-W43-5', '23/10/2026', 'bad', ' 2026-10-23'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_as_of(raw)
        with patch('portal.deadlines.business_today', return_value=AS_OF):
            self.assertEqual(parse_as_of(None), AS_OF)
            self.assertEqual(parse_as_of(''), AS_OF)

    @override_settings(REMINDER_DAYS=(3, 10, 3))
    def test_configurable_windows_are_sorted_deduplicated_and_used(self):
        self.assertEqual(reminder_days(), (10, 3))
        self.assertEqual(classify_maturity(AS_OF + timedelta(days=3), AS_OF).reminder_band, 3)
        self.assertEqual(classify_maturity(AS_OF + timedelta(days=4), AS_OF).reminder_band, 10)
        self.assertEqual(classify_maturity(AS_OF + timedelta(days=11), AS_OF).code, 'future')

    def test_invalid_thresholds_fail_explicitly(self):
        for configuration in ((), (0,), (-1,), ('7',), (True,)):
            with self.subTest(configuration=configuration), override_settings(REMINDER_DAYS=configuration):
                with self.assertRaises(ImproperlyConfigured):
                    reminder_days()


class DueActionTests(MaturityTestCase):
    def report(self, **options):
        output = StringIO()
        call_command('due_actions', as_of=AS_OF.isoformat(), stdout=output, **options)
        return output.getvalue()

    def test_command_includes_exact_due_records_and_excludes_nonaccepted_and_day31(self):
        output = self.report()
        self.assertIn('Evaluation date: 2026-10-23 (explicit --as-of evaluation)', output)
        for key in ('past', 'today', 'seven', 'fifteen', 'thirty', 'other'):
            self.assertIn(self.records[key].reference + '\t', output)
        for key in ('later', 'pending', 'changes', 'draft', 'other_draft'):
            self.assertNotIn(self.records[key].reference + '\t', output)
        self.assertIn('Total due instruments: 6', output)
        self.assertIn('Matured: 1 | Matures today: 1 | Approaching maturity: 4', output)
        self.assertIn('no notifications sent or stored', output)

    def test_command_and_ui_helper_share_classification_and_order(self):
        rows = due_actions(Instrument.objects.all(), AS_OF)
        references = [row['instrument'].reference for row in rows]
        self.assertEqual(references, [self.records[key].reference for key in
                                     ('past', 'today', 'seven', 'other', 'fifteen', 'thirty')])
        self.assertEqual([row['maturity'].code for row in rows],
                         ['matured', 'today', 'approaching', 'approaching', 'approaching', 'approaching'])

    def test_command_institution_scope_and_unknown_code(self):
        output = self.report(institution='A')
        self.assertIn('Total due instruments: 5', output)
        self.assertNotIn(self.records['other'].reference, output)
        with self.assertRaises(CommandError):
            self.report(institution='DOES-NOT-EXIST')

    def test_repeated_command_is_read_only_and_identical(self):
        with CaptureQueriesContext(connection) as queries:
            first, second = self.report(), self.report()
        self.assertEqual(first, second)
        writes = [query['sql'] for query in queries if query['sql'].lstrip().upper().startswith(
            ('INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'DROP', 'ALTER'))]
        self.assertEqual(writes, [])

    def test_default_report_uses_current_business_date(self):
        output = StringIO()
        with patch('portal.deadlines.business_today', return_value=AS_OF):
            call_command('due_actions', stdout=output)
        self.assertIn('2026-10-23 (current business date)', output.getvalue())
        self.assertIn('Total due instruments: 6', output.getvalue())

    def test_empty_institution_has_a_valid_zero_report(self):
        Institution.objects.create(code='EMPTY', name='Empty Fictional Institution')
        output = self.report(institution='EMPTY')
        self.assertIn('Total due instruments: 0', output)
        self.assertIn('Matured: 0 | Matures today: 0 | Approaching maturity: 0', output)

    def test_invalid_date_produces_friendly_command_error(self):
        with self.assertRaisesMessage(CommandError, 'YYYY-MM-DD'):
            call_command('due_actions', as_of='2026-02-30', stdout=StringIO())

    def test_date_max_does_not_overflow_report(self):
        output = StringIO()
        call_command('due_actions', as_of='9999-12-31', stdout=output)
        self.assertIn('Total due instruments: 7', output.getvalue())

    def test_output_keeps_user_controlled_fields_on_one_line(self):
        Instrument.objects.filter(pk=self.records['past'].pk).update(reference='REF\nSECOND\tCOLUMN\x1bESC')
        output = self.report()
        self.assertIn('REF SECOND COLUMN ESC\t', output)
        self.assertNotIn('\x1b', output)

    @override_settings(REMINDER_DAYS=(7,))
    def test_custom_threshold_is_used_by_report(self):
        output = self.report()
        self.assertIn('Total due instruments: 4', output)
        self.assertNotIn(self.records['fifteen'].reference, output)
