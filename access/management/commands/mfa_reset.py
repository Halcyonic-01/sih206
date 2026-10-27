"""Remove a staff member's authenticator app after a lost phone, with an access-log entry."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from access.models import AccessLog, MfaDevice


class Command(BaseCommand):
    help = 'Delete the authenticator app of a user (lost phone). They sign in with the password and enrol again.'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--reason', required=True, help='Why, for the access log (for example a ticket number).')

    def handle(self, *args, username, reason, **options):
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise CommandError('No such user.')
        deleted, _ = MfaDevice.objects.filter(user=user).delete()
        AccessLog.objects.create(user=user, username=username, action='MFA_RESET', object_type='user', object_id=user.pk,
                                 detail=f'reset from the command line: {reason}'[:500])
        self.stdout.write(f'Removed {deleted} device(s) for {username}. Make sure the person is who they say they are before they enrol again.')
