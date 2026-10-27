from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError

from access.models import RegionAssignment
from notifications import recipients
from obligations.models import InstitutionProfile
from portal.models import Instrument
from portal.permissions import OFFICER_GROUP, scoped_documents, scoped_instruments
from portal.tests.common import PortalTestCase


class RegionScopeTests(PortalTestCase):
    def setUp(self):
        super().setUp()
        for institution, region, number in ((self.institution_a, 'North', 1), (self.institution_b, 'South', 2)):
            InstitutionProfile.objects.create(institution=institution, aicte_id=f'AICTE-{number}', trust_name='Trust',
                institution_type='PRIVATE', region=region, state='X', contact_email=f'c{number}@example.invalid')
        self.record_a = self.submitted()
        self.client.force_login(self.b)
        response = self.client.post('/api/instruments/', {**self.payload(reference='B-1'), 'document': self.pdf()})
        self.assertEqual(response.status_code, 201, response.content)
        self.record_b = Instrument.objects.get(reference='B-1')
        records = __import__('portal.services', fromlist=['x'])
        records.submit(self.b, self.record_b.pk, self.record_b.version)
        self.south = get_user_model().objects.create_user(username='officer-south')
        self.south.groups.add(Group.objects.get(name=OFFICER_GROUP))
        self.head = get_user_model().objects.create_user(username='head-south')
        self.head.groups.add(Group.objects.get(name=OFFICER_GROUP))
        RegionAssignment.objects.create(user=self.south, region='south')
        RegionAssignment.objects.create(user=self.head, region='South', is_head=True)

    def test_an_officer_without_a_region_keeps_national_scope(self):
        references = set(scoped_instruments(self.officer).values_list('reference', flat=True))
        self.assertEqual(references, {self.record_a.reference, 'B-1'})

    def test_a_regional_officer_sees_only_their_region_everywhere(self):
        self.assertEqual(list(scoped_instruments(self.south).values_list('reference', flat=True)), ['B-1'])
        self.assertEqual({d.instrument_id for d in scoped_documents(self.south)}, {self.record_b.pk})
        self.client.force_login(self.south)
        self.assertEqual(self.client.get(f'/api/instruments/{self.record_a.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/instruments/{self.record_b.pk}/').status_code, 200)
        document = self.record_a.documents.first()
        self.assertEqual(self.client.get(f'/api/documents/{document.pk}/download/').status_code, 404)
        listing = self.client.get('/api/instruments/').json()
        self.assertEqual([r['reference'] for r in listing['results']], ['B-1'])

    def test_the_institution_list_is_restricted_too(self):
        from obligations.services import scoped_institutions
        self.assertEqual(set(scoped_institutions(self.south).values_list('code', flat=True)), {'B'})
        self.assertEqual(set(scoped_institutions(self.officer).values_list('code', flat=True)), {'A', 'B'})

    def test_an_institution_without_a_profile_is_invisible_to_a_regional_officer(self):
        InstitutionProfile.objects.filter(institution=self.institution_b).delete()
        self.assertEqual(scoped_instruments(self.south).count(), 0)

    def test_notifications_go_to_national_officers_and_the_matching_region_only(self):
        north = {u.username for u in recipients.officers(self.institution_a)}
        south = {u.username for u in recipients.officers(self.institution_b)}
        self.assertEqual(north, {'officer'})
        self.assertEqual(south, {'officer', 'officer-south', 'head-south'})
        self.assertEqual({u.username for u in recipients.officers()}, {'officer', 'officer-south', 'head-south'})

    def test_escalations_go_to_the_regional_head_and_fall_back_to_the_officers(self):
        self.assertEqual([u.username for u in recipients.regional_heads(self.institution_b)], ['head-south'])
        self.assertEqual({u.username for u in recipients.regional_heads(self.institution_a)}, {'officer'})

    def test_assign_region_command(self):
        call_command('assign_region', 'officer', 'North', '--head', stdout=StringIO())
        self.assertEqual(list(scoped_instruments(self.officer).values_list('reference', flat=True)), [self.record_a.reference])
        out = StringIO()
        call_command('assign_region', 'officer', 'north', '--remove', stdout=out)
        self.assertIn('national', out.getvalue())
        with self.assertRaisesMessage(CommandError, 'Only officer'):
            call_command('assign_region', 'institution_a', 'North', stdout=StringIO())
