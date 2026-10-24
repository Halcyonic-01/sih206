"""Synthetic Clearance-unit and Auditor accounts for the demo. Existing accounts are never modified."""
import secrets
from getpass import getpass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from access.models import UnitAssignment
from access.private_files import make_private
from portal.permissions import AUDITOR_GROUP, CLEARANCE_GROUP

ACCOUNTS = [
    ('clearance_pgrc', CLEARANCE_GROUP, UnitAssignment.Unit.PGRC),
    ('clearance_vigilance', CLEARANCE_GROUP, UnitAssignment.Unit.VIGILANCE),
    ('clearance_grants', CLEARANCE_GROUP, UnitAssignment.Unit.GRANTS),
    ('auditor', AUDITOR_GROUP, None),
]


class Command(BaseCommand):
    help = 'Create the synthetic Clearance (PGRC, Vigilance, Grants) and Auditor demo accounts.'

    def add_arguments(self, parser):
        parser.add_argument('--generate-password', action='store_true',
                            help='Local DEBUG mode only: save random credentials under ignored data/.')

    def handle(self, *args, **options):
        User = get_user_model()
        missing = [account for account in ACCOUNTS if not User.objects.filter(username=account[0]).exists()]
        if not missing:
            self.stdout.write('All staff demo accounts already exist; nothing changed.')
            return
        path = settings.BASE_DIR / 'data' / 'staff-credentials.txt'
        if options['generate_password']:
            if not settings.DEBUG:
                raise CommandError('Generated demo credentials are available only in local DEBUG mode.')
            if path.exists():
                raise CommandError('data/staff-credentials.txt already exists. Remove it or use interactive mode.')
            password = secrets.token_urlsafe(24)
        else:
            password = getpass('Choose a password for NEW staff demo accounts (input hidden): ')
            if password != getpass('Confirm password: '):
                raise CommandError('Passwords do not match. Nothing changed.')
        try:
            for username, _, _ in missing:
                validate_password(password, User(username=username))
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from None
        with transaction.atomic():
            groups = {name: Group.objects.get_or_create(name=name)[0] for name in {a[1] for a in missing}}
            for username, group, unit in missing:
                user = User.objects.create_user(username=username, password=password)
                user.groups.add(groups[group])
                if unit:
                    UnitAssignment.objects.create(user=user, unit=unit)
                self.stdout.write(f'Created {username}')
        if options['generate_password']:
            with path.open('x', encoding='utf-8') as handle:
                handle.write('LOCAL SYNTHETIC DEMO ONLY - DO NOT COMMIT OR SHARE\n')
                for username, _, _ in missing:
                    handle.write(f'{username}: {password}\n')
            try:
                make_private(path)
            except OSError:
                pass
            self.stdout.write('Random credentials saved to data/staff-credentials.txt (not printed).')
