from getpass import getpass
import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from portal.models import Institution, UserProfile
from portal.permissions import AUTHORITY_GROUP, INSTITUTION_GROUP, OFFICER_GROUP


class Command(BaseCommand):
    help = 'Create synthetic institutions and demo accounts; existing accounts are never modified.'

    def add_arguments(self, parser):
        parser.add_argument('--generate-password', action='store_true',
                            help='Local DEBUG mode only: save random credentials under ignored data/.')
        parser.add_argument('--authority-only', action='store_true',
                            help='Add only the Milestone 5 Authority account without changing earlier accounts.')

    def handle(self, *args, **options):
        User = get_user_model()
        authority_only = options['authority_only']
        accounts = [('authority', None)] if authority_only else [
            ('institution_a', 'DEMO-A'), ('institution_b', 'DEMO-B'), ('officer', None)]
        missing = [(name, code) for name, code in accounts if not User.objects.filter(username=name).exists()]
        if not missing:
            self.stdout.write('All demo accounts already exist; nothing changed.')
            return
        generated = options['generate_password']
        filename = 'authority-credentials.txt' if authority_only else 'demo-credentials.txt'
        credentials_path = settings.BASE_DIR / 'data' / filename
        if generated:
            if not settings.DEBUG:
                raise CommandError('Generated demo credentials are available only in local DEBUG mode.')
            if credentials_path.exists():
                raise CommandError('Credentials file already exists. Use interactive seed_demo for missing accounts.')
            password = secrets.token_urlsafe(24)
        else:
            password = getpass('Choose a password for NEW demo accounts (input hidden): ')
            if password != getpass('Confirm password: '):
                raise CommandError('Passwords do not match. Nothing changed.')
        try:
            for username, _ in missing:
                validate_password(password, User(username=username))
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages))
        credentials_written = False
        try:
            with transaction.atomic():
                institutions = {}
                for code, label in ([] if authority_only else [('DEMO-A', 'Fictional Technical Institute A'),
                                                              ('DEMO-B', 'Fictional Technical Institute B')]):
                    institutions[code], _ = Institution.objects.get_or_create(code=code, defaults={'name': label})
                if authority_only:
                    authority_group, _ = Group.objects.get_or_create(name=AUTHORITY_GROUP)
                else:
                    institution_group, _ = Group.objects.get_or_create(name=INSTITUTION_GROUP)
                    officer_group, _ = Group.objects.get_or_create(name=OFFICER_GROUP)
                for username, code in missing:
                    user = User.objects.create_user(username=username, password=password)
                    user.groups.add(authority_group if authority_only else (institution_group if code else officer_group))
                    if code:
                        UserProfile.objects.create(user=user, institution=institutions[code])
                    self.stdout.write(f'Created {username}')
                if generated:
                    with credentials_path.open('x', encoding='utf-8') as credentials:
                        credentials_written = True
                        credentials.write('LOCAL SYNTHETIC DEMO ONLY - DO NOT COMMIT OR SHARE\n')
                        for username, _ in missing:
                            credentials.write(f'{username}: {password}\n')
        except Exception:
            if credentials_written:
                credentials_path.unlink(missing_ok=True)
            raise
        if generated:
            self.stdout.write(f'Random credentials saved to data/{filename} (not printed).')
        self.stdout.write(self.style.SUCCESS('Demo accounts ready. Use synthetic data only.'))
