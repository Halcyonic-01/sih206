from datetime import date
from decimal import Decimal
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from ai.evaluation import load_manifest
from portal.models import Instrument
from portal.services import save_draft


class Command(BaseCommand):
    help = 'Seed only labelled synthetic extraction fixtures in an explicitly disposable local database.'

    def add_arguments(self, parser):
        parser.add_argument('--manifest', default='fixtures/ai-evaluation/manifest.json')
        parser.add_argument('--confirm-disposable', action='store_true')

    def handle(self, **options):
        if not settings.DEBUG or not options['confirm_disposable']:
            raise CommandError('Requires local DEBUG and --confirm-disposable.')
        path = Path(options['manifest'])
        data = load_manifest(path)
        owner = get_user_model().objects.filter(username='institution_a').first()
        if not owner:
            raise CommandError('Seed synthetic institution_a first.')
        for entry in data['cases']:
            values = entry['declared']
            existing = Instrument.objects.filter(reference=values['reference']).first()
            if existing:
                if existing.created_by_id != owner.pk or not existing.documents.filter(sha256=entry['sha256']).exists():
                    raise CommandError('Existing fixture conflicts; use a clean disposable database.')
                continue
            save_draft(owner, values | {'amount': Decimal(values['amount']),
                'issue_date': date.fromisoformat(values['issue_date']),
                'maturity_date': date.fromisoformat(values['maturity_date']),
                'document': SimpleUploadedFile(entry['file'], (path.parent / entry['file']).read_bytes(), content_type='application/pdf')})
        self.stdout.write(f"Seeded/verified {len(data['cases'])} synthetic evaluation records.")
