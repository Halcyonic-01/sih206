"""One-time, non-destructive bridge from Yash's prototype outbox to the shared outbox.

Old notification history remains in private archive tables; active messages start
in the authoritative platform tables. Accounts, deposits and documents are untouched.
"""
import hashlib
from django.db import transaction


def has_legacy_notifications(connection):
    with connection.cursor() as cursor:
        tables = {row.name for row in connection.introspection.get_table_list(cursor)}
        if 'notifications_notification' not in tables:
            return False
        columns = {row.name for row in connection.introspection.get_table_description(cursor, 'notifications_notification')}
    if {'idempotency_key', 'recipient_key', 'template_id'}.issubset(columns):
        return False
    if {'key', 'template', 'recipient_id'}.issubset(columns):
        return True
    raise ValueError('Unrecognized notification schema; no table was changed.')


def archive_legacy_notifications(connection):
    if connection.vendor != 'postgresql':
        raise ValueError('The legacy outbox bridge is PostgreSQL-only.')
    from notifications.models import DeliveryAttempt, Notification
    quote = connection.ops.quote_name
    with transaction.atomic(using=connection.alias):
        if not has_legacy_notifications(connection):
            return False
        with connection.cursor() as cursor:
            tables = {row.name for row in connection.introspection.get_table_list(cursor)}
            if any(name in tables for name in ('notifications_yash_archive', 'notifications_yash_attempt_archive')):
                raise ValueError('Legacy archive already exists; inspect it before proceeding.')
            cursor.execute('SELECT current_schema()')
            schema = cursor.fetchone()[0]
            for original, archived in (('notifications_deliveryattempt', 'notifications_yash_attempt_archive'),
                                       ('notifications_notification', 'notifications_yash_archive')):
                if original not in tables:
                    continue
                cursor.execute(f'ALTER TABLE {quote(original)} RENAME TO {quote(archived)}')
                # PostgreSQL index names are schema-wide. Preserve the old indexes
                # under distinct names so the new tables can use their standard names.
                cursor.execute('SELECT indexname FROM pg_indexes WHERE schemaname = %s AND tablename = %s', [schema, archived])
                for index_name, in cursor.fetchall():
                    new_name = 'yash_archive_' + hashlib.sha256(index_name.encode()).hexdigest()[:20]
                    cursor.execute(f'ALTER INDEX {quote(schema)}.{quote(index_name)} RENAME TO {quote(new_name)}')
        with connection.schema_editor(atomic=False) as editor:
            editor.create_model(Notification)
            editor.create_model(DeliveryAttempt)
    return True
