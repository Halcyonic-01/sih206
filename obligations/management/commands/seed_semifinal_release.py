"""Add one new synthetic release rehearsal record through the existing services."""
import json
from uuid import uuid4
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from portal import record_operations, services
from portal.models import Instrument


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--confirm-disposable', action='store_true',
            help='Explicitly confirm this DEBUG SQLite database is disposable (for CI).')

    def handle(self, **options):
        if (not settings.DEBUG or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3'
                or (settings.SETTINGS_MODULE != 'config.rehearsal_settings' and not options['confirm_disposable'])):
            raise CommandError('Use the disposable rehearsal profile or explicitly confirm a DEBUG SQLite database with --confirm-disposable.')
        source = Instrument.objects.get(reference='PS7-RELEASE-READY')
        owner = get_user_model().objects.get(username='institution_a')
        officer = get_user_model().objects.get(username='officer')
        documents = list(source.documents.order_by('pk'))
        def upload(document):
            with document.file.open('rb') as stream:
                return SimpleUploadedFile(document.original_name, stream.read(), content_type='application/pdf')
        primary = next(d for d in documents if d.kind == 'FDR')
        data = {k: getattr(source, k) for k in ['bank', 'issue_date', 'maturity_date', 'mode', 'ifsc',
            'branch', 'holder_names', 'lien_marked', 'obligation']}
        record = services.save_draft(owner, data | {'reference': 'SYNTH-SEMIFINAL-' + uuid4().hex[:10],
            'amount': source.amount, 'document': upload(primary)})
        for document in documents:
            if document.pk == primary.pk:
                continue
            record_operations.upload_document(owner, record.pk, record.version, upload(document), document.kind)
            record.refresh_from_db()
        record = services.submit(owner, record.pk, record.version)
        record = services.review(officer, record.pk, record.version, 'accept',
            'Manually prepared synthetic release rehearsal; no bank authenticity claim.')
        target = settings.BASE_DIR / 'data' / 'release-scenario.json'
        target.write_text(json.dumps({'id': record.pk, 'reference': record.reference,
            'obligation_id': record.obligation_id, 'version': record.version}) + '\n')
        self.stdout.write(f'New synthetic release scenario saved: {target}')
