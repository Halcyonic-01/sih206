"""Check connectivity privately; explicit flags initialize this app's schema."""
import os
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, DatabaseError, transaction
from config.database import private_schema
from config.legacy_notifications import has_legacy_notifications, archive_legacy_notifications


class Command(BaseCommand):
    help = 'Check the configured PostgreSQL connection. --initialize creates the private app schema; --migrate applies app migrations.'

    def add_arguments(self, parser):
        parser.add_argument('--initialize', action='store_true')
        parser.add_argument('--migrate', action='store_true')
        parser.add_argument('--upgrade-legacy-notifications', action='store_true',
            help='Archive prototype notification history and create the authoritative shared outbox tables.')

    def handle(self, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('Supabase is not configured. Add DATABASE_URL to the ignored .env, or set it in this terminal.')
        schema = private_schema(os.environ.get('DATABASE_SCHEMA', 'portal_app'))
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.execute('SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname = %s)', [schema])
                exists = cursor.fetchone()[0]
                if options['initialize']:
                    with transaction.atomic():
                        cursor.execute(f'CREATE SCHEMA IF NOT EXISTS {connection.ops.quote_name(schema)}')
                        # Keep Django's auth/financial tables outside public/Data API access.
                        cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated', 'service_role')")
                        roles = ['PUBLIC'] + [connection.ops.quote_name(row[0]) for row in cursor.fetchall()]
                        for role in roles:
                            cursor.execute(f'REVOKE ALL ON SCHEMA {connection.ops.quote_name(schema)} FROM {role}')
                            for kind in ('TABLES', 'SEQUENCES', 'FUNCTIONS'):
                                cursor.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA {connection.ops.quote_name(schema)} REVOKE ALL ON {kind} FROM {role}')
                    exists = True
                if not exists:
                    raise CommandError('Connected. Private schema is absent; run check_supabase --initialize --migrate to create the app tables.')
                cursor.execute('SELECT current_schema()')
                if cursor.fetchone()[0] != schema:
                    raise CommandError('Connection search_path does not select the private application schema; use a Session pooler/direct connection.')
            if has_legacy_notifications(connection):
                if not options['upgrade_legacy_notifications']:
                    raise CommandError('Legacy notification tables detected. Use --upgrade-legacy-notifications --migrate to archive that history and install the shared outbox without resetting portal data.')
                archive_legacy_notifications(connection)
                self.stdout.write('Legacy notification history retained in private archive tables; shared outbox installed.')
            if options['migrate']:
                call_command('migrate', interactive=False, verbosity=options['verbosity'])
            self.stdout.write(self.style.SUCCESS('PostgreSQL connection and private application schema are ready. Credentials were not printed.'))
        except (DatabaseError, OSError, ValueError):
            raise CommandError('Could not complete the Supabase database check. Verify the dashboard connection URI, password, network access, TLS and schema permissions. No credentials were printed.') from None
