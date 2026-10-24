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
