"""PostgreSQL triggers that make the evidence tables append-only (P1-4).

The application already refuses to update or delete these rows (`AppendOnlyQuerySet`, `save()`/`delete()` guards), and
the audit hash chain detects a changed row afterwards. The triggers add prevention: a database session that tries
`UPDATE` or `DELETE` on one of them fails, whoever is connected. They apply to PostgreSQL only; SQLite (local demo and tests)
keeps the application-level guards.

A table owner or superuser can still `ALTER TABLE ... DISABLE TRIGGER`, so run the application as a role that does not own
these tables (docs/supabase.md); `check_supabase --privileges` reports it. `TRUNCATE` is not covered by row triggers.
"""
FUNCTION = 'forbid_append_only_change'
# (app label, model name): the tables that must never change after insert.
MODELS = (('portal', 'AuditEvent'), ('audit', 'AuditSeal'), ('access', 'AccessLog'),
          ('verification', 'VerificationEvidence'))


def trigger_name(table):
    return f'{table}_append_only'[:63]


def tables(apps):
    return [apps.get_model(app, name)._meta.db_table for app, name in MODELS]


def install(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    quote = schema_editor.quote_name
    schema_editor.execute(f"""
        CREATE OR REPLACE FUNCTION {quote(FUNCTION)}() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% on % is not allowed: the table is append-only', TG_OP, TG_TABLE_NAME
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql""", params=None)  # params=None: the % signs are RAISE placeholders, not driver placeholders
    for table in tables(apps):
        schema_editor.execute(f'DROP TRIGGER IF EXISTS {quote(trigger_name(table))} ON {quote(table)}')
        schema_editor.execute(
            f'CREATE TRIGGER {quote(trigger_name(table))} BEFORE UPDATE OR DELETE ON {quote(table)} '
            f'FOR EACH ROW EXECUTE FUNCTION {quote(FUNCTION)}()')


def remove(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    quote = schema_editor.quote_name
    for table in tables(apps):
        schema_editor.execute(f'DROP TRIGGER IF EXISTS {quote(trigger_name(table))} ON {quote(table)}')
    schema_editor.execute(f'DROP FUNCTION IF EXISTS {quote(FUNCTION)}()')


def report(cursor, schema, apps):
    """Read-only findings as (ok, message) pairs for `check_supabase --privileges`."""
    findings = []
    for table in tables(apps):
        cursor.execute(
            "SELECT t.tgenabled FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relname = %s AND t.tgname = %s AND NOT t.tgisinternal",
            [schema, table, trigger_name(table)])
        row = cursor.fetchone()
        enabled = bool(row) and row[0] == 'O'
        findings.append((enabled, f'{table}: append-only trigger {"active" if enabled else "MISSING or disabled"}'))
    cursor.execute('SELECT rolsuper FROM pg_roles WHERE rolname = current_user')
    superuser = bool((cursor.fetchone() or [False])[0])
    findings.append((not superuser, 'connected role is a superuser: it can disable the triggers' if superuser
                     else 'connected role is not a superuser'))
    cursor.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = %s AND c.relname = ANY(%s) AND pg_get_userbyid(c.relowner) = current_user",
        [schema, tables(apps)])
    owned = cursor.fetchone()[0]
    findings.append((owned == 0, f'connected role owns {owned} of the {len(MODELS)} append-only tables'
                     + (': it can disable their triggers; run the app as a non-owner role' if owned else '')))
    return findings
