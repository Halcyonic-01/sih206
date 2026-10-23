"""Lock the independently labeled synthetic rule cases to the implementation."""
from datetime import date
import json

from django.conf import settings

from portal.models import Document, Instrument
from portal.validation import CHECKS_VERSION, run_checks
from .common import PortalTestCase


class EvaluationContractTests(PortalTestCase):
    def test_frozen_synthetic_ground_truth(self):
        dataset = json.loads((settings.BASE_DIR / 'evaluation/cases.json').read_text(encoding='utf-8'))
        self.assertEqual(len(dataset['cases']), 24)
        for case in dataset['cases']:
            with self.subTest(case=case['id']):
                # Clear document rows before their protected parent rows.
                Document.objects.all().delete()
                Instrument.objects.all().delete()
                fields = dict(bank=case.get('bank', 'Fictional Bank'), reference=case.get('reference', 'FDR-001'),
                              amount_paise=50000000, issue_date=date(2026, 1, 1), maturity_date=date(2027, 1, 1),
                              created_by=self.a, institution=self.institution_a)
                item = Instrument.objects.create(**fields)
                if 'other' in case:
                    other = dict(fields)
                    other.update({key: value for key, value in case['other'].items() if key != 'institution'})
                    if case['other'].get('institution') == 'other':
                        other['institution'] = self.institution_b
                    Instrument.objects.create(**other)
                if case['document'] != 'none':
                    Document.objects.create(instrument=item, kind=case['document'], file='synthetic.pdf',
                                            original_name='synthetic.pdf', size_bytes=0, sha256='0' * 64,
                                            uploaded_by=self.a)
                self.assertEqual({finding.code for finding in run_checks(item)}, set(case['expected']))

    def test_rule_revision_does_not_rewrite_old_snapshots(self):
        item = self.submitted()
        event = item.audit_events.get(action='SUBMITTED')
        event.after['checks_version'] = 'technical-v1'
        event.save(update_fields=['after'])
        before = event.after.copy()
        run_checks(item)
        event.refresh_from_db()
        self.assertEqual(event.after, before)
        self.assertEqual(CHECKS_VERSION, 'technical-v2')
