from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from portal import releases, services
from portal.models import AuditEvent, Instrument
from portal.permissions import (OFFICER_GROUP, clearance_unit, require_auditor, require_clearance,
                                role, scoped_access_logs, scoped_audit_events, scoped_documents,
                                scoped_instruments, scoped_release_requests)
from .base import StaffTestCase


class RoleResolutionTests(StaffTestCase):
    def test_every_role_resolves(self):
        expected = {self.a: 'institution', self.officer: 'officer', self.authority: 'authority',
                    self.pgrc: 'clearance', self.auditor: 'auditor'}
        for user, name in expected.items():
            with self.subTest(user=user.username):
                self.assertEqual(role(user), name)

    def test_two_roles_fail_closed(self):
        self.auditor.groups.add(Group.objects.get(name=OFFICER_GROUP))
        self.assertIsNone(role(self.auditor))
        with self.assertRaises(PermissionDenied):
            scoped_instruments(self.auditor)

    def test_inactive_user_has_no_role(self):
        self.auditor.is_active = False
        self.assertIsNone(role(self.auditor))

    def test_clearance_unit_lookup_and_fail_closed(self):
        self.assertEqual(clearance_unit(self.pgrc), 'PGRC')
        self.assertEqual(require_clearance(self.vigilance, 'VIGILANCE'), 'VIGILANCE')
        with self.assertRaises(PermissionDenied):
            require_clearance(self.pgrc, 'VIGILANCE')
        with self.assertRaises(PermissionDenied):
            clearance_unit(self.unassigned_clearance)
        with self.assertRaises(PermissionDenied):
            clearance_unit(self.officer)

    def test_require_auditor(self):
        require_auditor(self.auditor)
        for user in (self.a, self.officer, self.authority, self.pgrc):
            with self.assertRaises(PermissionDenied):
                require_auditor(user)


class ScopeTests(StaffTestCase):
    def setUp(self):
        self.draft = self.instrument(self.institution_a, self.a, Instrument.Status.DRAFT, 'DRAFT-A')
        self.submitted = self.instrument(self.institution_a, self.a, reference='SUB-A')
        self.other = self.instrument(self.institution_b, self.b, Instrument.Status.ACCEPTED, 'ACC-B')
        self.with_release = self.instrument(self.institution_b, self.b, Instrument.Status.ACCEPTED, 'REL-B')
        self.release_for(self.with_release, self.b)

    def refs(self, user):
        return set(scoped_instruments(user).values_list('reference', flat=True))

    def test_institution_sees_only_its_own(self):
        self.assertEqual(self.refs(self.a), {'DRAFT-A', 'SUB-A'})
        self.assertEqual(self.refs(self.b), {'ACC-B', 'REL-B'})

    def test_staff_never_see_drafts(self):
        for user in (self.officer, self.authority, self.auditor):
            with self.subTest(user=user.username):
                self.assertEqual(self.refs(user), {'SUB-A', 'ACC-B', 'REL-B'})

    def test_clearance_sees_only_instruments_with_a_release_case(self):
        self.assertEqual(self.refs(self.pgrc), {'REL-B'})

    def test_documents_and_release_requests_follow_instrument_scope(self):
        self.assertEqual(scoped_release_requests(self.pgrc).count(), 1)
        self.assertEqual(scoped_release_requests(self.a).count(), 0)
        self.assertEqual(scoped_release_requests(self.auditor).count(), 1)
        self.assertEqual(scoped_documents(self.a).count(), 0)

    def test_audit_events_follow_scope(self):
        for instrument in (self.draft, self.submitted, self.other):
            AuditEvent.objects.create(instrument=instrument, actor=self.officer, action='X')
        count = lambda user: scoped_audit_events(user).count()  # noqa: E731
        self.assertEqual(count(self.a), 2)       # its own draft event and submitted event
        self.assertEqual(count(self.b), 1)
        self.assertEqual(count(self.auditor), 2)  # drafts stay private even from the auditor
        self.assertEqual(count(self.pgrc), 0)

    def test_access_log_is_auditor_only(self):
        self.assertEqual(scoped_access_logs(self.auditor).count(), 0)
        for user in (self.a, self.officer, self.authority, self.pgrc):
            with self.assertRaises(PermissionDenied):
                scoped_access_logs(user)


class ReadOnlyRoleTests(StaffTestCase):
    """The auditor and clearance units can read but never change an institution's or officer's records."""

    def setUp(self):
        self.record = self.instrument(self.institution_a, self.a, reference='SUB-A')

    def test_workflow_services_reject_new_roles(self):
        for user in (self.auditor, self.pgrc):
            with self.subTest(user=user.username):
                with self.assertRaises(PermissionDenied):
                    services.submit(user, self.record.pk, self.record.version)
                with self.assertRaises(PermissionDenied):
                    services.review(user, self.record.pk, self.record.version, 'accept', 'No.')
                with self.assertRaises(PermissionDenied):
                    releases.request_release(user, self.record.pk, self.record.version, 'No.')
                with self.assertRaises(PermissionDenied):
                    releases.decide_release(user, self.record.pk, 1, self.record.version, 'approve', 'No.')

    def test_legacy_write_endpoints_return_403(self):
        for user in (self.auditor, self.pgrc):
            self.client.force_login(user)
            with self.subTest(user=user.username):
                for name in ('instrument_review', 'observation_add', 'instrument_submit'):
                    response = self.client.post(reverse(name, args=[self.record.pk]), {'version': 1})
                    self.assertEqual(response.status_code, 403, name)
                self.assertEqual(self.client.get(reverse('instrument_create')).status_code, 403)

    def test_auditor_can_read_register_and_detail(self):
        self.client.force_login(self.auditor)
        self.assertContains(self.client.get(reverse('instrument_list') + '?category=all'), 'SUB-A')
        self.assertEqual(self.client.get(reverse('instrument_detail', args=[self.record.pk])).status_code, 200)

    def test_clearance_cannot_open_an_instrument_without_a_release_case(self):
        self.client.force_login(self.pgrc)
        self.assertEqual(self.client.get(reverse('instrument_detail', args=[self.record.pk])).status_code, 404)

    def test_api_me_reports_role_and_unit(self):
        self.client.force_login(self.pgrc)
        body = self.client.get('/api/auth/me/').json()
        self.assertEqual((body['role'], body['unit']), ('clearance', 'PGRC'))
        self.client.force_login(self.auditor)
        body = self.client.get('/api/auth/me/').json()
        self.assertEqual((body['role'], body['unit']), ('auditor', None))
        self.client.force_login(self.unassigned_clearance)
        self.assertEqual(self.client.get('/api/auth/me/').json()['unit'], None)
