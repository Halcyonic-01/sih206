import csv
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from portal.deadlines import CATEGORIES
from portal.exports import spreadsheet_text
from portal.models import AuditEvent, Instrument
from portal.permissions import AUTHORITY_GROUP
from .maturity_common import MaturityTestCase


@override_settings(DEBUG=True)
class ExportTests(MaturityTestCase):
    def rows(self, query=None):
        response = self.client.get(reverse('instrument_export'), query or {})
        self.assertEqual(response.status_code, 200)
        return response, list(csv.DictReader(StringIO(response.content.decode('utf-8-sig'))))

    def test_same_scope_and_filters_as_register_for_every_role(self):
        authority = get_user_model().objects.create_user(username='export_authority')
        authority.groups.add(Group.objects.get_or_create(name=AUTHORITY_GROUP)[0])
        for user in (self.a, self.b, self.officer, authority):
            self.client.force_login(user)
            for category in CATEGORIES:
                query = {'category': category, 'as_of': '2026-10-23', 'institution': self.institution_b.pk}
                page = self.client.get(reverse('instrument_list'), query)
                response, rows = self.rows(query)
                self.assertEqual([int(row['ID']) for row in rows],
                                 [item.pk for item in page.context['instruments']])
                self.assertContains(page, 'Export this view as CSV')
                self.assertIn('no-store', response['Cache-Control'])
                self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
                self.assertIn('attachment;', response['Content-Disposition'])
                for row in rows:
                    self.assertEqual(row['Evaluation date'], '2026-10-23')
                    self.assertEqual(row['Bank verification'], 'Not verified by bank')
            _, rows = self.rows()
            if user == self.officer:
                self.assertTrue(all(row['Review status'] == 'SUBMITTED' for row in rows))

    def test_safe_strings_precision_and_csv_round_trip(self):
        item = self.records['draft']
        item.reference = '=HYPERLINK("bad")'
        item.bank = ' \t@SUM(1,2)'
        item.amount_paise = 50000025
        item.save()
        self.institution_a.name = 'Fictional, "Institute"\nSecond line'
        self.institution_a.save()
        self.client.force_login(self.a)
        _, rows = self.rows({'category': 'all'})
        row = next(row for row in rows if row['ID'] == str(item.pk))
        self.assertEqual(row['Reference'], "'" + item.reference)
        self.assertEqual(row['Bank'], "'" + item.bank)
        self.assertEqual(row['Institution'], self.institution_a.name)
        self.assertEqual(row['Amount INR'], '500000.25')
        for text in ('=1', '+1', '-1', '@X', '\tX', '\rX', '\nX', '\u2003=1', '\ufeff=1', '\x00=1'):
            self.assertEqual(spreadsheet_text(text), "'" + text)
        self.assertEqual(spreadsheet_text('Normal value'), 'Normal value')

    def test_denied_roles_anonymous_and_bad_filters(self):
        self.assertEqual(self.client.get(reverse('instrument_export')).status_code, 302)
        user = get_user_model().objects.create_user(username='unassigned_export')
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('instrument_export')).status_code, 403)
        self.client.force_login(self.a)
        for query in ({'category': 'secret'}, {'as_of': '2026-99-99'}):
            self.assertEqual(self.client.get(reverse('instrument_export'), query).status_code, 400)
        with override_settings(DEBUG=False):
            self.assertEqual(self.client.get(reverse('instrument_export'), {'as_of': '2026-10-23'}).status_code, 400)

    def test_empty_export_and_read_only(self):
        self.client.force_login(self.b)
        counts = Instrument.objects.count(), AuditEvent.objects.count()
        _, rows = self.rows({'category': 'today', 'as_of': '2026-10-23'})
        self.assertEqual(rows, [])
        self.assertEqual(counts, (Instrument.objects.count(), AuditEvent.objects.count()))
        Instrument.objects.filter(pk=self.records['seven'].pk).update(superseded_at=timezone.now())
        Instrument.objects.filter(pk=self.records['fifteen'].pk).update(released_at=timezone.now())
        self.client.force_login(self.a)
        _, history = self.rows({'category': 'all'})
        states = {int(row['ID']): row['Lifecycle'] for row in history}
        self.assertEqual(states[self.records['seven'].pk], 'Superseded')
        self.assertEqual(states[self.records['fifteen'].pk], 'Released')
        _, current = self.rows({'category': 'accepted'})
        self.assertNotIn(str(self.records['seven'].pk), [row['ID'] for row in current])
        self.assertNotIn(str(self.records['fifteen'].pk), [row['ID'] for row in current])
