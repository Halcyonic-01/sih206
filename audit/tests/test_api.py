import csv
from datetime import datetime, timezone as dt_timezone
from io import StringIO

from access.models import AccessLog
from access.tests.base import StaffTestCase
from portal.models import AuditEvent, Instrument


class AuditApiBase(StaffTestCase):
    def setUp(self):
        self.submitted_record = self.submitted()          # DRAFT_CREATED + SUBMITTED by institution A
        self.draft = self.instrument(self.institution_a, self.a, Instrument.Status.DRAFT, 'PRIVATE-DRAFT')
        AuditEvent.objects.create(instrument=self.draft, actor=self.a, action='DRAFT_CREATED')
        self.other = self.instrument(self.institution_b, self.b, Instrument.Status.ACCEPTED, '=cmd|calc')
        self.review = AuditEvent.objects.create(
            instrument=self.other, actor=self.officer, action='ACCEPTED', reason='Looks fine.',
            before={'status': 'SUBMITTED', 'version': 1}, after={'status': 'ACCEPTED', 'version': 2})
        self.client.force_login(self.auditor)

    def events(self, query=''):
        response = self.client.get('/api/audit/events/' + query)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()


class AuditEventTests(AuditApiBase):
    def test_only_auditors_can_read(self):
        for user in (self.a, self.officer, self.authority, self.pgrc):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                for path in ('/api/audit/events/', f'/api/audit/events/{self.review.pk}/', '/api/audit/events/facets/',
                             '/api/audit/events/export/', '/api/audit/access-log/', '/api/audit/access-log/facets/',
                             '/api/audit/access-log/export/'):
                    self.assertEqual(self.client.get(path).status_code, 403, path)
        self.client.logout()
        self.assertEqual(self.client.get('/api/audit/events/').status_code, 401)

    def test_lists_submitted_history_newest_first_and_never_drafts(self):
        body = self.events()
        references = {row['instrument']['reference'] for row in body['results']}
        self.assertNotIn('PRIVATE-DRAFT', references)
        self.assertEqual(body['results'][0]['id'], self.review.pk)
        row = body['results'][0]
        self.assertEqual(row['actor']['username'], 'officer')
        self.assertEqual(row['instrument']['institution'], 'B')
        self.assertEqual(set(row), {'id', 'created_at', 'action', 'reason', 'instrument', 'actor'})
        self.assertNotIn('before', row)

    def test_filters(self):
        pk = self.submitted_record.pk
        self.assertEqual({r['instrument']['id'] for r in self.events(f'?instrument={pk}')['results']}, {pk})
        self.assertEqual(self.events('?q=cmd')['count'], 1)
        self.assertEqual({r['instrument']['institution'] for r in self.events('?institution=A')['results']}, {'A'})
        self.assertEqual({r['actor']['username'] for r in self.events(f'?actor={self.officer.pk}')['results']}, {'officer'})
        self.assertEqual(self.events('?actor_name=OFFI')['count'], 1)
        self.assertEqual({r['action'] for r in self.events('?action=ACCEPTED&action=SUBMITTED')['results']},
                         {'ACCEPTED', 'SUBMITTED'})

    def test_date_range_uses_the_business_timezone_and_is_inclusive(self):
        # 2026-03-01 19:00 UTC is 2026-03-02 00:30 in Asia/Kolkata.
        AuditEvent.objects.filter(pk=self.review.pk).update(created_at=datetime(2026, 3, 1, 19, 0, tzinfo=dt_timezone.utc))
        ids = lambda q: {r['id'] for r in self.events(q)['results']}  # noqa: E731
        self.assertIn(self.review.pk, ids('?date_from=2026-03-02&date_to=2026-03-02'))
        self.assertNotIn(self.review.pk, ids('?date_from=2026-03-01&date_to=2026-03-01'))
        self.assertNotIn(self.review.pk, ids('?date_from=2026-03-03'))

    def test_bad_filters_return_400_with_field_errors(self):
        response = self.client.get('/api/audit/events/?date_from=02-03-2026&instrument=abc')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'validation_error')
        response = self.client.get('/api/audit/events/?instrument=abc')
        self.assertIn('instrument', response.json()['errors'])

    def test_detail_shows_snapshots_and_computed_changes_without_the_version_counter(self):
        body = self.client.get(f'/api/audit/events/{self.review.pk}/').json()
        self.assertEqual(body['changes'], [{'field': 'status', 'before': 'SUBMITTED', 'after': 'ACCEPTED'}])
        self.assertEqual(body['before']['version'], 1)
        self.assertEqual(body['reason'], 'Looks fine.')

    def test_detail_of_a_draft_event_is_hidden(self):
        draft_event = AuditEvent.objects.get(instrument=self.draft)
        self.assertEqual(self.client.get(f'/api/audit/events/{draft_event.pk}/').status_code, 404)

    def test_facets(self):
        body = self.client.get('/api/audit/events/facets/').json()
        self.assertIn('ACCEPTED', body['actions'])
        self.assertIn('SUBMITTED', body['actions'])
        self.assertEqual({a['username'] for a in body['actors']}, {'institution_a', 'officer'})
        self.assertEqual(body['institutions'], ['A', 'B'])

    def test_pagination(self):
        body = self.events('?page_size=1')
        self.assertEqual((body['count'] > 1, len(body['results']), body['page_size']), (True, 1, 1))


class AccessLogTests(AuditApiBase):
    def setUp(self):
        super().setUp()
        self.rows = [
            AccessLog.objects.create(user=self.officer, username='officer', action='DOCUMENT_DOWNLOAD',
                                     object_type='document', object_id=5, ip_address='10.0.0.1'),
            AccessLog.objects.create(user=self.a, username='institution_a', action='EXPORT',
                                     object_type='instrument_register', ip_address='10.0.0.2'),
            AccessLog.objects.create(username='nobody', action='LOGIN_FAILED', ip_address='10.0.0.3'),
        ]

    def logs(self, query=''):
        response = self.client.get('/api/audit/access-log/' + query)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_lists_and_filters(self):
        self.assertGreaterEqual(self.logs()['count'], 3)
        self.assertEqual({r['username'] for r in self.logs('?action=DOCUMENT_DOWNLOAD')['results']}, {'officer'})
        self.assertEqual(self.logs('?username=nobo')['count'], 1)
        self.assertEqual(self.logs('?object_type=document&object_id=5')['count'], 1)
        self.assertEqual(self.logs('?ip=10.0.0.2')['count'], 1)
        self.assertEqual(self.logs(f'?user={self.a.pk}&action=EXPORT')['count'], 1)
        self.assertEqual(self.logs('?action=EXPORT&action=LOGIN_FAILED')['count'], 2)

    def test_facets(self):
        body = self.client.get('/api/audit/access-log/facets/').json()
        self.assertIn('LOGIN_FAILED', body['actions'])
        self.assertIn('document', body['object_types'])

    def test_failed_login_rows_never_contain_secrets(self):
        row = self.logs('?action=LOGIN_FAILED')['results'][0]
        self.assertNotIn('password', ' '.join(str(v) for v in row.values()).lower())


class ExportTests(AuditApiBase):
    def read(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Disposition'].startswith('attachment'))
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        return list(csv.reader(StringIO(response.content.decode('utf-8-sig'))))

    def test_audit_export_is_filtered_neutralises_formulas_and_is_logged_once(self):
        rows = self.read(self.client.get('/api/audit/events/export/?institution=B'))
        self.assertEqual(rows[0][:4], ['Event ID', 'Time', 'Institution', 'Reference'])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][3], "'=cmd|calc")
        logged = AccessLog.objects.filter(action=AccessLog.EXPORT, object_type='audit_events')
        self.assertEqual(logged.count(), 1)
        self.assertIn('rows=1', logged.get().detail)
        self.assertEqual(AccessLog.objects.filter(action=AccessLog.DOWNLOAD).count(), 0)

    def test_access_log_export_is_logged(self):
        rows = self.read(self.client.get('/api/audit/access-log/export/'))
        self.assertEqual(rows[0][:3], ['ID', 'Time', 'Username'])
        self.assertEqual(AccessLog.objects.filter(action=AccessLog.EXPORT, object_type='access_log').count(), 1)
