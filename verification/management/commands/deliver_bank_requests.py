from django.core.management.base import BaseCommand
from verification.bank import deliver_requests


class Command(BaseCommand):
    help = 'Deliver pending bank confirmation challenges to operator-reviewed contacts.'

    def handle(self, **options):
        self.stdout.write(f'Delivered {deliver_requests()} bank requests. Tokens and codes are not logged.')
