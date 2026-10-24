from django.core.management.base import BaseCommand

from audit.chain import seal_pending


class Command(BaseCommand):
    help = 'Seal audit events that have no seal yet (events from before sealing was switched on). Idempotent.'

    def handle(self, *args, **options):
        sealed = seal_pending()
        self.stdout.write(f'Sealed {sealed} previously unsealed audit event(s) (marked backfilled).')
