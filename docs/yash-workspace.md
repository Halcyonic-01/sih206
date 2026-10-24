> After the team-main merge, use the shared SPA (`/records`, `/dashboard`,
> `/reconciliation`, `/notifications`) and `/legacy/` for old templates.
> `/workspace` is retained as a compatible records route. Platform notification
> service/scheduler and shared auth/client supersede the prototype implementations.
> See [Supabase setup](supabase.md) for existing-database compatibility upgrades.

# Yash feature handoff: Y1-Y8

## Run locally

Use Python 3.12 and Node 24 LTS (PDF.js requires Node >=22.13 or >=24).
From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
cd frontend
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe manage.py seed_demo --generate-password
.\.venv\Scripts\python.exe manage.py seed_demo --authority-only --generate-password
.\.venv\Scripts\python.exe manage.py seed_scenarios
.\.venv\Scripts\python.exe manage.py seed_yash_examples
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8010 --noreload
```

Open `/workspace/`. It uses the existing Django sign-in page; private random demo
credentials remain in ignored `data/demo-credentials.txt`. Seed commands preserve
existing accounts and records. Do not paste credentials into issues or screenshots.
Existing `/` routes and templates remain available. See [the OCR, notification and bank-channel handoff](pending-integrations.md) for the new integration setup and tested boundaries. No live bank/provider connection or public deployment is claimed.

The minimal frontend entry, settings/URL registration, and release evidence page-count
assignment were explicitly approved by Yash while the shared K1/K2 code was absent.
Kushagra may mount `RecordsWorkspace` in the final shell using its injected `Api`
adapter instead. Same-origin session cookies and CSRF are required; no browser-storage
tokens. The static bundle is generated locally and is not committed.

## Task status and boundaries

| Task | Implementation | Remaining handoff |
|---|---|---|
| Y1 | Deposit modes, institution-validated obligation FK, bank/payment metadata, nullable lien, verification level, document categories/page count; additive 0005 migration | Review by K; S1 is merged upstream |
| Y2 | Killable PDF parser with 10-second deadline, strict structure checks, page count, rejection of encryption/active content/embedded files; observation bounds | Parsing is not antivirus, authenticity validation or an OS memory sandbox |
| Y3 | Scoped records/search/filter/page/export/detail/create/edit/submit/review/observations/resolve/renew/correct/upload/download APIs; action flags; optimistic writes; retained evidence | Outbox and session/client integration added; authoritative OpenAPI/platform review remains |
| Y4 | Records/form/detail tabs/PDF.js viewer, officer actions, corrections, typed upload and renewal; error/empty/loading states | Shared client/AuthProvider added; retain compatibility with the team shell |
| Y5 | Six PS categories, scope-preserving search/date filters, intervention queues and accessible maturity chart | Scoped coverage from reviewed stored requirements added; full programme/rule calculation still belongs to S2. Unknown policy stays unknown |
| Y6 | Append-only ORM evidence; officer review evidence; bounded synthetic statement CSV preview/commit, UTR/amount/date comparison, ambiguity handling, replay prevention and stale-version rollback; officer-only cross-institution duplicate warning; configured-prefix issuer warning | Signed-link/OTP bank workflow and notification outbox added. Live bank configuration/response and a reviewed issuer directory remain external prerequisites |
| Y7 | Verification evidence tab and synthetic reconciliation upload/preview/commit/results screen | No claim that synthetic matches establish bank confirmation |
| Y8 | Shared ai module/AiRun, no-tools schema-constrained PDF extraction transport with 30-second hard deadline, field/page validation, advisory mismatch display and explicit prefill; disabled/manual fallback | Prepared before P0 merge with explicit Yash approval. Live provider calls and real-document accuracy have not been tested |

Yash explicitly requested local OCR and the bank workflow after the initial build. Other Stage 3 work (copilot, live feeds, Locker delivery and fuzzy matching) remains outside this implementation.

## API routes (all under /api/)

- `GET/POST instruments/`; `GET/PATCH instruments/{id}/`.
- `POST instruments/{id}/submit|review|renew|correct|documents|observations/`.
- `POST instruments/{id}/observations/{observation_id}/resolve/`.
- `GET instruments/export.csv` (same query filters); `GET documents/{id}/download/`.
- `GET dashboard/`; `GET instruments/{id}/verification/`.
- `GET/POST verification/statements/`; `POST documents/{id}/ai-extract/` and `ocr/`.
- `GET/POST instruments/{id}/bank-requests/`; public form `/bank/confirm/{token}/`.
- `GET notifications/`, `GET notifications/deliveries/` (officer); `POST notifications/{id}/read/`.
- `GET obligations/`; session endpoints under `auth/`.

Lists accept `q`, `category`, `mode`, `status`, `verification_level`,
`maturity_from`, `maturity_to`, `page`, `page_size` (max 100).
Monetary writes use decimal INR `amount` strings; storage stays integer paise.
Mutation bodies require `version`; renewal uses the predecessor's version.
Record create/edit accept multipart PDFs or JSON fields. Institution ownership,
verification and workflow fields cannot be assigned through the write serializer.
Responses include `actions`; backend services independently enforce permissions.

Statement files: UTF-8 CSV, exact header `utr,amount,value_date`, positive
two-decimal INR amount, ISO date; max 1 MB/1,000 rows. First POST a `document` to
preview; then POST it with `commit=true`, a synthetic `source` label and the
JSON-encoded `versions` map returned by preview. Duplicate UTRs/multiple candidate
records are ambiguous, not automatically matched. Synthetic matches append
`SIMULATED_STATEMENT` evidence but never set `CONFIRMED`. Amount/date discrepancies
create blocking observations when a supporting document exists. The portal does
not change held amounts or execute payments during reconciliation.

`seed_yash_examples` adds one matching and one mismatching RTGS record without
altering existing records. `fixtures/synthetic-statement.csv` is its corresponding
synthetic input. Use it to demonstrate both results through the reconciliation UI.

Evidence is append-only through the supported model/queryset API, not tamper-proof
against direct SQL or database administrators. K's stronger audit controls remain
separate. Changed declarations/uploads reset the current verification label while
retaining previous version-specific evidence.

## Integration contracts

`portal.api.records_urls` remains independently mountable. Shared auth/session endpoints,
frontend client/AuthProvider and `notifications.services.notify` are now connected.
Disabling `YASH_NOTIFY_BACKEND` explicitly returns `notification_queued=false`.
Queueing is distinct from actual delivery. See [integration setup](pending-integrations.md).

`VERIFICATION_ISSUER_PREFIXES` is an optional reviewed tuple of four-letter prefixes.
It defaults to empty; no bank directory has been invented or scraped. Even a listed
prefix establishes neither branch existence nor FDR authenticity.

Scoped coverage reads reviewed stored requirements. Authoritative programme-to-required-amount rules and policy publication remain S2 work; missing policy is never inferred.

## Optional AI configuration

AI is off unless the operating-system variable `AI_ENABLED=true` is deliberately
set. Model: Google Gemini `gemini-3.8-flash` (`AI_MODEL`). Set `GEMINI_API_KEY` privately if testing authorized
synthetic documents. No key is saved in the repo or frontend. The UI requires an
explicit synthetic-data declaration and consent to transfer to Google Gemini before an
enabled request. Max 10 MB/30 known pages; 10 attempted calls per user per hour.
No documents were sent during development; provider tests are mocked.

Output is locally checked against the six-field contract with evidence pages.
It can only prefill an editable form for a user to review and explicitly save.
Missing credentials, disabled AI, timeout, refusal, malformed output and integrity
failure retain the manual workflow. AiRun stores metadata and bounded suggestions,
not raw PDF bytes or provider error messages. S7 can reuse `call_model(payload)`
for its separate structured-JSON summary feature; no S7 workflow is implemented here.

## Verification and demo

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate --check
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe scripts/evaluate_release.py --output data/yash-evaluation.json
cd frontend
npm ci
npm run build
npm audit
npx playwright install chromium
npx playwright test
```

Browser tests require a locally running server, seeded synthetic accounts and the
built frontend. They add synthetic records and retain decisions, so use an isolated
demo database for rehearsal. Passwords are read privately, never logged; traces are
off. Tests exercise real session login/CSRF, creation, PDF rendering, AI-off fallback,
submission, discrepancy, correction/resubmission, resolution, acceptance/evidence,
renewal, dashboard, narrow viewport and reconciliation preview/commit.

The frozen 24-case metadata/10-case envelope evaluation is preserved. Its upload
section explicitly calls the historical envelope helper, not the new parser; Y2's
parser/security behavior is tested separately. Old result files/labels are untouched.
No real-world extraction, bank-authentication, regulatory or performance accuracy
claim is made.

The offline packager includes the records, verification and AI apps plus the built
workspace and PDF worker. Build the frontend first, then prepare platform-matching
Python 3.12 wheels and the archive from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip download --only-binary=:all: --dest .offline-wheels -r requirements.txt pip==26.2.1
.\.venv\Scripts\python.exe scripts/build_offline_demo.py
```

Extract the ZIP into a fresh folder and run `Setup-Offline.ps1`, then `Start-Demo.ps1`.
Open `http://127.0.0.1:8000/workspace/` with the locally generated demo credentials.
Python 3.12 must already be installed; Node is needed only when building the bundle.
The wheels prepared on this machine target Windows x64. Private data, credentials,
planning files and node_modules are excluded. Package hashes check integrity, not
publisher authenticity. The installer uses bundled wheels with `--no-index`; a
physically disconnected rehearsal remains a team acceptance check. This is a local
synthetic demo, not a production release.
