from django.core.management.base import BaseCommand, CommandError
from notifications.digest_dispatch import dispatch


class Command(BaseCommand):
    help = 'Prepare Monday 09:00 IST digests; default dry run. --queue requires WEEKLY_DIGEST_ENABLED.'

    def add_arguments(self, parser):
        parser.add_argument('--queue', action='store_true')
        parser.add_argument('--user-id', type=int)

    def handle(self, *args, **options):
        result = dispatch(dry_run=not options['queue'], user_id=options['user_id'])
        self.stdout.write(str(result))
        if result['failed']:
            raise CommandError('Some digest sources failed; inspect safe server logs and retry.')
