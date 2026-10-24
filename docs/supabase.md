# Connect Django to Supabase PostgreSQL

This integration uses Supabase as Django's PostgreSQL database. React continues
to call the scoped Django APIs with the existing session login. Document files
still use the protected local storage backend; Supabase Auth/Storage are separate
integrations. No database password or privileged API key belongs in frontend code.

## Get the connection string

1. Sign in at https://supabase.com/dashboard and open/create a project.
2. Keep the project's database password in your password manager.
3. Click **Connect → Session pooler** and copy the **URI** string on port **5432**.
4. Put that complete string in the repository's ignored `.env` as `DATABASE_URL`.
   Replace `[YOUR-PASSWORD]` with the actual database password. Percent-encode URI
   punctuation inside the password, such as `@` → `%40` and `#` → `%23`.
   Copy the actual host/username from the dashboard; do not invent the region host.
5. Keep these additional settings:

```dotenv
DATABASE_SCHEMA=portal_app
DATABASE_SSLMODE=require
```

Do not paste the URI/password into chat, screenshots, Git or frontend `.env` files.
A Supabase project URL or publishable/anon API key cannot replace a database URI.
The Session pooler supports IPv4. A direct database connection also works on a
network with the appropriate IPv6/IPv4 support. This integration rejects the
transaction pooler on port 6543 because it uses session schema state.

Settings load the root `.env` with the shared platform loader, without overriding explicitly
set process variables or expanding `${...}` in passwords. To force offline SQLite,
set `DATABASE_BACKEND=sqlite` in the process environment. With `auto` (default), an
empty URL uses SQLite; a nonempty invalid URL fails clearly instead of silently
using SQLite. When editing `.env`, restart Django to load the changes.

## Initialize and verify

From the repository root, using Python 3.12:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py check_supabase --initialize --migrate
.\.venv\Scripts\python.exe manage.py check_supabase
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8010 --noreload
```

The first check connects using TLS, creates the private `portal_app` schema,
removes Data API role/public schema access and future default grants in that
schema, then applies Django migrations there. It does not drop tables or rewrite
existing Supabase public/auth/storage schemas. Without flags the check is
read-only; it reports whether the connection/search_path/schema are ready.
Initialization requires a database owner/role with the required schema privileges.
Errors are summarized without printing the URL/password.

In Supabase's Table Editor choose schema `portal_app` to inspect the app tables.
Keep this schema out of the **Data API exposed schemas** list. Browser users reach
these tables through Django's role and institution checks, not the Supabase Data
API. Do not grant `anon`, `authenticated` or `service_role` access to this schema.
The project-owner connection is for development/bootstrap; use a dedicated,
appropriately restricted database role for production deployment.

`sslmode=require` encrypts the connection. For production certificate/hostname
verification, obtain the project's CA certificate from Supabase and configure
`DATABASE_SSLMODE=verify-full` plus `DATABASE_SSL_ROOT_CERT` with its absolute path.
No live cloud connection is established until the actual URI is configured.

## Existing data and accounts

If this development project used Yash's prototype notification schema before the
team-platform merge, the check refuses to silently use the incompatible tables.
Use this explicit, non-destructive upgrade after reviewing the branch:

```powershell
.\.venv\Scripts\python.exe manage.py check_supabase --upgrade-legacy-notifications --migrate
```

It retains all earlier notification and delivery-attempt rows in the private
`notifications_yash_archive` and `notifications_yash_attempt_archive` tables,
and creates the authoritative shared outbox tables. The active inbox starts
fresh; archived history remains available to database administrators. It does
not reset users, deposit records, documents or Django's applied-migration history.
The operation is transactional and is a no-op once the shared tables are present.
Unknown layouts or an existing archive with an incompatible active table fail
without overwriting data. This bridge has also been exercised on a temporary
PostgreSQL schema, with every synthetic row and DDL change rolled back afterward.

A fresh Supabase database starts empty. Existing SQLite records, account password
hashes and local documents are not transferred automatically. This deliberately
avoids copying local/private records into an unspecified remote project. Choose
and review a separate data-transfer plan if the team needs that migration.

For fresh synthetic accounts, `manage.py seed_demo` can prompt privately for a
password without replacing the existing SQLite credential files. Use synthetic
accounts/data only for development; do not run broad data imports casually.
The local SQLite file remains available when `DATABASE_BACKEND=sqlite` is selected.
Do not delete the local database or document directory to connect Supabase.

## Tests and offline compatibility

`manage.py test` always selects local SQLite even if `.env` contains a live
`DATABASE_URL`. It will not create/drop a Supabase test database. Configuration
tests cover TLS, percent-encoded credentials, private-schema validation, pooler
selection, secret-safe errors and offline selection. The connection command's
initialization/migration behavior is unit-tested with a mock connection.
Passing those tests does not prove live Postgres schema/workflow compatibility;
run the connection/migration and scoped application checks on a dedicated
Supabase development project before treating it as validated.

Offline Setup/Start/Verify commands explicitly select SQLite. The archive excludes
the private `.env`; it includes pinned PostgreSQL/dotenv wheels alongside the
existing dependencies. Distribution-name canonicalization handles wheel metadata
such as `typing_extensions` versus the requirements name `typing-extensions`.

Official references:
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/docs/guides/api/securing-your-api
- https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes
