# Restore the database and the documents

The database holds the records and the audit trail; `data/documents/` holds the PDFs. Each is only meaningful with the other
(a record row points to a file and its SHA-256), so they are **always backed up and restored together**, and with the same
`AUDIT_CHAIN_KEY` ([key runbook](audit-chain-key-rotation.md)): a restore under a different key fails chain verification.

What you need to keep, per environment: the database backup, a copy of `data/documents/`, `AUDIT_CHAIN_KEY`, and
`DJANGO_SECRET_KEY` (in your secret store, never in the backup folder).

## Back up

Stop writes if you can (a short maintenance window gives a consistent copy).

**Supabase PostgreSQL** (the app's tables are in the `portal_app` schema):

```bash
pg_dump --format=custom --schema=portal_app --no-owner --file=portal-$(date -u +%Y%m%dT%H%M%SZ).dump "$DATABASE_URL"
```

`DATABASE_URL` is the Session pooler string from the dashboard (see [supabase](../supabase.md)). Do not echo it.

**SQLite** (local demo): stop the server, then copy `data/portal.sqlite3`.

**Documents** (both): copy the whole folder, preserving file names:

```bash
cp -a data/documents "backup-documents-$(date -u +%Y%m%dT%H%M%SZ)"
```

On Docker the data lives in the `portal-data` volume ([docker](../docker.md)); copy it with `docker compose cp web:/app/data/documents ./backup-documents`.

Record the audit head with the backup: `python manage.py verify_audit_chain` prints `Head: <hash>`. Store backups privately
and off the server; they contain every record.

## Restore into a new place

Never restore over the only copy of existing data. Use a new project or a new empty folder.

1. **New database.** Create a new Supabase project (or an empty SQLite path). Put its Session pooler URI in the new
   environment's `DATABASE_URL`, then prepare the schema: `python manage.py check_supabase --initialize`
   (do **not** run `--migrate` yet if you are loading a dump; the dump contains the tables).
2. **Load the dump:**
   ```bash
   pg_restore --no-owner --schema=portal_app --dbname="$DATABASE_URL" portal-<timestamp>.dump
   ```
   For SQLite, put the backed-up file at `data/portal.sqlite3`.
3. **Put the documents back** into `data/documents/` of the new deployment (or its volume), file names unchanged.
4. **Set the same keys.** `AUDIT_CHAIN_KEY` exactly as before (and `DJANGO_SECRET_KEY`, or the pinned audit key if it was a
   derived one).
5. **Migrate forward, if the code is newer than the dump:** `python manage.py migrate`.

## Verify before anyone uses it

```bash
python manage.py check
python manage.py verify_audit_chain          # must say OK and print the head you recorded
python manage.py shell -c "
import hashlib
from portal.models import Document
bad = []
for d in Document.objects.iterator():
    try:
        with d.file.open('rb') as f:
            h = hashlib.sha256(f.read()).hexdigest()
    except FileNotFoundError:
        bad.append((d.pk, 'missing')); continue
    if h != d.sha256:
        bad.append((d.pk, 'changed'))
print('documents with a problem:', len(bad), bad)"
```

Expected: chain `OK`, and `documents with a problem: 0`. Then sign in as the officer and as an institution user, open a
record, download its PDF and check the notifications bell.

| Result | Meaning | Do |
|---|---|---|
| `broken` chain | Wrong `AUDIT_CHAIN_KEY`, or the dump and the audit table are from different moments | Recheck the key; if it is right, [broken chain runbook](broken-audit-chain.md) |
| `missing` documents | The documents copy is older than the dump | Restore a newer documents copy; a record without its file must not be accepted or released |
| `changed` documents | The file differs from the hash recorded at upload | Treat as tampering or corruption: do not use the file, ask the institution to upload it again |

## Restore drill

Do this once before relying on the backups, and after any change to storage: restore into a scratch project, run the
verification above, delete the scratch project. Write down how long it took.
