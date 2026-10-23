# FDR Portal — Milestones 1–6

**Release status:** localhost synthetic-demo candidate; public/real-data deployment is blocked. The release audit passed 159 tests and the bounded synthetic rule evaluation, but target-browser visual/offline rehearsal remains unverified. Read [release-readiness report](docs/release-readiness.md), [implemented architecture](docs/architecture.md), and [five-minute demo/fallback](docs/demo-script.md) before presenting. This is an FDR lifecycle MVP, not an OCR/AICTE policy-validation system.

A local, synthetic-data demonstration of **institution submission → protected PDF → scrutiny/corrections → officer acceptance → maturity reporting → linked renewal or authority-controlled release**, with preserved audit history and evidence-backed completion.

Milestones 1–6 are implemented. There is no OCR, bank verification, notification delivery, or payment execution. Officer acceptance means **accepted for tracking**, not bank authentication or regulatory compliance. Every detail page explicitly says **Not independently bank-verified**. Release authorization and evidence-backed completion are separate human actions.

## Milestone 6 update

The register exports its current authorized view as CSV, with the same category/date filters and spreadsheet formula protection. No database migration or application dependency was added. The offline distributable includes pinned wheels, source, local assets, tests and synthetic fixtures; it excludes existing databases, uploads and credentials. Python 3.12 must already be installed on the demo machine.

See [offline setup, synthetic scenarios, verification and recovery](docs/offline-demo.md) for exact commands and file responsibilities, and [final verification evidence](docs/final-verification.md) for measured results. Use `Start-Demo.ps1` to run the current application and `Verify-Demo.ps1` for the complete acceptance suite. Build a new distributable with `.\.venv\Scripts\python.exe scripts\build_offline_demo.py` after downloading the pinned wheels as documented.

The `seed_scenarios` command creates 17 synthetic instruments through existing workflow services and never resets existing decisions. Offline setup runs this in its own extracted folder. The original workspace data remains separate. The sections below describe the preserved earlier milestones.

## Milestone 5 update

Institutions can request release of their own accepted current instruments. A separate Authority role approves or rejects with reasons. Approval keeps maturity monitoring active; only a separate completion action with a new PDF and explanation records completion and removes the instrument from current monitoring.

- One open request per instrument, with preserved rejected/completed histories.
- Institution/Officer accounts cannot authorize or complete releases; requesters cannot act on their own requests after changing roles.
- Pending/authorized releases block renewal, and an existing renewal proposal blocks conflicting release requests.
- Evidence PDFs are classified separately from FDR documents and use protected downloads.
- Instrument state, release state, evidence metadata and audit entries commit together; known failures roll back and remove the new file.
- No funds are transferred or bank authenticity/settlement inferred.

The additive `0004_release_workflow` migration is applied. Existing records/accounts are preserved, and a pre-update backup is in ignored `data/backups/`. No new dependency or environment variable is needed.

The new `authority` account is available in this workspace. Its password is in ignored `data/authority-credentials.txt`; existing passwords remain in `data/demo-credentials.txt`. On another Milestone 4 installation:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo --authority-only --generate-password
```

Use **Release requests** in navigation, or open **http://127.0.0.1:8000/releases/**. The Authority queue defaults to pending requests; select Approved to find cases awaiting completion. Read `docs/releases.md` for scope and exact behavior. Milestone 6 packaging and CSV are documented in docs/offline-demo.md.

## Milestone 4 update

Accepted current instruments now offer **Create renewal draft**. The new instrument has its own details/PDF and a fixed predecessor link. The predecessor stays current through draft, submission and corrections; only officer acceptance atomically supersedes it. Original records/documents remain accessible through lineage links and the All visible records register.

- One retained successor proposal per predecessor; continue an existing draft instead of creating competitors.
- Same-institution links only; no reparenting, self-links or cycles through the supported application workflow.
- Current maturity views/reports exclude superseded instruments and count the accepted successor once.
- Supersession is separate from review status: old records retain their acceptance history with an explicit Superseded timestamp/badge.
- Draft successor details remain private from officers until submission. Officers can see a generic renewal-start audit event without private draft metadata.
- Milestone 4 added no cancellation, branching or automatic bank verification. Milestone 5 release handling is documented above.

The additive `0003_instrument_renewal` migration is applied in this workspace. A pre-update SQLite backup is under ignored `data/backups/`; existing account/domain fields were verified unchanged after migration. No new dependency or environment variable is needed.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py test portal.tests --verbosity 2
```

Read `docs/renewals.md` for exact renewal workflow and safeguards, and `docs/releases.md` for the release interaction.

## Milestone 3 update

Maturity reporting uses the existing instrument dates and review states. No new dependencies, models or database migrations were added. The existing database was backed up under ignored `data/backups/` before the update.

- Open **http://127.0.0.1:8000/dashboard/** after signing in, or use the Dashboard navigation link.
- Counts link to institution-scoped filtered lists: pending review, accepted current records, approaching maturity, matures today and matured.
- Accepted current records include matured instruments but exclude superseded predecessors and completed releases; approved releases remain monitored. The maturity cards are subsets, not additional disjoint totals.
- Only accepted records enter maturity action lists. Draft/submitted/correction records still show declared maturity facts in their register/detail views.
- The original landing behavior remains: institution register or officer pending queue.
- Maturity is calculated at read time. It does not change review state, determine regulatory noncompliance, or confirm a bank instrument.

Default demo thresholds are 30/15/7 days, and the business timezone is Asia/Kolkata. Optional environment variables are `REMINDER_DAYS` and `BUSINESS_TIMEZONE`; see `.env.example`. Local DEBUG-mode dashboard/register forms support an explicit, visibly labeled evaluation date. Detail pages always show the actual business date.

Run the read-only due-action report:

```powershell
.\.venv\Scripts\python.exe manage.py due_actions --as-of 2026-10-23
.\.venv\Scripts\python.exe manage.py due_actions --as-of 2026-10-23 --institution DEMO-A
```

Without `--as-of`, the command uses the current date in the configured business timezone. It prints a report only: no notifications, files, audit events or status changes are created. The CLI is for a trusted local operator and defaults to all institutions. No scheduler or notification-delivery service has been deployed.

Read `docs/maturity.md` for exact category/band behavior and verification instructions. Renewal monitoring changes are documented in `docs/renewals.md`.

## Milestone 2 update

The existing Milestone 1 application, accounts, documents, instruments and audit events are preserved. Before applying the additive `0002_reviewobservation` migration, a SQLite backup was created under ignored `data/backups/`. Existing domain/account rows were compared with that backup after migration and were unchanged.

No new dependencies or environment variables are required. On an existing Milestone 1 installation, stop/restart the development server around the update and run:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py test portal.tests --verbosity 2
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

New functionality:

- Current technical findings: missing FDR PDF (blocking), possible same-institution duplicate bank/reference (warning).
- Officer observations tied to a specific PDF and an optional positive page number.
- Blocking observations prevent acceptance until an officer explicitly resolves them with an explanation.
- Corrections do not erase findings or automatically resolve observations.
- Original and resolved observations remain in the detail page and audit snapshots.

Read `docs/checks.md` for the exact checks, permissions, workflow restrictions and limitations. These are technical/demo checks, not AICTE policy validation.

## Environment inspected

The workspace was empty and was not a Git repository. No existing project work was overwritten.

- The `py` launcher reported no installed Pythons.
- The default `python` command resolved to MSYS Python 3.10.11.
- The Codex bundled runtime provides Python 3.12.14.
- `uv` is installed. The selected Django version is pinned in `requirements.txt`.
- The bundled runtime's normal venv creation reached an `ensurepip` failure. The environment was provisioned with `uv pip`, which does not need pip inside the venv.

## Exact setup commands (PowerShell)

Run from `C:\Saksham\Code files\SIH3rd`.

**The current workspace already has `.venv`, dependencies, and database migrations applied. Skip environment creation if `.venv` exists.** The portable runtime path below is specific to the inspected machine.

```powershell
Set-Location -LiteralPath 'C:\Saksham\Code files\SIH3rd'
& 'C:\Users\sriva\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m venv --without-pip .venv
uv pip install --python .venv\Scripts\python.exe --cache-dir .uv-cache -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
```

On another machine with standard Python 3.12, use `py -3.12 -m venv .venv` and `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` instead. Do not delete/recreate an existing environment blindly.

No activation, Node, API keys, or database service are needed. Network access is needed to download packages on a fresh setup, but not to run the application.

### Demo accounts

The current workspace is seeded with `institution_a`, `institution_b`, `officer`, and `authority`. Open ignored `data/demo-credentials.txt` for the original accounts and `data/authority-credentials.txt` for the Authority password. No credentials are committed or embedded in application code.

On a fresh database, choose either interactive setup:

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo
```

Or local-only random credentials:

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo --generate-password
```

The seed command never resets existing accounts or passwords. The generated-credentials option refuses to overwrite an existing credentials file when new accounts are needed. Use synthetic data only and do not share this file.

### Start the application

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Open **http://127.0.0.1:8000/**. Stop with Ctrl+C. This is Django's local development server; it is not a production deployment.

## Verify all implemented milestones automatically

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test portal.tests --verbosity 2
```

Tests use a separate test database and temporary document directories. They do not reset the demo database. The Codex sandbox initially denied its temporary-file operations; the test command was rerun with approved filesystem access. A normal local terminal should not need that Codex-specific approval.

For an optional live HTTP smoke test, with the server running and generated demo credentials available:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_http.py
# Stop and restart the server, then:
.\.venv\Scripts\python.exe scripts/smoke_http.py --verify
```

This creates one accepted synthetic `SMOKE-...` instrument in the local database. It uses actual HTTP cookies, CSRF tokens, and PDF uploads, and checks persistence after restart. It does not print credentials. It is separate from the isolated unit/integration suite.

The suite checks real sign-in/POST logout/CSRF, creation, submission, officer acceptance, required decision reasons, correction/resubmission, original PDF bytes/hash, preservation of documents/values, institution isolation, unauthenticated access, role restrictions, self-review denial, input validation, locked records, stale requests, invalid/oversized files, rollback on audit failure, and idempotent account seeding.

### Verified implementation results

- Django system checks: passed.
- Migration drift check: no changes detected.
- Automated suite: **134 tests passed** (103 prior tests plus 31 release tests).
- Live localhost HTTP workflow: passed, including real PDF uploads, correction/resubmission, acceptance, protected downloads, institution isolation, and CSRF rejection.
- Milestone 2 live scrutiny workflow: passed, including a same-institution duplicate warning, page-1 amount observation, blocked acceptance after correction, explicit resolution, and unchanged bank-verification disclaimer.
- Milestone 3 live maturity workflow: passed, including 7/15/30/31-day boundaries, dashboard/card list agreement, institution isolation, and repeated report runs with identical output and unchanged database hashes.
- Milestone 4 live renewal workflow: passed, including linked drafts, correction/resubmission, competing-proposal rejection, supersession audit, preserved PDFs and current monitoring of the successor only.
- Milestone 5 live release workflow: passed, including independent authority decisions, rejection, missing-evidence blocking, separate PDF-backed completion, protected evidence and monitoring cutover.
- Server stopped/restarted: accepted record, decision history, old/new values, and both PDF downloads remained available.
- All five milestones' live restart checks passed; original documents, observations, resolutions, maturity reporting, renewal lineage, release decisions and completion evidence persisted.
- Existing instrument/document/observation/audit rows, account credentials and role assignments were compared with the pre-Milestone-3 backup and preserved. Original PDF hashes matched.
- The same preservation check passed against the pre-Milestone-4 backup, comparing all original columns after the additive migration; old records received no inferred lineage or supersession.
- The pre-Milestone-5 preservation check also passed: existing records, credentials, roles and PDF hashes are unchanged; existing documents are classified as FDR and no old release history was inferred.
- Embedded browser preview could not initialize in the tool environment, so visual browser QA is still a manual check. The live HTTP test is not a claim of visual verification.

Milestones 1–6 are implemented; see docs/offline-demo.md for final setup and verification.

## Verify Milestone 5 manually

1. As an institution, open an accepted current instrument without a successor proposal. Submit a release reason.
2. Confirm the request is Pending and the instrument is still monitored. New renewal proposals must be blocked.
3. As Authority, open **Release requests**, inspect the record and authorize with a reason. Institution/Officer decision attempts must fail.
4. Confirm **Release authorized; completion pending**. The record must still appear in current maturity views.
5. Try completion without a PDF: validation must block it.
6. Upload a new synthetic completion PDF, enter an explanation, and record completion as Authority.
7. Confirm original FDR/evidence downloads and audit history remain available, while the record leaves current monitoring. Bank verification remains unconfirmed and no payment is executed.
8. On a separate synthetic record, reject a request with a reason. Confirm it stays current and the rejection cannot be rewritten; a later request is a separate history entry.

Optional live check (adds two new synthetic records without releasing existing ones):

```powershell
.\.venv\Scripts\python.exe scripts/smoke_releases.py
# Restart the server, then:
.\.venv\Scripts\python.exe scripts/smoke_releases.py --verify
```

## Verify Milestone 4 manually

1. Sign in as an institution and open an accepted current instrument. Choose **Create renewal draft**.
2. Enter successor reference/dates, confirm or change the prefilled bank/amount, upload its PDF, and save.
3. Confirm it is a separate draft linked to the original. The predecessor remains current and monitored.
4. Return to the predecessor: its successor link opens the same draft. Attempting a second proposal returns a conflict.
5. Submit the successor. As officer, request corrections, then as institution correct/resubmit. The predecessor must remain current throughout.
6. As officer, resolve any blocking observations and accept the successor with a reason.
7. Confirm the predecessor now shows **Superseded** with actor/reason/time in history, while both documents and the bidirectional lineage remain accessible.
8. Check the accepted-current dashboard/list/report: only the successor is counted. The old record remains in All visible records.
9. Confirm both records still say **Not independently bank-verified**.

Optional live check (adds two new synthetic instruments without renewing existing ones):

```powershell
.\.venv\Scripts\python.exe scripts/smoke_renewals.py
# Restart the server, then:
.\.venv\Scripts\python.exe scripts/smoke_renewals.py --verify
```

## Verify Milestone 3 manually

1. Sign in and choose **Dashboard**. Confirm the displayed business date and your authorized scope.
2. In local demo mode, set evaluation date to `2026-10-23`.
3. Use accepted synthetic instruments with maturity dates `2026-10-22`, `2026-10-23`, `2026-10-30`, `2026-11-07`, `2026-11-22`, and `2026-11-23`.
4. Confirm yesterday is matured, today is separate, 7/15/30 days are approaching, and 31 days is outside the default window.
5. Open each dashboard card. Its filtered list must contain exactly its count and retain the demo evaluation date.
6. Sign in as another institution: the first institution's records and counts must not appear. Officers can see accepted cases through explicit filters, while private drafts stay hidden.
7. Run the due-action report twice with the same date. Output must match, and no notifications or instrument changes should be created.

Optional live HTTP test, which creates the scenario through real forms/review actions:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_maturity.py
# Restart the server, then:
.\.venv\Scripts\python.exe scripts/smoke_maturity.py --verify
```

This creates nine new synthetic `MATURITY-...` records and preserves existing data. It checks dashboard/list counts, institution isolation, excluded pending/draft cases, command/dashboard agreement, and database hashes around repeated read-only report runs. The verify phase adds no new instruments.

## Verify Milestone 2 manually

Use separate browser sessions for the institution and officer.

1. Create an instrument with a unique reference, bank `Fictional Scrutiny Bank`, declared amount `500000.00`, valid issue/maturity dates, and `fixtures/scrutiny-fdr.pdf`.
2. Create a second draft in the same institution with the same bank/reference. Open the first record: its technical-check section shows `POSSIBLE_DUPLICATE`, the relevant declared values and a warning explanation.
3. Submit the first record. As officer, download its PDF: the synthetic document visibly states INR 600000.00.
4. Under **Manual document observations**, select that PDF, enter page `1`, select **Blocking**, and describe both amounts. Record the observation.
5. Attempt acceptance: the server blocks it and reports that blocking observations must be resolved.
6. Request corrections. As institution, confirm the comment/document/page are visible, correct the declared amount to `600000.00`, save, and resubmit.
7. As officer, confirm the original observation remains unresolved and still blocks acceptance. Corrections alone do not resolve it.
8. Enter a resolution explaining the manual recheck against page 1 and choose **Resolve observation**.
9. Accept with a reason. The detail page preserves the original observation, page, document, author/time, resolution and resolver/time, together with audit history.
10. Confirm **Not independently bank-verified** still appears. The duplicate warning is advisory and does not prevent the authorized acceptance.

Optional live HTTP acceptance test (server must be running):

```powershell
.\.venv\Scripts\python.exe scripts/smoke_scrutiny.py
# Stop and restart the server, then:
.\.venv\Scripts\python.exe scripts/smoke_scrutiny.py --verify
```

The script creates two synthetic `SCRUTINY-...` records: an accepted demonstration record and a duplicate draft. It does not reset existing data. Use `--base-url http://127.0.0.1:8001` if testing on a different local port. Like the original smoke script, it uses ignored generated demo credentials.

## Verify manually in two browser sessions

Use a normal browser window for `institution_a` and a private window for `officer`.

1. As `institution_a`, choose **New FDR**.
2. Enter reference `DEMO-FDR-001`, bank `Fictional Bank`, amount `500000.00`, issue `2026-01-01`, maturity `2027-01-01`.
3. Upload `fixtures/sample-fdr.pdf`. It is a synthetic demonstration PDF, not a financial instrument.
4. Save. Confirm **Draft** status, document download, and `DRAFT_CREATED` history.
5. Choose **Submit for review**. Confirm **Submitted** status; editing is unavailable.
6. As `officer`, refresh the queue. Open the record and download its PDF.
7. Choose **Request corrections**, enter a reason such as `Please correct the bank reference`, and record the decision.
8. As the institution, see the reason. Edit the reference, optionally upload another PDF, save, and resubmit.
9. Confirm the old PDF and earlier values remain in the history.
10. As officer, choose **Accept for tracking**, record a reason, and save.
11. As institution, confirm **Accepted for tracking** and the officer decision in history.
12. Sign in as `institution_b`: the first institution's record/detail/document URLs must return 404 and not appear in its register.
13. Try a draft without a PDF: saving succeeds but submitting is blocked. Try a negative amount, maturity before issue, or text renamed as PDF: validation must reject it.
14. Stop and restart the server. Sign back in and confirm the instrument, decision, PDF, and audit history remain available.

The officer list intentionally shows only pending submitted cases. After a decision, the existing detail URL remains accessible to the officer and the institution; accepted cases leave the pending queue.

## What each file does

| File | Responsibility |
|---|---|
| `manage.py` | Django CLI entry point |
| `requirements.in` / `requirements.txt` | Supported Django range / exact installed dependency versions |
| `.gitignore` | Excludes runtime database/files, secrets, caches, and environment |
| `.env.example` | Lists optional environment settings; it is documentation, not an auto-loaded file |
| `config/settings.py` | Application, SQLite, sessions, storage, upload limits, timezone, templates |
| `config/urls.py` | Login/logout and portal routes; no public media route or admin bypass |
| `config/asgi.py` / `config/wsgi.py` | Standard application entry points |
| `portal/apps.py` | Django app configuration |
| `portal/models.py` | Institution, membership, instrument, immutable document additions, manual observations and audit events |
| `portal/migrations/0001_initial.py` | Initial schema, positive amount and valid date constraints |
| `portal/migrations/0002_reviewobservation.py` | Additive observation table with page/resolution consistency constraints |
| `portal/migrations/0003_instrument_renewal.py` | Predecessor link, supersession timestamp and database constraints |
| `portal/migrations/0004_release_workflow.py` | Release requests, released timestamp, document kinds and state consistency constraints |
| `portal/validation.py` | Named technical checks, structured findings and versioned audit snapshots |
| `portal/deadlines.py` | Business date, maturity facts, reminder bands, scoped filters/counts and due-action selection |
| `portal/forms.py` | Permitted inputs, INR decimal-to-paise input, dates, PDF checks, scoped evidence and resolution forms |
| `portal/permissions.py` | Exclusive Institution/Officer roles and institution-scoped queries |
| `portal/services.py` | Draft/submission/review, atomic renewal cutover, blocking checks, observations, version checks, audit and file cleanup |
| `portal/releases.py` | Release request, Authority decision and evidence-backed completion transactions |
| `portal/uploads.py` | Shared bounded PDF validation for original FDRs and completion evidence |
| `portal/views.py` | HTTP forms/actions, protected downloads, scoped dashboard and filtered register |
| `portal/urls.py` | Named register/create/detail/edit/submit/review/download URLs |
| `portal/admin.py` | Explains why no editable admin surface is registered |
| `portal/management/commands/seed_demo.py` | Idempotent original account creation, plus opt-in authority-only setup |
| `portal/management/commands/due_actions.py` | Trusted-operator read-only maturity report; no delivery or persistence |
| `templates/base.html` | Shared navigation, local stylesheet, demonstration disclosure |
| `templates/registration/login.html` | Django authentication form |
| `templates/portal/instrument_list.html` | Institution register / officer pending queue |
| `templates/portal/dashboard.html` | Scoped dashboard cards linking to matching filters |
| `templates/portal/report_context.html` | Shared explicit evaluation-date and demo-policy labels |
| `templates/portal/report_error.html` | Safe errors for invalid report inputs |
| `templates/portal/release_queue.html` | Scoped request queue with status filters |
| `templates/portal/release_panel.html` | Request, Authority decision, evidence upload and preserved completion history |
| `templates/portal/instrument_form.html` | Create/edit/upload form |
| `templates/portal/instrument_detail.html` | Details, protected document links, review, audit snapshots |
| `templates/portal/conflict.html` | Locked-record response |
| `static/css/app.css` | Local responsive styling without CDN dependencies |
| `portal/tests/common.py` | Isolated users/institutions and temporary-storage test setup |
| `portal/tests/pdf_fixture.py` | Pure-Python synthetic PDF fixture generator |
| `portal/tests/test_submission.py` | Workflow, validation, concurrency, audit, auth and seed tests |
| `portal/tests/test_permissions.py` | Institution isolation and role enforcement tests |
| `portal/tests/test_documents.py` | Protected bytes/downloads, upload rejection and rollback tests |
| `portal/tests/test_validation.py` | Duplicate scope, check snapshots and verification disclaimer tests |
| `portal/tests/test_observations.py` | Evidence/page validation, correction/resolution, blocking, permissions, concurrency and audit rollback tests |
| `portal/tests/maturity_common.py` | Synthetic fixed-date reporting fixtures in the isolated test database |
| `portal/tests/test_deadlines.py` | Threshold/timezone boundaries, command scope, repeatability and read-only behavior |
| `portal/tests/test_dashboard.py` | Dashboard/list agreement, filters, permissions and unchanged landing behavior |
| `portal/tests/test_renewals.py` | Lineage, pending monitoring, atomic cutover, rollback, permissions, constraints and current-record counts |
| `portal/tests/test_releases.py` | Release states, roles, evidence, audit/file rollback, monitoring, conflicts and safe account upgrade |
| `fixtures/sample-fdr.pdf` | Synthetic PDF for manual submission |
| `fixtures/scrutiny-fdr.pdf` | Synthetic PDF stating INR 600000.00 for the manual mismatch scenario |
| `fixtures/release-evidence.pdf` | Synthetic completion PDF; not bank-issued evidence |
| `scripts/smoke_http.py` | Optional live HTTP correction/acceptance and restart persistence checks |
| `scripts/smoke_scrutiny.py` | Optional live HTTP scrutiny workflow and restart verification |
| `scripts/smoke_maturity.py` | Optional live maturity/dashboard/report scenario and restart verification |
| `scripts/smoke_renewals.py` | Optional live renewal/correction/acceptance scenario and restart verification |
| `scripts/smoke_releases.py` | Optional live request/approval/rejection/completion and restart verification |
| `docs/checks.md` | Exact technical checks, manual scrutiny workflow and acceptance checklist |
| `docs/maturity.md` | Maturity categories, demo thresholds, due-action CLI and limitations |
| `docs/renewals.md` | Linked successors, supersession, graph restrictions, audit and acceptance checks |
| `docs/releases.md` | Authority role, release states, evidence, conflict rules and acceptance checks |

`__init__.py` files mark Python packages. Generated `__pycache__` files and files under `data/` are runtime artifacts.

## Data and trust boundaries

- Amounts are stored as integer paise. Times are UTC internally and displayed in the configured business timezone (Asia/Kolkata by default).
- Declared details are entered manually. There is no automatic document comparison.
- Document observations and page numbers are entered manually; the PDF page count is not automatically checked.
- All unresolved blocking observations require explicit officer resolution before acceptance. Warnings remain advisory.
- Maturity/reporting views are read-only, preserve institution isolation and use no-store cache headers. Browser date overrides are restricted to local DEBUG mode and visibly labeled.
- Renewal drafts preserve predecessor monitoring until approval. Superseded records stay historical; no original documents or decisions are overwritten.
- Release authorization remains monitored until a separate, evidence-backed completion. Completed records remain historical, with protected FDR/evidence downloads and immutable application decisions.
- Original document filenames are metadata; storage uses generated UUID filenames.
- Downloads require an authorized session and return attachments with `nosniff` and no-store headers.
- PDF validation checks extension, declared MIME type, header/trailer, and size. It is **not** malware scanning, full parsing, page-limit enforcement, or authentication of a financial document. Use synthetic PDFs only.
- Submitted/accepted records are locked. Correction uploads append new documents. Audit snapshots retain declared fields, document IDs, state, version, actor, reason, and time.
- Audit events have no editing UI. A database administrator can still modify local data; this is not tamper-proof storage.
- Version checks prevent stale edits/decisions; this SQLite prototype is not a load-tested multi-user production system.
- Database transactions and audit writes commit together. Known failed upload transactions remove their files; a process crash during a file write could still leave an orphan file.

## Configuration and local backups

Default settings run locally. `.env.example` is not automatically read. Set environment variables explicitly in PowerShell if needed:

```powershell
$env:MAX_UPLOAD_MB = '10'
```

No production configuration is claimed. Before shared hosting, use a private secret key, `DJANGO_DEBUG=false`, explicit hosts, HTTPS/secure cookies, access review, deployment checks, file hardening, and operational controls.

For local backup, stop the server and copy `data/portal.sqlite3` together with `data/documents/`. Keep the backup and `data/demo-credentials.txt` private. Restart after copying. Do not commit these files.

## Optional Git initialization

The inspected directory was not a Git repository. No commits have been created automatically. After reviewing the files:

```powershell
git init
git add .gitignore .env.example requirements.in requirements.txt manage.py config portal templates static fixtures scripts docs README.md
git status --short
git commit -m "Implement FDR lifecycle through evidence-backed release completion"
```

Check that `data/` and `.venv/` are excluded before committing. Future milestones require a separate instruction.
