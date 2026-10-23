"""Repeatable synthetic demonstration data; never resets existing records."""
from datetime import date, timedelta
from decimal import Decimal
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from portal import releases, services
from portal.models import Document, Instrument
from portal.permissions import institution_for, role

AS_OF = date(2026, 10, 23)


class Command(BaseCommand):
    help = 'Create synthetic M6 scenarios once, through existing workflow services (DEBUG only).'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Synthetic scenarios require local DEBUG mode.')
        manifest = settings.BASE_DIR / 'data' / 'scenarios-v1.json'
        if manifest.exists():
            try:
                saved = json.loads(manifest.read_text(encoding='utf-8'))
                ids = list(saved['instruments'].values())
                if saved['version'] != 1 or len(ids) != 17 or len(set(ids)) != 17:
                    raise ValueError('Unexpected manifest structure')
                if Instrument.objects.filter(pk__in=ids, reference__startswith='M6-').count() != 17:
                    raise ValueError('Scenario records are missing')
            except (ValueError, KeyError, TypeError) as exc:
                raise CommandError(f'Existing scenario manifest is invalid: {exc}. No changes made.')
            self.stdout.write('Scenario manifest already exists; no records or demo decisions changed.')
            return
        if Instrument.objects.filter(reference__startswith='M6-').exists():
            raise CommandError('M6 references already exist without a manifest. No changes made.')
        try:
            users = {name: get_user_model().objects.get(username=name) for name in
                     ('institution_a', 'institution_b', 'officer', 'authority')}
            for name, expected in [('institution_a', 'institution'), ('institution_b', 'institution'),
                                   ('officer', 'officer'), ('authority', 'authority')]:
                if role(users[name]) != expected:
                    raise ValueError(f'Unexpected role for {name}')
            for name, code in [('institution_a', 'DEMO-A'), ('institution_b', 'DEMO-B')]:
                if institution_for(users[name]).code != code:
                    raise ValueError(f'Unexpected institution for {name}')
            fixtures = {name: (settings.BASE_DIR / 'fixtures' / name).read_bytes() for name in
                        ('sample-fdr.pdf', 'scrutiny-fdr.pdf', 'release-evidence.pdf')}
        except (get_user_model().DoesNotExist, ValueError, OSError) as exc:
            raise CommandError(f'Run both seed_demo commands first and retain bundled fixtures: {exc}')
        owner, officer, authority = (users[key] for key in ('institution_a', 'officer', 'authority'))
        ids, files = {}, []
        wrote_manifest = False

        def upload(name='sample-fdr.pdf'):
            return SimpleUploadedFile(name, fixtures[name], content_type='application/pdf')

        def create(key, days=7, state='accepted', actor=None, predecessor=None, fixture='sample-fdr.pdf', reference=None):
            actor = actor or owner
            cleaned = dict(reference=reference or f'M6-{key.upper()}', bank='Fictional Demo Bank',
                           amount=Decimal('500000.00'), issue_date=date(2026, 1, 1),
                           maturity_date=AS_OF + timedelta(days=days), document=upload(fixture))
            if predecessor:
                predecessor.refresh_from_db()
                cleaned['predecessor_version'] = predecessor.version
            item = services.save_draft(actor, cleaned, predecessor_id=predecessor.pk if predecessor else None)
            files.extend(doc.file for doc in item.documents.all())
            if state != 'draft':
                item = services.submit(actor, item.pk, item.version)
            if state == 'accepted':
                item = services.review(officer, item.pk, item.version, 'accept', 'Manually reviewed synthetic demonstration only.')
            ids[key] = item.pk
            return item

        try:
            with transaction.atomic():
                create('valid', state='submitted')
                discrepancy = create('discrepancy', state='submitted', fixture='scrutiny-fdr.pdf')
                services.add_observation(officer, discrepancy.pk, discrepancy.version,
                                         discrepancy.documents.get(), 1, 'BLOCKING',
                                         'Synthetic page 1 states INR 600000; entered amount is INR 500000. Correct and resubmit.')
                discrepancy.refresh_from_db()
                services.review(officer, discrepancy.pk, discrepancy.version, 'changes', 'Resolve the page 1 amount discrepancy.')
                create('duplicate_original', reference='M6-DUPLICATE')
                create('duplicate_proposal', reference='M6-DUPLICATE', state='draft')
                for key, days in [('matured', -1), ('today', 0), ('seven', 7), ('fifteen', 15), ('thirty', 30), ('future', 31)]:
                    create(key, days)
                parent = create('renewal_old', 7)
                create('renewal_successor', 180, predecessor=parent)
                for outcome in ('pending', 'approved', 'rejected', 'completed'):
                    item = create(f'release_{outcome}', 7)
                    request = releases.request_release(owner, item.pk, item.version, 'Synthetic demonstration release request.')
                    if outcome != 'pending':
                        item.refresh_from_db()
                        releases.decide_release(authority, item.pk, request.pk, item.version,
                                                'reject' if outcome == 'rejected' else 'approve',
                                                'Synthetic authority assessment; no bank transaction.')
                    if outcome == 'completed':
                        item.refresh_from_db()
                        request = releases.complete_release(authority, item.pk, request.pk, item.version,
                                                             'Synthetic evidence reviewed; manual completion recorded.',
                                                             upload('release-evidence.pdf'))
                        files.append(request.completion_evidence.file)
                create('other_institution', 7, actor=users['institution_b'])
                manifest.parent.mkdir(parents=True, exist_ok=True)
                with manifest.open('x', encoding='utf-8') as target:
                    wrote_manifest = True
                    json.dump({'version': 1, 'as_of': AS_OF.isoformat(), 'instruments': ids}, target, indent=2)
        except Exception:
            for file in files:
                file.delete(save=False)
            if wrote_manifest:
                manifest.unlink(missing_ok=True)
            raise
        self.stdout.write(self.style.SUCCESS('Created 17 synthetic instruments. Manifest: data/scenarios-v1.json; evaluation date 2026-10-23.'))
