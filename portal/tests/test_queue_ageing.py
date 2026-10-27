from datetime import date, datetime, timedelta, timezone as dt_timezone

from django.utils import timezone

from portal import services
from portal.deadlines import business_today
from portal.models import Instrument
from portal.models import AuditEvent
from portal.queue_ageing import band, submission_waits, waiting
from portal.tests.common import PortalTestCase


class BandTests(PortalTestCase):
    def test_bands_follow_the_limit(self):
        self.assertEqual([band(w, 7) for w in (0, 3, 4, 7, 8)], ['ok', 'ok', 'soon', 'soon', 'overdue'])

    def test_working_days_skip_weekends_and_holidays(self):
        info = waiting(date(2026, 10, 23), date(2026, 10, 28), 7, ['2026-10-27'])    # Fri -> Wed, Tuesday is a holiday
        self.assertEqual((info['working_days'], info['calendar_days']), (2, 5))


class QueueAgeingApiTests(PortalTestCase):
    def test_a_submitted_record_shows_how_long_it_has_waited(self):
        record = self.submitted()
        AuditEvent.objects.filter(instrument=record, action='SUBMITTED').update(created_at=timezone.now() - timedelta(days=12))
        self.client.force_login(self.officer)
        row = next(r for r in self.client.get('/api/instruments/').json()['results'] if r['id'] == record.pk)
        self.assertEqual(row['waiting']['band'], 'overdue')
        self.assertGreaterEqual(row['waiting']['calendar_days'], 12)

    def test_records_that_are_not_waiting_for_review_have_no_badge(self):
        record = self.draft()
        self.client.force_login(self.a)
        row = next(r for r in self.client.get('/api/instruments/').json()['results'] if r['id'] == record.pk)
        self.assertIsNone(row['waiting'])

    def test_submission_waits_costs_one_query_for_many_records(self):
        records = [self.submitted()]
        with self.assertNumQueries(2):  # thresholds (RuleSet), then every SUBMITTED event at once
            submission_waits(records, date(2026, 10, 27))

    def test_the_dashboard_has_a_maturity_calendar_of_current_accepted_records(self):
        record = self.submitted()
        record = services.review(self.officer, record.pk, record.version, 'accept', 'Synthetic review')
        Instrument.objects.filter(pk=record.pk).update(maturity_date=business_today() + timedelta(days=30))
        record.refresh_from_db()
        self.client.force_login(self.officer)
        body = self.client.get('/api/dashboard/').json()
        self.assertIn('maturity_calendar', body, body)
        days = {d['date']: d for d in body['maturity_calendar']}
        self.assertEqual(days[str(record.maturity_date)]['count'], 1)
        self.assertEqual(days[str(record.maturity_date)]['records'][0]['reference'], record.reference)
