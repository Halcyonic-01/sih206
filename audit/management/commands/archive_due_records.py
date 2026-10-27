"""List records whose retention period has passed, and archive them when asked."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from portal import retention
from portal.models import Instrument
from portal.services import WorkflowError


class Command(BaseCommand):
    help = ('List settled records that are archival due (not archived, no legal hold). With --archive --as-user <authority user> '
            '--reason "<text>" it archives them (freezes them) one by one, each audited under that user.')

    def add_arguments(self, parser):
        parser.add_argument('--archive', action='store_true')
        parser.add_argument('--as-user', help='The authority user the archival is recorded under.')
        parser.add_argument('--reason', default='')

    def handle(self, *args, archive=False, as_user=None, reason='', **options):
        settled = Instrument.objects.filter(Q(released_at__isnull=False) | Q(superseded_at__isnull=False)).select_related('institution')
        items = [item for item in settled.order_by('pk') if retention.state(item)['archival_due'] and not retention.state(item)['legal_hold']]
        for item in items:
            self.stdout.write(f'{item.pk}\t{item.reference}\t{item.institution.code}\tdue {retention.due_on(item).isoformat()}')
        self.stdout.write(f'{len(items)} record(s) archival due.')
        if not archive:
            return
        actor = get_user_model().objects.filter(username=as_user).first() if as_user else None
        if actor is None or not reason.strip():
            raise CommandError('--archive needs --as-user <authority username> and --reason.')
        done = 0
        for item in items:
            try:
                retention.archive(actor, item, reason)
                done += 1
            except WorkflowError as error:
                self.stderr.write(f'{item.reference}: {error}')
        self.stdout.write(f'{done} record(s) archived.')
