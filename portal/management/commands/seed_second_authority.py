"""Add a second authority account, so the authority who authorised a release is not the only one who can complete it."""
from getpass import getpass
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from portal.permissions import AUTHORITY_GROUP

DEFAULT_USERNAME = 'authority_second'


class Command(BaseCommand):
    help = ('Create one more Authority account (default authority_second). Needed to complete a release when '
            'RELEASE_REQUIRE_DIFFERENT_COMPLETER=true and for the second signature on large releases. An existing account is never changed.')

    def add_arguments(self, parser):
        parser.add_argument('--username', default=DEFAULT_USERNAME)
        parser.add_argument('--generate-password', action='store_true',
                            help='Local DEBUG mode only: save a random password in the ignored data/authority-credentials.txt.')

    def handle(self, *args, username, generate_password, **options):
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(f'{username} already exists; nothing changed.')
            return
        if generate_password:
            if not settings.DEBUG:
                raise CommandError('Generated credentials are available only in local DEBUG mode.')
            password = secrets.token_urlsafe(24)
        else:
            password = getpass(f'Choose a password for {username} (input hidden): ')
            if password != getpass('Confirm password: '):
                raise CommandError('Passwords do not match. Nothing changed.')
        try:
            validate_password(password, User(username=username))
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from None
        path = settings.BASE_DIR / 'data' / 'authority-credentials.txt'
        with transaction.atomic():
            user = User.objects.create_user(username=username, password=password)
            user.groups.add(Group.objects.get_or_create(name=AUTHORITY_GROUP)[0])
            if generate_password:
                path.parent.mkdir(exist_ok=True)
                fresh = not path.exists()
                with path.open('a', encoding='utf-8') as credentials:
                    if fresh:
                        credentials.write('LOCAL SYNTHETIC DEMO ONLY - DO NOT COMMIT OR SHARE\n')
                    credentials.write(f'{username}: {password}\n')
                try:
                    path.chmod(0o600)
                except OSError:
                    pass
        where = f' Password saved to data/authority-credentials.txt (not printed).' if generate_password else ''
        self.stdout.write(self.style.SUCCESS(f'Created Authority account {username}.{where}'))
