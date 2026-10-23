from datetime import date, timedelta

from portal.models import Instrument
from .common import PortalTestCase

AS_OF = date(2026, 10, 23)


class MaturityTestCase(PortalTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.records = {}
        for key, days, status, institution, user in [
            ('past', -1, 'ACCEPTED', cls.institution_a, cls.a),
            ('today', 0, 'ACCEPTED', cls.institution_a, cls.a),
            ('seven', 7, 'ACCEPTED', cls.institution_a, cls.a),
            ('fifteen', 15, 'ACCEPTED', cls.institution_a, cls.a),
            ('thirty', 30, 'ACCEPTED', cls.institution_a, cls.a),
            ('later', 31, 'ACCEPTED', cls.institution_a, cls.a),
            ('pending', 7, 'SUBMITTED', cls.institution_a, cls.a),
            ('changes', -1, 'CHANGES_REQUESTED', cls.institution_a, cls.a),
            ('draft', -1, 'DRAFT', cls.institution_a, cls.a),
            ('other', 7, 'ACCEPTED', cls.institution_b, cls.b),
            ('other_draft', -1, 'DRAFT', cls.institution_b, cls.b),
        ]:
            cls.records[key] = Instrument.objects.create(
                institution=institution, created_by=user, reference=f'M3-{key.upper()}',
                bank='Fictional Maturity Bank', amount_paise=10000000,
                issue_date=date(2026, 1, 1), maturity_date=AS_OF + timedelta(days=days), status=status,
            )
