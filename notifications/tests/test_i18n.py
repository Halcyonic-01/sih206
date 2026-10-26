from string import Formatter
from types import SimpleNamespace
from django.test import SimpleTestCase
from notifications.catalog import TEMPLATES, render
from notifications.i18n import HINDI, display_translations


class NotificationLanguageTests(SimpleTestCase):
    def test_every_system_template_has_hindi_with_identical_data_placeholders(self):
        self.assertEqual(set(HINDI), set(TEMPLATES))
        def fields(text):
            return {name for _, name, _, _ in Formatter().parse(text) if name}
        for name, template in TEMPLATES.items():
            for english, hindi in zip([template.subject, template.body], HINDI[name]):
                self.assertEqual(fields(english), fields(hindi), name)

    def test_display_preserves_references_dates_names_and_stored_history(self):
        context = {'reference': 'FDR/2026/A-01', 'days': 15, 'maturity_date': '2026-11-10',
                   'private_token': 'DO-NOT-EXPOSE'}
        subject, body, _, _ = render('maturity_reminder', context)
        item = SimpleNamespace(template_id='maturity_reminder', context=context, subject=subject, body=body)
        result = display_translations(item)
        self.assertIn('FDR/2026/A-01', result['hi']['subject'])
        self.assertIn('2026-11-10', result['hi']['body'])
        self.assertNotIn('DO-NOT-EXPOSE', str(result))
        self.assertEqual((item.subject, item.body), (subject, body))

    def test_unknown_or_modified_historical_messages_are_not_rewritten(self):
        item = SimpleNamespace(template_id='instrument_submitted', context={'reference': 'A'},
                               subject='A different historical message', body='Free text')
        self.assertEqual(display_translations(item), {})
        item.template_id = 'custom-message'
        self.assertEqual(display_translations(item), {})
