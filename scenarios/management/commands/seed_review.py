"""Review-build seed v2 (K8): everything the reviewers' walkthrough needs, on top of seed_demo and seed_scenarios.

Idempotent: a manifest in data/ records that it ran. Owners add their own scenario data by shipping a management
command named `seed_review_<area>` (for example `seed_review_obligations`); this command runs every such command
in alphabetical order after the platform data. Synthetic data only; local DEBUG mode only.
"""
import json
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command, get_commands
from django.core.management.base import BaseCommand, CommandError
from django.test import Client, override_settings

from access.logging import AccessLog
from audit.chain import verify_chain
from notifications.models import Notification
from obligations.models import InstitutionProfile
from portal.models import Document, Institution, Instrument

DEMO_DATE = date(2026, 10, 23)   # the evaluation date used by seed_scenarios and the PS scenario 4 walkthrough
VERSION = 2
PROFILES = {
    'DEMO-A': dict(aicte_id='DEMO-AICTE-0001', trust_name='Fictional Education Trust A', institution_type='PRIVATE',
                   region='North', state='Delhi', contact_email='registrar-a@demo.example'),
    'DEMO-B': dict(aicte_id='DEMO-AICTE-0002', trust_name='Fictional Education Trust B', institution_type='AIDED',
                   region='South', state='Karnataka', contact_email='registrar-b@demo.example'),
}


class Command(BaseCommand):
    help = 'Seed v2 for the review build: demo e-mail addresses, institution profiles, activity, rules run.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Run again even if the manifest exists.')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Review seed data is synthetic and runs only in local DEBUG mode.')
        manifest = settings.BASE_DIR / 'data' / 'seed-review-v2.json'
        if manifest.exists() and not options['force']:
            self.stdout.write('Review seed v2 already applied. Use --force to run the idempotent steps again.')
            return
        User = get_user_model()
        missing = [name for name in ('institution_a', 'institution_b', 'officer', 'authority')
                   if not User.objects.filter(username=name).exists()]
        if missing:
            raise CommandError(f'Create the demo accounts first (seed_demo). Missing: {", ".join(missing)}')

        if not Instrument.objects.filter(reference__startswith='M6-').exists():
            call_command('seed_scenarios', stdout=self.stdout)
        self.addresses()
        self.profiles()
        fresh = not manifest.exists()
        if fresh:
            self.activity()
        self.rules()
        errors = self.owner_seeds()

        result = verify_chain()
        self.stdout.write(f'Audit chain: {result.status} ({result.checked} sealed events).')
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({'version': VERSION, 'demo_date': DEMO_DATE.isoformat(),
                                        'notifications': Notification.objects.count()}, indent=2), encoding='utf-8')
        if errors:
            raise CommandError('Some owner seeds failed: ' + '; '.join(errors))
        self.stdout.write(self.style.SUCCESS('Review seed v2 applied. Demo evaluation date: 2026-10-23.'))

    def addresses(self):
        """Example-domain addresses so the e-mail channel has somewhere to go (nothing real)."""
        User = get_user_model()
        count = 0
        for user in User.objects.filter(email='').exclude(is_superuser=True):
            user.email = f'{user.username}@demo.example'
            user.save(update_fields=['email'])
            count += 1
        self.stdout.write(f'Demo e-mail addresses set for {count} account(s).')

    def profiles(self):
        for code, values in PROFILES.items():
            institution = Institution.objects.filter(code=code).first()
            if institution:
                _, created = InstitutionProfile.objects.get_or_create(institution=institution, defaults=values)
                self.stdout.write(f'Institution profile {code}: {"created" if created else "kept"}.')

    def activity(self):
        """Real downloads and exports through the real views, so the access log has genuine rows."""
        User = get_user_model()
        document = Document.objects.filter(instrument__reference__startswith='M6-').order_by('pk').first()
        for username in ('officer', 'institution_a'):
            client = Client(HTTP_HOST='localhost')
            client.force_login(User.objects.get(username=username))
            if document and username == 'officer':
                client.get(f'/legacy/documents/{document.pk}/download/')
            client.get('/legacy/instruments/export.csv?category=all')
        self.stdout.write(f'Access log rows: {AccessLog.objects.count()}.')

    def rules(self):
        # Emails stay PENDING here: `python manage.py send_notifications` (or the scheduler) delivers them,
        # which is exactly what the PS scenario 4 walkthrough shows.
        with override_settings(NOTIFY_SEND_ON_COMMIT=False):
            call_command('run_due_rules', '--as-of', DEMO_DATE.isoformat(), stdout=self.stdout)

    def owner_seeds(self):
        errors = []
        for name in sorted(name for name in get_commands() if name.startswith('seed_review_')):
            self.stdout.write(f'Running {name} ...')
            try:
                call_command(name, stdout=self.stdout)
            except Exception as exc:  # one owner's problem must not hide the others
                errors.append(f'{name}: {exc}')
        return errors
