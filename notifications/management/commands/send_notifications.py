from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.service import deliver_pending


class Command(BaseCommand):
    help = 'Send pending notification emails (bounded retries with backoff). Run every few minutes.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        sent, failed = deliver_pending(now=timezone.now(), limit=options['limit'])
        self.stdout.write(f'Notification emails: {sent} sent, {failed} failed (will retry or surface as FAILED).')
