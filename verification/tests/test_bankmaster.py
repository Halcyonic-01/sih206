from datetime import date
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from portal import services
from portal.tests.common import PortalTestCase
from verification.bankmaster import same_name
from verification.models import BankBranch, BankSuccession
from verification.services import checks

FIXTURES = Path(settings.BASE_DIR) / 'fixtures'


class NameTests(SimpleTestCase):
    def test_loose_name_comparison(self):
        self.assertTrue(same_name('State Bank of India', 'STATE BANK OF INDIA'))
        self.assertTrue(same_name('Canara Bank', 'Canara Bank Ltd.'))
        self.assertFalse(same_name('Punjab National Bank', 'Canara Bank'))
        self.assertFalse(same_name('', 'Canara Bank'))


class LoaderTests(PortalTestCase):
    def test_directory_loads_updates_and_skips_bad_rows(self):
        out = StringIO()
        call_command('load_ifsc_directory', str(FIXTURES / 'ifsc-directory-sample.csv'), '--directory-version', '2026-10', stdout=out)
        self.assertIn('3 added, 0 updated, 0 skipped', out.getvalue())
        call_command('load_ifsc_directory', str(FIXTURES / 'ifsc-directory-sample.csv'), '--directory-version', '2026-11', stdout=StringIO())
        self.assertEqual(BankBranch.objects.get(ifsc='SBIN0000691').directory_version, '2026-11')
        bad = Path(self.make_tmp('IFSC,BANK\nBAD,Some Bank\nSBIN0000001,State Bank of India\n'))
        out = StringIO()
        call_command('load_ifsc_directory', str(bad), '--directory-version', 'x', stdout=out, stderr=StringIO())
        self.assertIn('1 added', out.getvalue())
        self.assertIn('1 skipped', out.getvalue())
        with self.assertRaises(CommandError):
            call_command('load_ifsc_directory', str(bad), '--directory-version', 'x', '--strict', stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command('load_ifsc_directory', str(self.make_tmp('A,B\n1,2\n')), '--directory-version', 'x')

    def make_tmp(self, text):
        import tempfile
        handle = tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False)
        handle.write(text)
        handle.close()
        self.addCleanup(Path(handle.name).unlink)
        return handle.name

    def test_successions_load_unverified_unless_confirmed(self):
        call_command('load_bank_successions', str(FIXTURES / 'bank-successions-draft.csv'), stdout=StringIO())
        self.assertEqual(BankSuccession.objects.count(), 8)
        self.assertFalse(BankSuccession.objects.filter(verified=True).exists())
        call_command('load_bank_successions', str(FIXTURES / 'bank-successions-draft.csv'), '--verified', stdout=StringIO())
        self.assertEqual(BankSuccession.objects.filter(verified=True).count(), 8)


@override_settings(VERIFICATION_ISSUER_PREFIXES=('SBIN',))
class IssuerCheckTests(PortalTestCase):
    def record(self, **fields):
        item = self.draft()
        for key, value in fields.items():
            setattr(item, key, value)
        item.save()
        return item

    def codes(self, item):
        return {f['code']: f for f in checks(self.officer, item)}

    def test_without_a_directory_the_old_prefix_rule_applies(self):
        self.assertIn('ISSUER_UNCONFIRMED', self.codes(self.record(ifsc='SBIN0000691', bank='State Bank of India')))
        self.assertIn('ISSUER_UNKNOWN', self.codes(self.record(ifsc='XXXX0000001')))

    def test_a_listed_ifsc_names_the_bank_and_branch(self):
        call_command('load_ifsc_directory', str(FIXTURES / 'ifsc-directory-sample.csv'), '--directory-version', 'v1', stdout=StringIO())
        found = self.codes(self.record(ifsc='SBIN0000691', bank='State Bank of India', branch='Parliament Street'))
        self.assertEqual(set(found), {'ISSUER_UNCONFIRMED'})
        self.assertIn('Parliament Street', found['ISSUER_UNCONFIRMED']['explanation'])
        self.assertIn('v1', found['ISSUER_UNCONFIRMED']['explanation'])

    def test_name_branch_unlisted_and_unknown_bank_are_flagged(self):
        call_command('load_ifsc_directory', str(FIXTURES / 'ifsc-directory-sample.csv'), '--directory-version', 'v1', stdout=StringIO())
        found = self.codes(self.record(ifsc='SBIN0000691', bank='Punjab National Bank', branch='Somewhere Else'))
        self.assertTrue({'ISSUER_NAME_MISMATCH', 'ISSUER_BRANCH_MISMATCH'} <= set(found))
        self.assertIn('IFSC_NOT_IN_DIRECTORY', self.codes(self.record(ifsc='SBIN0999999', bank='State Bank of India')))
        self.assertIn('ISSUER_UNKNOWN', self.codes(self.record(ifsc='ZZZZ0000001', bank='Unknown')))

    def test_a_merged_bank_is_not_treated_as_unknown_only_when_the_mapping_is_verified(self):
        call_command('load_ifsc_directory', str(FIXTURES / 'ifsc-directory-sample.csv'), '--directory-version', 'v1', stdout=StringIO())
        call_command('load_bank_successions', str(FIXTURES / 'bank-successions-draft.csv'), stdout=StringIO())
        self.assertIn('ISSUER_UNKNOWN', self.codes(self.record(ifsc='SYNB0000123', bank='Syndicate Bank')))
        call_command('load_bank_successions', str(FIXTURES / 'bank-successions-draft.csv'), '--verified', stdout=StringIO())
        merged = self.codes(self.record(ifsc='SYNB0000123', bank='Syndicate Bank'))
        self.assertEqual(set(merged), {'ISSUER_MERGED'})
        self.assertIn('Canara Bank', merged['ISSUER_MERGED']['explanation'])

    def test_a_listed_predecessor_ifsc_mentions_the_merger_and_accepts_either_name(self):
        BankBranch.objects.create(ifsc='SYNB0000001', bank_code='SYNB', bank_name='Syndicate Bank', branch='Manipal', directory_version='v1')
        BankSuccession.objects.create(old_code='SYNB', new_code='CNRB', old_name='Syndicate Bank', new_name='Canara Bank',
                                      effective_date=date(2020, 4, 1), verified=True)
        found = self.codes(self.record(ifsc='SYNB0000001', bank='Canara Bank', branch='Manipal'))
        self.assertEqual(set(found), {'ISSUER_UNCONFIRMED', 'ISSUER_MERGED'})


class RenewalReasonTests(PortalTestCase):
    def renew(self, **extra):
        record = self.submitted()
        record = services.review(self.officer, record.pk, record.version, 'accept', 'Synthetic review')
        self.client.force_login(self.a)
        payload = self.payload(reference='RENEWED-1', issue_date='2027-01-01', maturity_date='2028-01-01', version=record.version) | extra
        return record, self.client.post(f'/api/instruments/{record.pk}/renew/', payload, content_type='application/json')

    def test_the_reason_is_recorded_and_shown_on_both_sides_of_the_link(self):
        record, response = self.renew(renewal_reason='BANK_MERGER_REPLACEMENT', renewal_note='Syndicate Bank became Canara Bank')
        self.assertEqual(response.status_code, 201, response.content)
        successor = response.json()
        self.assertEqual(successor['lineage']['link'], {'reason': 'BANK_MERGER_REPLACEMENT', 'note': 'Syndicate Bank became Canara Bank'})
        self.assertEqual(self.client.get(f'/api/instruments/{successor["id"]}/').json()['lineage']['link']['reason'], 'BANK_MERGER_REPLACEMENT')
        self.assertEqual(self.client.get(f'/api/instruments/{record.pk}/').json()['lineage']['successor']['id'], successor['id'])
        self.assertEqual(self.client.get(f'/api/instruments/{record.pk}/').json()['lineage']['link']['reason'], 'BANK_MERGER_REPLACEMENT')
        plain = self.draft()
        self.assertIsNone(self.client.get(f'/api/instruments/{plain.pk}/').json()['lineage']['link'])

    def test_a_default_reason_is_routine_and_other_needs_words(self):
        _, response = self.renew()
        self.assertEqual(response.json()['lineage']['link']['reason'], 'ROUTINE_RENEWAL')

    def test_other_without_a_note_is_refused(self):
        _, response = self.renew(renewal_reason='OTHER')
        self.assertEqual(response.status_code, 409, response.content)
