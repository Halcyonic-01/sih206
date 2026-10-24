"""Y1 storage boundaries; no policy, PDF parsing or verification is inferred."""
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from obligations.models import DepositObligation
from portal.models import Document, Institution, Instrument
from portal.services import event, snapshot


class RecordFieldTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username='synthetic-y1-user')
        cls.institution = Institution.objects.create(code='Y1-A', name='Synthetic A')
        cls.other = Institution.objects.create(code='Y1-B', name='Synthetic B')
        cls.obligation = DepositObligation.objects.create(institution=cls.institution)

    def item(self, **changes):
        return Instrument(**(dict(institution=self.institution, created_by=self.owner,
            reference='SYNTHETIC-Y1', bank='Synthetic bank', amount_paise=50000025,
            issue_date=date(2026, 1, 1), maturity_date=date(2027, 1, 1)) | changes))

    def test_legacy_defaults_do_not_invent_evidence(self):
        item = self.item()
        item.full_clean()
        item.save()
        item.refresh_from_db()
        self.assertEqual(item.mode, Instrument.Mode.FDR)
        self.assertEqual(item.verification_level, Instrument.VerificationLevel.DECLARED)
        self.assertIsNone(item.obligation_id)
        self.assertIsNone(item.lien_marked)
        self.assertEqual((item.ifsc, item.branch, item.holder_names, item.utr), ('', '', '', ''))

    def test_multiple_holdings_can_link_to_same_protected_obligation(self):
        for mode in Instrument.Mode.values:
            item = self.item(mode=mode, obligation=self.obligation, reference=f'SYNTHETIC-{mode}')
            item.full_clean()
            item.save()
        self.assertEqual(self.obligation.instruments.count(), 3)
        with self.assertRaises(ProtectedError):
            self.obligation.delete()

    def test_cross_institution_obligation_rejected(self):
        item = self.item(institution=self.other, obligation=self.obligation)
        with self.assertRaises(ValidationError) as error:
            item.full_clean()
        self.assertIn('obligation', error.exception.message_dict)

    def test_invalid_choices_rejected_even_by_direct_database_write(self):
        for values in [{'mode': 'OTHER'}, {'verification_level': 'AUTO_VERIFIED'}]:
            with self.subTest(values=values):
                with self.assertRaises(ValidationError):
                    self.item(**values).full_clean()
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.item(**values).save()

    def test_ifsc_checks_format_without_claiming_issuer_exists(self):
        self.item(ifsc='TEST0123456').full_clean()
        for value in ['BAD', 'test0123456', 'TEST1123456', 'TEST0123456\n']:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.item(ifsc=value).full_clean()

    def test_lien_unknown_false_and_true_remain_distinct(self):
        for lien in [None, False, True]:
            with self.subTest(lien=lien):
                item = self.item(lien_marked=lien)
                item.full_clean()
                item.save()
                item.refresh_from_db()
                self.assertIs(item.lien_marked, lien)

    def test_document_kinds_and_unknown_page_count_preserve_storage_contract(self):
        item = self.item()
        item.save()
        for kind in Document.Kind.values:
            document = Document(instrument=item, kind=kind, file='synthetic/y1.pdf',
                original_name='synthetic.pdf', size_bytes=20, sha256='0' * 64, uploaded_by=self.owner)
            document.full_clean()
            document.save()
            document.refresh_from_db()
            self.assertIsNone(document.page_count)
        document.page_count = 2
        document.full_clean()
        document.save()
        for count in [0, -1]:
            document.page_count = count
            with self.subTest(count=count), self.assertRaises(ValidationError):
                document.full_clean()
            with self.assertRaises(IntegrityError), transaction.atomic():
                Document.objects.filter(pk=document.pk).update(page_count=count)

    def test_new_audit_snapshots_include_fields_without_rewriting_old_events(self):
        item = self.item(obligation=self.obligation, mode=Instrument.Mode.RTGS,
                         ifsc='TEST0123456', branch='Synthetic branch', holder_names='Synthetic holder',
                         utr='SYNTHETIC-UTR', lien_marked=False)
        item.full_clean()
        item.save()
        previous = {'reference': item.reference, 'checks_version': 'technical-v1'}
        old = item.audit_events.create(actor=self.owner, action='LEGACY', after=previous)
        event(item, self.owner, 'DRAFT_CREATED', {})
        current = item.audit_events.get(action='DRAFT_CREATED').after
        self.assertEqual(current['obligation_id'], self.obligation.pk)
        for field in ['mode', 'ifsc', 'branch', 'holder_names', 'utr', 'lien_marked', 'verification_level']:
            self.assertEqual(current[field], getattr(item, field))
        old.refresh_from_db()
        self.assertEqual(old.after, previous)
        self.assertEqual(snapshot(item)['verification_level'], Instrument.VerificationLevel.DECLARED)
