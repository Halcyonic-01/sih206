"""Owned idempotent synthetic seed, discovered by K8's existing seed_review hook."""
from datetime import date
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from obligations import services
from obligations.catalogue import draft_payload
from obligations.models import DepositObligation, InstitutionProfile, ProgrammeApproval, RuleSet
from portal.models import Institution
from portal.permissions import role


class Command(BaseCommand):
    help = 'Seed SIMULATED institution/obligation data; no accounts, instruments or approved policy.'

    @transaction.atomic
    def handle(self, *args, **options):
        actor = next((u for u in get_user_model().objects.filter(is_active=True, groups__name='Officer').order_by('pk')
                      if role(u) == 'officer'), None)
        if actor is None:
            raise CommandError('Run the existing demo-account seed first; an unambiguous officer is required.')
        code = 'SYNTH-S4-REVIEW'
        institution = Institution.objects.filter(code=code).first()
        if institution and not InstitutionProfile.objects.filter(institution=institution, aicte_id=code).exists():
            raise CommandError('Synthetic seed identity collision; existing data was left unchanged.')
        if institution is None:
            profile = services.create_institution(actor, dict(code=code, name='SIMULATED S4 Review College',
                aicte_id=code, trust_name='SIMULATED Review Trust', institution_type='PRIVATE',
                region='North', state='Delhi', contact_email='review@example.invalid'), 'SIMULATED S4 review seed')
            institution = profile.institution
        rule, _ = RuleSet.objects.get_or_create(code='synthetic-s4-review-draft', version=1, defaults=dict(
            effective_from=date(2026, 1, 1), payload=draft_payload(), source_document='SIMULATED review seed',
            source_clause='Draft demo only; not approved policy'))
        if not ProgrammeApproval.objects.filter(institution=institution, loa_ref=code).exists():
            services.save_child(actor, ProgrammeApproval, institution.pk, dict(programme='MANAGEMENT', level='PG',
                approved_on=date(2026, 1, 1), loa_ref=code, land_tenure='OWNED', building_tenure='OWNED'),
                'SIMULATED S4 review seed')
        if not DepositObligation.objects.filter(institution=institution, basis_reference=code).exists():
            services.save_child(actor, DepositObligation, institution.pk, dict(basis='APPROVAL', basis_reference=code,
                rule_version_id=rule.pk, required_paise=150000000,
                term_start=date(2026, 1, 1), term_end=date(2036, 1, 1)), 'SIMULATED S4 review seed')
        self.stdout.write('SIMULATED S4 institution and draft obligation ready; existing rows retained.')
