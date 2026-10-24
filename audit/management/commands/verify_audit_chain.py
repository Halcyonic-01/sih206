from django.core.management.base import BaseCommand, CommandError

from audit.chain import verify_chain


class Command(BaseCommand):
    help = 'Verify the audit hash chain. Exits non-zero when any event was changed, removed or inserted.'

    def handle(self, *args, **options):
        result = verify_chain()
        self.stdout.write(f'Audit chain: {result.status.upper()}. Checked {result.checked} sealed event(s) '
                          f'({result.backfilled} sealed late), {result.unsealed} unsealed. Head: {result.head or "-"}')
        for item in result.broken:
            self.stderr.write(f'BROKEN at event {item["event_id"]}: {item["reason"]} - {item["detail"]}')
        if result.broken:
            raise CommandError('The audit trail does not match its seals.')
        if result.unsealed:
            raise CommandError('Some audit events are unsealed. Run: python manage.py seal_audit_chain')
