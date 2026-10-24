from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from access.models import UnitAssignment
from portal.models import Instrument, ReleaseRequest
from portal.permissions import AUDITOR_GROUP, AUTHORITY_GROUP, CLEARANCE_GROUP
from portal.tests.common import PortalTestCase

PASSWORD = 'Testing-Only-7jS!'


class StaffTestCase(PortalTestCase):
    """PortalTestCase (institutions A and B, officer) plus authority, clearance units and an auditor."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        User = get_user_model()
        authority_group = Group.objects.create(name=AUTHORITY_GROUP)
        clearance_group = Group.objects.create(name=CLEARANCE_GROUP)
        auditor_group = Group.objects.create(name=AUDITOR_GROUP)
        cls.authority = User.objects.create_user(username='authority', password=PASSWORD)
        cls.authority.groups.add(authority_group)
        cls.pgrc = User.objects.create_user(username='clearance_pgrc', password=PASSWORD)
        cls.pgrc.groups.add(clearance_group)
        UnitAssignment.objects.create(user=cls.pgrc, unit=UnitAssignment.Unit.PGRC)
        cls.vigilance = User.objects.create_user(username='clearance_vigilance', password=PASSWORD)
        cls.vigilance.groups.add(clearance_group)
        UnitAssignment.objects.create(user=cls.vigilance, unit=UnitAssignment.Unit.VIGILANCE)
        cls.unassigned_clearance = User.objects.create_user(username='clearance_nounit', password=PASSWORD)
        cls.unassigned_clearance.groups.add(clearance_group)
        cls.auditor = User.objects.create_user(username='auditor', password=PASSWORD)
        cls.auditor.groups.add(auditor_group)

    def instrument(self, institution, owner, status=Instrument.Status.SUBMITTED, reference='REF-1'):
        return Instrument.objects.create(
            institution=institution, reference=reference, bank='Fictional Bank', amount_paise=5_000_000,
            issue_date=date(2026, 1, 1), maturity_date=date(2027, 1, 1), status=status, created_by=owner)

    def release_for(self, instrument, requester):
        return ReleaseRequest.objects.create(instrument=instrument, requested_by=requester, reason='Release.')
