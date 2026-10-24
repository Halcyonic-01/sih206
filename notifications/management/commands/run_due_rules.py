from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from portal.deadlines import business_today
from portal.models import Instrument
from notifications.services import notify


class Command(BaseCommand):
    help = 'Enqueue configured maturity reminders once per record, threshold and date.'

    def handle(self, **options):
        today = business_today()
        count = 0
        for item in Instrument.objects.filter(status='ACCEPTED', superseded_at__isnull=True, released_at__isnull=True):
            days = (item.maturity_date-today).days
            if days not in settings.REMINDER_DAYS:
                continue
            recipients = get_user_model().objects.filter(is_active=True, userprofile__institution_id=item.institution_id)
            notify(recipients=list(recipients.values_list('pk', flat=True)), template='maturity_reminder',
                   context={'instrument_id': item.pk, 'reference': item.reference},
                   key=f'maturity:{item.pk}:{days}:{today}')
            count += 1
        self.stdout.write(f'Processed {count} maturity reminders; repeated runs are idempotent.')
