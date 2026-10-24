from django.core.management.base import BaseCommand, CommandError

from notifications.rules import RULES, run_rules
from portal.deadlines import parse_as_of
from portal.models import Institution


class Command(BaseCommand):
    help = ('Evaluate the daily deadline rules and queue notifications (maturity reminders, overdue renewals, '
            'penalty review, proof-due reminders, SLA breaches). Idempotent: run it daily; --as-of replays a date.')

    def add_arguments(self, parser):
        parser.add_argument('--as-of', help='Evaluation date YYYY-MM-DD (default: today in the business timezone).')
        parser.add_argument('--dry-run', action='store_true', help='List what would be queued; write nothing.')
        parser.add_argument('--institution', help='Limit to one institution code.')
        parser.add_argument('--only', choices=RULES, action='append', help='Run only this rule group (repeatable).')

    def handle(self, *args, **options):
        try:
            as_of = parse_as_of(options['as_of'])
        except ValueError as exc:
            raise CommandError(str(exc)) from None
        institution = None
        if options['institution']:
            institution = Institution.objects.filter(code=options['institution']).first()
            if institution is None:
                raise CommandError('Unknown institution code.')
        result = run_rules(as_of, dry_run=options['dry_run'], institution=institution, only=options['only'])
        for line in result.lines:
            self.stdout.write(line)
        suffix = ' (dry run: nothing written)' if options['dry_run'] else ''
        self.stdout.write(f'Queued {result.created} notification(s); {result.skipped} event(s) already sent{suffix}.')
        if result.errors:
            for error in result.errors:
                self.stderr.write(f'ERROR {error}')
            raise CommandError(f'{len(result.errors)} rule group(s) failed; the others completed.')
