"""Load a published IFSC directory (CSV) into the bank and branch master. Offline: the file is supplied by the operator."""
import csv
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from verification.models import BankBranch

IFSC = re.compile(r'\A[A-Z]{4}0[A-Z0-9]{6}\Z')
COLUMNS = {'IFSC', 'BANK'}


class Command(BaseCommand):
    help = ('Load IFSC,BANK,BRANCH,CITY,STATE rows (RBI/NPCI directory export) into the bank master. Existing IFSCs are updated; '
            'nothing is deleted. Invalid rows are listed and skipped; use --strict to load nothing if any row is invalid.')

    def add_arguments(self, parser):
        parser.add_argument('csv_file')
        parser.add_argument('--directory-version', required=True, dest='version', help='Label of this directory, for example 2026-10 (shown in findings).')
        parser.add_argument('--strict', action='store_true')

    def handle(self, *args, csv_file, version, strict=False, **options):
        try:
            handle = open(csv_file, newline='', encoding='utf-8-sig')
        except OSError as error:
            raise CommandError(f'Cannot read {csv_file}: {error.strerror}') from None
        with handle:
            reader = csv.DictReader(handle)
            headers = {(name or '').strip().upper() for name in reader.fieldnames or []}
            if not COLUMNS <= headers:
                raise CommandError('The CSV needs the columns IFSC and BANK (and optionally BRANCH, CITY, STATE).')
            good, bad = [], []
            for number, raw in enumerate(reader, 2):
                row = {(k or '').strip().upper(): (v or '').strip() for k, v in raw.items()}
                ifsc = row.get('IFSC', '').upper()
                if not IFSC.match(ifsc) or not row.get('BANK'):
                    bad.append(f'line {number}: invalid IFSC or missing bank name')
                    continue
                good.append((ifsc, row))
        if bad and strict:
            raise CommandError('; '.join(bad[:10]) + (f' ... and {len(bad) - 10} more' if len(bad) > 10 else ''))
        created = updated = 0
        with transaction.atomic():
            for ifsc, row in good:
                _, was_created = BankBranch.objects.update_or_create(ifsc=ifsc, defaults={
                    'bank_code': ifsc[:4], 'bank_name': row['BANK'][:200], 'branch': row.get('BRANCH', '')[:200],
                    'city': row.get('CITY', '')[:100], 'state': row.get('STATE', '')[:100], 'directory_version': version[:60]})
                created += was_created
                updated += not was_created
        for message in bad[:20]:
            self.stderr.write(message)
        self.stdout.write(f'Directory {version}: {created} added, {updated} updated, {len(bad)} skipped.')
