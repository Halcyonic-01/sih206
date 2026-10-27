"""Restrict an officer to one or more regions, or lift the restriction (P2-2)."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from access.models import AccessLog, RegionAssignment
from portal.permissions import role


class Command(BaseCommand):
    help = ('Assign an officer to a region (the "region" of the institutions\' AICTE profiles, for example "North"). '
            'An officer with no region keeps national scope. Use --remove to take a region away, --head to make them its head.')

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('region')
        parser.add_argument('--head', action='store_true', help='Also the regional head who receives escalations.')
        parser.add_argument('--remove', action='store_true')

    def handle(self, *args, username, region, head=False, remove=False, **options):
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise CommandError('No such user.')
        if role(user) != 'officer':
            raise CommandError('Only officer accounts can be assigned to a region.')
        region = ' '.join(region.split())
        if not region:
            raise CommandError('Give a region.')
        if remove:
            deleted, _ = RegionAssignment.objects.filter(user=user, region__iexact=region).delete()
            detail = f'removed region {region}'
        else:
            RegionAssignment.objects.update_or_create(user=user, region=region, defaults={'is_head': head})
            deleted, detail = 1, f'assigned region {region}{" (head)" if head else ""}'
        AccessLog.objects.create(user=None, username='system', action='REGION_ASSIGNMENT', object_type='user',
                                 object_id=user.pk, detail=f'{username}: {detail}'[:500])
        remaining = list(RegionAssignment.objects.filter(user=user).values_list('region', flat=True))
        self.stdout.write(f'{username}: {detail}. Now scoped to: {", ".join(remaining) if remaining else "all regions (national)"}.')
