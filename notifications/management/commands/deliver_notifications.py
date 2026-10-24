from django.core.management.base import BaseCommand
from notifications.services import deliver_pending


class Command(BaseCommand):
    help = 'Deliver up to 100 queued notifications with bounded retries.'

    def handle(self, **options):
        self.stdout.write(f'Delivered {deliver_pending()} notifications.')
