"""Load bank-merger mappings (old code to new code). They are used by the checks only once marked verified."""
import csv
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from verification.models import BankSuccession


class Command(BaseCommand):
    help = ('Load old_code,new_code,old_name,new_name,effective_date,source rows. Rows are stored UNVERIFIED unless --verified is '
            'given, which you should only pass after checking each row against the RBI / Government notification named in `source`.')

    def add_arguments(self, parser):
        parser.add_argument('csv_file')
        parser.add_argument('--verified', action='store_true', help='Mark the loaded rows as checked against their notification.')

    def handle(self, *args, csv_file, verified=False, **options):
        try:
            handle = open(csv_file, newline='', encoding='utf-8-sig')
        except OSError as error:
            raise CommandError(f'Cannot read {csv_file}: {error.strerror}') from None
        count = 0
        with handle:
            for number, row in enumerate(csv.DictReader(handle), 2):
                old, new = (row.get('old_code') or '').strip().upper(), (row.get('new_code') or '').strip().upper()
                if len(old) != 4 or len(new) != 4 or old == new:
                    raise CommandError(f'line {number}: old_code and new_code must be different four-letter bank codes.')
                try:
                    effective = date.fromisoformat(row['effective_date'].strip()) if (row.get('effective_date') or '').strip() else None
                except ValueError:
                    raise CommandError(f'line {number}: effective_date must be YYYY-MM-DD.') from None
                BankSuccession.objects.update_or_create(old_code=old, defaults={
                    'new_code': new, 'old_name': (row.get('old_name') or '').strip()[:200], 'new_name': (row.get('new_name') or '').strip()[:200],
                    'effective_date': effective, 'source': (row.get('source') or '').strip()[:300], 'verified': verified})
                count += 1
        state = 'VERIFIED' if verified else 'UNVERIFIED (not used by the checks until verified)'
        self.stdout.write(f'{count} succession row(s) loaded, {state}.')
