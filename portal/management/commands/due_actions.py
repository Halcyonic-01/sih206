from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from portal.deadlines import due_actions, parse_as_of, reminder_days
from portal.models import Institution, Instrument


def cell(value):
    # Keep user-entered fields on one terminal row and remove control characters.
    return ''.join(char if char.isprintable() else ' ' for char in str(value))


class Command(BaseCommand):
    help = 'Read-only maturity action report for a trusted local operator. Does not send or save reminders.'

    def add_arguments(self, parser):
        parser.add_argument('--as-of', help='Explicit evaluation date in YYYY-MM-DD format.')
        parser.add_argument('--institution', help='Limit the report to one institution code.')

    def handle(self, *args, **options):
        try:
            as_of = parse_as_of(options['as_of'])
        except ValueError as exc:
            raise CommandError(str(exc)) from None
        records = Instrument.objects.all()
        code = options['institution']
        if code:
            if not Institution.objects.filter(code=code).exists():
                raise CommandError('Unknown institution code.')
            records = records.filter(institution__code=code)
        rows = due_actions(records, as_of)
        source = 'explicit --as-of evaluation' if options['as_of'] else 'current business date'
        self.stdout.write(f'Evaluation date: {as_of.isoformat()} ({source})')
        self.stdout.write(f'Business timezone: {settings.TIME_ZONE}')
        self.stdout.write('Demo reminder thresholds (days): ' + ', '.join(map(str, reminder_days())))
        self.stdout.write('Scope: ' + (cell(code) if code else 'all institutions (trusted local operator)'))
        self.stdout.write('Read-only report; no notifications sent or stored. Maturity is not a compliance decision.')
        self.stdout.write('Reference\tInstitution\tMaturity\tDays remaining\tCategory\tReminder band\tAction')
        for row in rows:
            instrument, maturity = row['instrument'], row['maturity']
            band = f'within {maturity.reminder_band} days' if maturity.reminder_band is not None else '-'
            self.stdout.write('\t'.join(map(cell, [instrument.reference, instrument.institution.code,
                instrument.maturity_date.isoformat(), maturity.days_remaining,
                maturity.code, band, maturity.action])))
        self.stdout.write(f'Total due instruments: {len(rows)}')
        self.stdout.write(' | '.join(f'{label}: {sum(row["maturity"].code == category for row in rows)}'
                                    for category, label in [('matured', 'Matured'), ('today', 'Matures today'),
                                                            ('approaching', 'Approaching maturity')]))
