# API conventions (K1)

The React app talks to Django only through `/api/`. The live contract is the OpenAPI schema at
`/api/docs/` (Swagger UI), `/api/redoc/` and `/api/schema/`. In production the docs need a signed-in user
unless `API_DOCS_PUBLIC=true`.

## Layout

| URL | Served by |
|---|---|
| `/api/...` | Django REST Framework (`portal/api/` and the extension modules below) |
| `/legacy/...` | The previous Django-template interface (route names unchanged). Kept until 28 Oct 2026. |
| `/assets/...`, other files in `frontend/dist` | WhiteNoise |
| everything else | `index.html` of the React build (`portal/spa.py`), so client-side routes survive a reload |

## Adding endpoints without editing shared files

`portal/api/urls.py` lists extension modules. Create the module that matches your area and expose
`urlpatterns` (paths are relative to `/api/`). Missing modules are skipped; a module that exists but
fails to import raises, so a typo is never hidden.

| Module | Owner |
|---|---|
| `portal/api/instrument_urls.py` | Y3 records, documents, review, renewal |
| `portal/api/dashboard_urls.py` | Y5 dashboard and search |
| `verification/api_urls.py` | Y6 |
| `obligations/api_urls.py` | S2, S4 |
| `casework/api_urls.py` | S5 |
| `notifications/api_urls.py` | K5 |
| `ai/api_urls.py` | Y8, S7 |
| `audit/api_urls.py` | K7 |

## Rules every endpoint follows

* **Auth:** session cookie. Unauthenticated requests get **401**. Every write sends `X-CSRFToken`
  (read the `csrftoken` cookie; `GET /api/auth/csrf/` sets it). The token rotates on sign-in, so read it
  again after login.
* **Errors:** always `{"detail": str, "code": str, "errors": {field: [messages]}?}`.

  | Status | `code` | When |
  |---|---|---|
  | 400 | `validation_error` | invalid input (`errors` per field) |
  | 401 | `not_authenticated` | no session |
  | 403 | `permission_denied` | wrong role, CSRF failure, own-record rules |
  | 404 | `not_found` | missing **or out of scope** (never reveal other institutions' records) |
  | 409 | `conflict` | `WorkflowError`, including a stale `version` |
  | 429 | `throttled` / `locked_out` | rate limit / sign-in lockout |
  | 503 | `unavailable` | database or storage problem; nothing internal is echoed |

  Raise `WorkflowError`, `PermissionDenied` or `ObjectDoesNotExist` from services; the handler maps them.
* **Lists** use `portal.api.pagination.StandardPagination`:
  `{count, page, page_size, total_pages, results}`; query `page`, `page_size` (max 100).
* **Roles:** use `portal.api.permissions.has_role('officer', ...)` for coarse access and the scoped
  helpers in `portal/permissions.py` for data access. Views validate and call services.
* **Money** is integer paise; dates are ISO `YYYY-MM-DD`; timestamps are ISO 8601.
* **Request IDs:** every response carries `X-Request-ID` (also available as `request.request_id`).
* **Browser rules:** the CSP allows scripts from our own origin only. No inline scripts, no CDN assets,
  no `dangerouslySetInnerHTML`.

## Roles and access (K4)

| Role | Group | Sees | May change |
|---|---|---|---|
| Institution | `Institution` | its own records (incl. drafts) | its own drafts, submissions, renewals, release requests |
| Officer | `Officer` | all submitted records | review, observations |
| Authority | `Authority` | all submitted records | release decision and completion |
| Clearance unit | `Clearance` + `access.UnitAssignment` (PGRC, VIGILANCE, GRANTS) | instruments that have a release case | its own clearance tasks (S5) |
| Auditor | `Auditor` | all submitted history, audit events, access log | nothing |

Use the scoped helpers in `portal/permissions.py` and never filter by IDs from the request body:
`scoped_instruments`, `scoped_documents`, `scoped_release_requests`, `scoped_audit_events`,
`scoped_access_logs` (auditor only), `clearance_unit(user)`, `require_clearance(user, unit)`,
`require_officer`, `require_authority`, `require_auditor`. Unknown or ambiguous role membership fails closed.
Test groups with `Group.objects.get_or_create(name=...)`: migrations do not create groups.

### Access log

Every endpoint that serves a **document, export, report, NOC or staff search** must call

```python
from access.logging import log_access
from access.models import AccessLog
log_access(request, AccessLog.DOCUMENT_DOWNLOAD, document, detail='instrument=%d' % document.instrument_id)
```

before it sends the file (also accepts a DRF request; actions are free strings: `EXPORT`, `REPORT`,
`NOC_VIEW`, `SEARCH`, ...). If a view forgets, `AccessLogMiddleware` still records any successful GET whose
path contains `download`, `export` or `report`, or ends in `.csv`/`.xlsx`/`.pdf`, as `DOWNLOAD`. Sign-in,
sign-out and failed sign-in are logged automatically (the attempted username only, never the password).
`AccessLog` rows are append-only (`AppendOnlyError` on update or delete).

Demo accounts: `python manage.py seed_staff --generate-password` creates `clearance_pgrc`,
`clearance_vigilance`, `clearance_grants` and `auditor` and writes `data/staff-credentials.txt` (git-ignored).

## Notifications (K5)

```python
from notifications.service import notify
from notifications import recipients as who

notify(who.officers(), 'instrument_submitted',
       {'reference': instrument.reference, 'url': f'/records/{instrument.pk}'},
       key=f'instrument:{instrument.pk}:submitted:v{instrument.version}')
```

* `recipients`: users, user ids or plain email addresses. Helpers in `notifications/recipients.py`:
  `officers()`, `authorities()`, `auditors()`, `clearance_users(unit=None)`, `institution_users(inst)`,
  `institution_contacts(inst)` (users plus the AICTE profile contact email).
* `template`: an id from `notifications/catalog.py`. Unknown ids still work if the context has `subject` and
  `message`. Add real templates there (K owns the file) when you need new wording.
* `key`: idempotency key of the **event**. Repeating a call with the same key and recipient does nothing, so it
  is safe in retries and in `run_due_rules`. Include the version or date that makes the event unique.
* `url`: a React path (`/records/42`), never an absolute URL. Messages carry a reference only, never amounts or
  account details.
* Call it inside the event's transaction: the row is rolled back with the event (outbox). Email is attempted right
  after commit; `python manage.py send_notifications` retries (5 attempts, 5/15/60/240 min backoff).
* API: `GET /api/notifications/` (own inbox, `?unread=1`), `GET /api/notifications/unread-count/`,
  `POST /api/notifications/{id}/read/`, `POST /api/notifications/read-all/`,
  `GET /api/notifications/delivery-status/` (auditor only, no message content).

## Auditor endpoints (K7)

Auditor role only (403 for everyone else, 401 when signed out). Drafts stay private, so they never appear.

| Endpoint | Purpose |
|---|---|
| `GET /api/audit/events/` | audit trail; filters `instrument`, `q` (reference), `institution`, `actor`, `actor_name`, repeated `action`, `date_from`, `date_to` (YYYY-MM-DD, business timezone, inclusive) |
| `GET /api/audit/events/{id}/` | full `before` / `after` snapshots and computed `changes` |
| `GET /api/audit/events/facets/` | actions, actors, institutions for the filter lists |
| `GET /api/audit/access-log/` | filters `user`, `username`, repeated `action`, `object_type`, `object_id`, `ip`, dates |
| `GET /api/audit/access-log/facets/` | actions and object types |
| `GET /api/audit/events/export/`, `GET /api/audit/access-log/export/` | CSV (at most 5,000 rows, formula-safe); each export is itself access-logged |

## Audit hash chain (K9)

Every `AuditEvent` is sealed (`audit.AuditSeal`) in the same transaction that writes it:
`hash = HMAC-SHA256(AUDIT_CHAIN_KEY, prev_hash | canonical event JSON)`. Seals are append-only and the database
rejects a second seal with the same `prev_hash` (no forks).

* `python manage.py verify_audit_chain` exits non-zero when an event was edited, removed or inserted
  (`event_modified`, `event_missing`, `chain_break`, or unsealed rows). `GET /api/audit/chain/verify/` returns the same
  result for the auditor screen.
* `python manage.py seal_audit_chain` seals older events; they are marked `backfilled` ("sealed late"): this proves
  they were not changed since, not that they were correct when written. `run_portal.py` runs it after `migrate`.
* Do not create audit events with `bulk_create` or raw SQL: they would be reported as unsealed.
* On PostgreSQL, triggers (`audit.0002_append_only_triggers`) also reject `UPDATE` and `DELETE` on the event, seal, access-log
  and verification-evidence tables; see [supabase](supabase.md). Run the app as a non-owner role.
* Limits: the chain detects tampering after the fact and the triggers can be disabled by a table owner. Anchoring the chain
  head in write-once storage is still open, so a database administrator could rebuild the chain.
* SQLite now runs with `transaction_mode=IMMEDIATE` so writers queue instead of racing.
