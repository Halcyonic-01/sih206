from io import StringIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .maturity_common import AS_OF, MaturityTestCase


@override_settings(DEBUG=True)
class DashboardTests(MaturityTestCase):
    def dashboard(self, **parameters):
        return self.client.get(reverse('dashboard'), {'as_of': AS_OF.isoformat(), **parameters})

    def listing(self, category, **parameters):
        return self.client.get(reverse('instrument_list'), {
            'category': category, 'as_of': AS_OF.isoformat(), **parameters})

    def test_institution_counts_are_scoped_and_accepted_subsets_are_separate(self):
        self.client.force_login(self.a)
        page = self.dashboard()
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.context['counts'], {
            'all': 9, 'pending': 1, 'accepted': 6, 'approaching': 3, 'today': 1, 'matured': 1})
        self.assertContains(page, 'Demo evaluation date: 2026-10-23')
        self.assertContains(page, 'not a determination of regulatory noncompliance')

    def test_officer_can_see_accepted_records_but_not_private_drafts(self):
        self.client.force_login(self.officer)
        page = self.dashboard()
        self.assertEqual(page.context['counts'], {
            'all': 9, 'pending': 1, 'accepted': 7, 'approaching': 4, 'today': 1, 'matured': 1})
        listing = self.listing('all')
        ids = {row.pk for row in listing.context['instruments']}
        self.assertNotIn(self.records['draft'].pk, ids)
        self.assertNotIn(self.records['other_draft'].pk, ids)
        self.assertIn(self.records['later'].pk, ids)

    def test_default_register_behavior_is_preserved_for_both_roles(self):
        self.client.force_login(self.officer)
        page = self.client.get(reverse('instrument_list'))
        self.assertEqual(list(page.context['instruments']), [self.records['pending']])
        self.client.force_login(self.a)
        page = self.client.get(reverse('instrument_list'))
        self.assertEqual(page.context['record_count'], 9)

    def test_every_dashboard_card_count_matches_its_filtered_list_and_keeps_demo_date(self):
        for user in (self.a, self.b, self.officer):
            self.client.force_login(user)
            dashboard = self.dashboard()
            for card in dashboard.context['cards']:
                with self.subTest(user=user.username, category=card['category']):
                    query = parse_qs(urlparse(card['url']).query)
                    self.assertEqual(query['as_of'], ['2026-10-23'])
                    page = self.client.get(card['url'])
                    self.assertEqual(page.status_code, 200)
                    self.assertEqual(page.context['record_count'], card['count'])
                    self.assertEqual(len(page.context['instrument_rows']), card['count'])

    def test_filtered_date_boundaries_are_exact_and_categories_do_not_overlap(self):
        self.client.force_login(self.a)
        expected = {'approaching': {'seven', 'fifteen', 'thirty'}, 'today': {'today'}, 'matured': {'past'}}
        for category, keys in expected.items():
            page = self.listing(category)
            self.assertEqual({record.pk for record in page.context['instruments']},
                             {self.records[key].pk for key in keys})
        page = self.listing('approaching')
        self.assertNotContains(page, self.records['later'].reference)
        self.assertNotContains(page, self.records['other'].reference)

    def test_dashboard_and_command_due_counts_agree(self):
        self.client.force_login(self.officer)
        counts = self.dashboard().context['counts']
        output = StringIO()
        call_command('due_actions', as_of='2026-10-23', stdout=output)
        due_count = sum(counts[category] for category in ('approaching', 'today', 'matured'))
        self.assertIn(f'Total due instruments: {due_count}', output.getvalue())

    def test_dashboard_and_register_require_login_and_valid_role(self):
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)
        outsider = get_user_model().objects.create_user(username='no-role')
        self.client.force_login(outsider)
        self.assertEqual(self.dashboard().status_code, 403)
        self.assertEqual(self.listing('all').status_code, 403)

    def test_forged_institution_filter_cannot_expand_scope(self):
        self.client.force_login(self.a)
        page = self.listing('all', institution=self.institution_b.pk)
        self.assertEqual(page.context['record_count'], 9)
        self.assertNotContains(page, self.records['other'].reference)
        page = self.dashboard(institution=self.institution_b.pk)
        self.assertEqual(page.context['counts']['accepted'], 6)

    def test_invalid_category_and_date_fail_safely(self):
        self.client.force_login(self.a)
        self.assertEqual(self.listing('unknown').status_code, 400)
        for raw in ('2026-02-30', 'bad', '20261023', '<script>'):
            with self.subTest(raw=raw):
                self.assertEqual(self.dashboard(as_of=raw).status_code, 400)
                self.assertEqual(self.listing('all', as_of=raw).status_code, 400)

    @override_settings(DEBUG=False)
    def test_browser_date_overrides_disabled_outside_local_demo_mode(self):
        self.client.force_login(self.a)
        self.assertEqual(self.dashboard().status_code, 400)
        self.assertEqual(self.listing('all').status_code, 400)
        page = self.client.get(reverse('dashboard'))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'name="as_of"')

    def test_default_dashboard_date_uses_business_timezone_without_demo_label(self):
        self.client.force_login(self.a)
        with patch('portal.deadlines.business_today', return_value=AS_OF):
            page = self.client.get(reverse('dashboard'))
        self.assertContains(page, 'Current business date: 2026-10-23')
        self.assertNotContains(page, 'Demo evaluation date:')
        for card in page.context['cards']:
            self.assertNotIn('as_of=', card['url'])

    def test_report_gets_are_read_only_and_have_no_store_headers(self):
        self.client.force_login(self.a)
        with CaptureQueriesContext(connection) as queries:
            dashboard = self.dashboard()
            listing = self.listing('approaching')
        writes = [query['sql'] for query in queries if query['sql'].lstrip().upper().startswith(
            ('INSERT', 'UPDATE', 'DELETE', 'REPLACE'))]
        self.assertEqual(writes, [])
        self.assertIn('no-store', dashboard['Cache-Control'])
        self.assertIn('no-store', listing['Cache-Control'])

    @override_settings(REMINDER_DAYS=(7,))
    def test_configuration_changes_dashboard_and_filter_consistently(self):
        self.client.force_login(self.a)
        self.assertEqual(self.dashboard().context['counts']['approaching'], 1)
        self.assertEqual(self.listing('approaching').context['record_count'], 1)

    def test_detail_shows_actual_business_date_and_does_not_change_review_status(self):
        self.client.force_login(self.a)
        record = self.records['past']
        with patch('portal.views.business_today', return_value=AS_OF):
            page = self.client.get(reverse('instrument_detail', args=[record.pk]))
        self.assertContains(page, 'Matured 1 day(s) ago')
        self.assertContains(page, 'Current business date: 2026-10-23')
        self.assertContains(page, 'Not independently bank-verified')
        record.refresh_from_db()
        self.assertEqual(record.status, 'ACCEPTED')
