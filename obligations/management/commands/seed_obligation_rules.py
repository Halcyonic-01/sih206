"""Install an explicit draft demo rule version; never overwrite a stored version."""
from datetime import date

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from obligations.catalogue import SOURCE, draft_payload
from obligations.models import RuleSet
from obligations.rules import RuleInputError, rule_snapshot


class Command(BaseCommand):
    help = 'Seed unapproved demo rules only. Supply a demo effective date; no policy is activated.'

    def add_arguments(self, parser):
        parser.add_argument('--effective-from', required=True,
                            help='Explicit demo evaluation window start (YYYY-MM-DD), not an official effective date.')
        parser.add_argument('--effective-to')
        parser.add_argument('--rule-version', type=int, default=1)

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            start = date.fromisoformat(options['effective_from'])
            end = date.fromisoformat(options['effective_to']) if options['effective_to'] else None
            candidate = RuleSet(code='sd_policy_demo', version=options['rule_version'],
                effective_from=start, effective_to=end, payload=draft_payload(),
                source_clause='Table 1.4; 1.12; 2.25(f); 2.21(h)-(i); 6.46; 7.7',
                source_document=SOURCE)
            candidate.full_clean(validate_unique=False, validate_constraints=False)
            expected = rule_snapshot(candidate, start)
        except (ValueError, TypeError, ValidationError) as exc:
            raise CommandError(str(exc)) from exc
        existing = RuleSet.objects.filter(code=candidate.code, version=candidate.version).first()
        if existing is not None:
            try:
                same = rule_snapshot(existing, start) == expected and existing.approved_by_id is None
            except RuleInputError:
                same = False
            if not same:
                raise CommandError('Stored version differs or has an approver. Create a new version; nothing was overwritten.')
            self.stdout.write('Draft demo rule version already exists; unchanged.')
        else:
            candidate.full_clean()
            candidate.save()
            self.stdout.write(self.style.SUCCESS('Created DRAFT_DEMO_NOT_APPROVED rule version. No policy activated.'))
