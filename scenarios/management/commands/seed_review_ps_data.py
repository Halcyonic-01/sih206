"""Seed v2 hook for PS scenarios 3, 7 and 9 (K8): obligations, linked holdings, a release-ready record, dated history.

Synthetic and idempotent. Everything goes through the services, so audit events, the hash chain and notifications are
written exactly as in real use. The dated KPI history is created with the clock set to past business days.
"""
from datetime import date, datetime, time
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from obligations import services as obligation_services
from obligations.calculations import ApprovalInput, required_amount
from obligations.catalogue import draft_payload
from obligations.models import DepositObligation, InstitutionProfile, ProgrammeApproval, RuleSet
from portal import record_operations, services
from portal.models import Institution, Instrument
from verification.services import import_statement

MARKER = 'PS7-RELEASE-READY'
RTGS_REFERENCE, RTGS_UTR = 'PS6-RTGS-CONFIRMED', 'UTRSEEDPS6001'
RULE_CODE = 'synthetic-s4-review-draft'  # the draft rule set seed_review_obligations also uses
REASON = 'SIMULATED review seed v2 (synthetic data only)'
IST = ZoneInfo('Asia/Kolkata')


def at(day, hour=11):
    return datetime.combine(day, time(hour), tzinfo=IST)


class Command(BaseCommand):
    help = 'Seed SIMULATED data for PS scenarios 3, 7 and 9 (obligations, release-ready record, dated KPI history).'

    def handle(self, *args, **options):
        self.prepare()
        if Instrument.objects.filter(reference=MARKER).exists():
            self.stdout.write('PS 3/7/9 review data already present.')
        else:
            self.scenarios()
        self.proof_and_confirmation()

    def prepare(self):
        users = get_user_model().objects
        try:
            self.a, self.b, self.officer = (users.get(username=name) for name in ('institution_a', 'institution_b', 'officer'))
            self.fixtures = {name: (settings.BASE_DIR / 'fixtures' / name).read_bytes()
                             for name in ('sample-fdr.pdf', 'scrutiny-fdr.pdf')}
            self.demo_a, self.demo_b = Institution.objects.get(code='DEMO-A'), Institution.objects.get(code='DEMO-B')
        except (get_user_model().DoesNotExist, Institution.DoesNotExist, OSError) as exc:
            raise CommandError(f'Run seed_demo, seed_staff and seed_scenarios first: {exc}')
        self.rule, _ = RuleSet.objects.get_or_create(code=RULE_CODE, version=1, defaults=dict(
            effective_from=date(2026, 1, 1), payload=draft_payload(), source_document='SIMULATED review seed',
            source_clause='Draft demo only; not approved policy'))

    def scenarios(self):
        demo_a, demo_b, rule = self.demo_a, self.demo_b, self.rule
        with transaction.atomic():
            # PS 3: E&T UG on leased land + MBA PG => (35 + 15) x 2 lakh, the plan's F1 example.
            a_ob = self.obligation(demo_a, rule, 'PS3-DEMO-A', [
                ('ENGINEERING_TECHNOLOGY', 'UG', 'LEASED', 'OWNED'), ('MANAGEMENT', 'PG', 'OWNED', 'OWNED')],
                date(2026, 1, 1), date(2036, 1, 1), intimation=date(2026, 9, 15))
            b_ob = self.obligation(demo_b, rule, 'PS3-DEMO-B', [('MANAGEMENT', 'PG', 'OWNED', 'OWNED')],
                                   date(2026, 1, 1), date(2036, 1, 1))
            linked = self.link(demo_a, a_ob) + self.link(demo_b, b_ob)
            # PS 9: dated history, so turnaround and renewal timeliness have real values.
            self.history(a_ob)
            # PS 7: a term-complete obligation and an accepted FDR with every APH 6.46 application document.
            rel_ob = self.obligation(demo_a, rule, 'PS7-TERM-COMPLETE', None, date(2016, 10, 1), date(2026, 10, 1),
                                     required=150000000)
            self.record(MARKER, rel_ob, date(2016, 10, 1), date(2026, 10, 1), Decimal('1500000.00'),
                        extra=('REQUEST_LETTER', 'AFFIDAVIT_6', 'APPROVAL_LETTER'))
        self.stdout.write(f'PS 3/7/9 review data: 3 obligations, {linked} holdings linked, dated KPI history, '
                          f'release-ready record {MARKER}.')

    @transaction.atomic
    def proof_and_confirmation(self):
        """S2 proof deadline and the % confirmed KPI: an officer receipt review and a statement-confirmed RTGS deposit."""
        obligation = DepositObligation.objects.filter(institution=self.demo_a, basis_reference='PS3-DEMO-A').first()
        if obligation and not obligation.proof_reviews.exists():
            # Intimation 15 Sep, due 30 Sep: payment proof arrived in time, Affidavit-3 never did -> PROOF_OVERDUE.
            obligation_services.record_proof_receipts(self.officer, obligation.pk, obligation.version, '2026-09-28',
                                                      None, 'Receipt register checked: Affidavit-3 not received.')
        if obligation and not Instrument.objects.filter(reference=RTGS_REFERENCE).exists():
            item = services.save_draft(self.a, dict(reference=RTGS_REFERENCE, bank='Fictional Demo Bank',
                amount=Decimal('500000.00'), issue_date=date(2026, 4, 2), maturity_date=date(2036, 1, 1), mode='RTGS',
                utr=RTGS_UTR, obligation=obligation, document=self.upload()))
            item = services.submit(self.a, item.pk, item.version)
            item = services.review(self.officer, item.pk, item.version, 'accept', 'Manually reviewed synthetic demonstration only.')
            import_statement(self.officer, f'utr,amount,value_date\n{RTGS_UTR},500000.00,2026-04-02\n'.encode(),
                             'SIMULATED review seed statement', {str(item.pk): item.version})
        self.stdout.write('Proof receipt review and statement-confirmed RTGS deposit ready.')

    def upload(self, name='sample-fdr.pdf', label=None):
        return SimpleUploadedFile(label or name, self.fixtures[name], content_type='application/pdf')

    def obligation(self, institution, rule, reference, approvals, start, end, intimation=None, required=None):
        if approvals:
            profile = InstitutionProfile.objects.get(institution=institution)
            for programme, level, land, building in approvals:
                obligation_services.save_child(self.officer, ProgrammeApproval, institution.pk, dict(
                    programme=programme, level=level, approved_on=start, loa_ref=f'{reference}-{programme}-{level}',
                    land_tenure=land, building_tenure=building), REASON)
            required = required_amount([ApprovalInput(*row) for row in approvals], rule, as_of=start,
                                       institution_type=profile.institution_type)['required_paise']
        return obligation_services.save_child(self.officer, DepositObligation, institution.pk, dict(
            basis='APPROVAL', basis_reference=reference, rule_version_id=rule.pk, required_paise=required,
            term_start=start, term_end=end, intimation_date=intimation), REASON)

    def link(self, institution, obligation):
        count = 0
        for item in Instrument.objects.filter(institution=institution, obligation__isnull=True).order_by('pk'):
            before = services.snapshot(item)
            services._compare_and_update(item, item.version, obligation=obligation)
            services.event(item, self.officer, 'OBLIGATION_LINKED', before, REASON)
            count += 1
        return count

    def record(self, reference, obligation, issue, maturity, amount, extra=(), predecessor=None, review=True):
        owner = self.a
        cleaned = dict(reference=reference, bank='Fictional Demo Bank', amount=amount, issue_date=issue,
                       maturity_date=maturity, mode='FDR', ifsc='SBIN0001234', branch='Synthetic branch',
                       holder_names='Fictional Trust; AICTE', lien_marked=True, obligation=obligation,
                       document=self.upload('scrutiny-fdr.pdf'))
        if predecessor:
            predecessor.refresh_from_db()
            cleaned['predecessor_version'] = predecessor.version
        item = services.save_draft(owner, cleaned, predecessor_id=predecessor.pk if predecessor else None)
        for kind in extra:
            record_operations.upload_document(owner, item.pk, item.version,
                                              self.upload(label=f'{kind.lower()}.pdf'), kind)
            item.refresh_from_db()
        item = services.submit(owner, item.pk, item.version)
        if review:
            item = services.review(self.officer, item.pk, item.version, 'accept', 'Manually reviewed synthetic demonstration only.')
        return item

    def at_time(self, moment):
        return mock.patch('django.utils.timezone.now', return_value=moment)

    def history(self, obligation):
        def dated(reference, issue, maturity, steps, predecessor=None):
            """steps: business days for create+submit, then (optional) changes, resubmit, then accept."""
            created, *rest = steps
            with self.at_time(at(created)):
                cleaned = dict(reference=reference, bank='Fictional Demo Bank', amount=Decimal('500000.00'),
                               issue_date=issue, maturity_date=maturity, mode='FDR', ifsc='SBIN0001234',
                               obligation=obligation, document=self.upload())
                if predecessor:
                    predecessor.refresh_from_db()
                    cleaned['predecessor_version'] = predecessor.version
                item = services.save_draft(self.a, cleaned, predecessor_id=predecessor.pk if predecessor else None)
                item = services.submit(self.a, item.pk, item.version)
            if len(rest) == 3:
                changes, resubmit, accept = rest
                with self.at_time(at(changes, 15)):
                    item = services.review(self.officer, item.pk, item.version, 'changes', 'Holder names missing on page 1.')
                with self.at_time(at(resubmit, 12)):
                    fixed = {key: cleaned[key] for key in ('reference', 'bank', 'amount', 'issue_date', 'maturity_date')}
                    item = services.save_draft(self.a, fixed | {'holder_names': 'Fictional Trust; AICTE',
                                                                'version': item.version}, item.pk)
                    item = services.submit(self.a, item.pk, item.version)
            else:
                accept, = rest
            with self.at_time(at(accept, 16)):
                return services.review(self.officer, item.pk, item.version, 'accept', 'Manually reviewed synthetic demonstration only.')

        dated('KPI-TURNAROUND-1', date(2026, 6, 25), date(2031, 6, 25), [date(2026, 7, 1), date(2026, 7, 4)])
        dated('KPI-CORRECTION-1', date(2026, 7, 5), date(2031, 7, 5),
              [date(2026, 7, 10), date(2026, 7, 13), date(2026, 7, 15), date(2026, 7, 17)])
        on_time = dated('KPI-RENEW-ONTIME-OLD', date(2025, 9, 30), date(2026, 9, 30), [date(2025, 10, 1), date(2025, 10, 3)])
        dated('KPI-RENEW-ONTIME-NEW', date(2026, 9, 30), date(2031, 9, 30), [date(2026, 9, 20), date(2026, 9, 25)], on_time)
        late = dated('KPI-RENEW-LATE-OLD', date(2025, 8, 31), date(2026, 8, 31), [date(2025, 9, 2), date(2025, 9, 4)])
        dated('KPI-RENEW-LATE-NEW', date(2026, 8, 31), date(2031, 8, 31), [date(2026, 9, 5), date(2026, 9, 10)], late)
