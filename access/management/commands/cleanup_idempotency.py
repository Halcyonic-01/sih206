"""Delete stored idempotent responses older than 24 hours. Cheap; safe to run every few minutes."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from access.models import IdempotentRequest


class Command(BaseCommand):
    help = 'Delete idempotency records older than 24 hours.'

    def handle(self, *args, **options):
        deleted, _ = IdempotentRequest.objects.filter(created_at__lt=timezone.now() - timedelta(hours=24)).delete()
        self.stdout.write(f'Removed {deleted} stored response(s).')
