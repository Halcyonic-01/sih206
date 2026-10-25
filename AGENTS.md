# AGENTS.md: instructions for the AI coding agents of Yash and Saksham

This file is for the AI coding agent working for **Yash** or **Saksham** on **Pramaan — Trust Backed by Evidence**, the Security Deposit / FDR portal (SIH problem statement 26265, AICTE Regulation Bureau). Read all of it before your first change, and again at the start of every new session.

The third team member, **Kushagra**, owns the platform and DevOps work. Do not implement Kushagra's tasks unless your human explicitly tells you to.

---

## 1. Identify who you work for

Work out whether your human is **Yash (task IDs `Y1`–`Y8`)** or **Saksham (task IDs `S1`–`S7`)**: from the human's instruction, the git author (`git config user.name`), or the branch prefix (`y/…` or `s/…`).

If it is not clear, ask once: *"Am I working for Yash or Saksham?"* Then use only that person's tasks.

| Person | Letter | Responsibilities | Areas they own (backend + React) |
|---|---|---|---|
| Kushagra | K | DevOps, backend, frontend | Platform and API foundation, React shell, CI and run scripts, roles and access log, notifications and `run_due_rules`, audit screens, seed data and review build |
| Yash | Y | AI, backend, frontend | Records and documents, dashboard and search, verification and reconciliation, AI document extraction, shared `ai/` module |
| Saksham | S | AI, backend, frontend | Institution master, APH rules and obligations, release case, clearances, penalties and NOC, reports, KPIs and data import, AI release summary |

---

## 2. Read the plan first (local PDFs, not in Git)

The plan is in two PDFs that are **shared privately and are deliberately not committed**. The folder `planning/` is git-ignored. Each person keeps the PDFs locally at:

- `planning/team-task-allocation.pdf`: **who does what.** Find every task with your person's letter, with its priority, due time, deliverable, dependencies ("Needs") and what it unblocks.
- `planning/gap-analysis-and-implementation-plan.pdf`: **what each task must do and how.** Read these sections:
  - **Section 2**: the three stages, the Stage 1 priority list, sync points, Stage 2 rules, Stage 3 backlog.
  - **Section 3**: problem statement vs. current code (what exists).
  - **Section 4**: AICTE handbook (APH) rules: Table 1.4 amounts, 10-year term, penalties, release clause 6.46.
  - **Section 7**: feature designs F1–F15 (data model, endpoints, acceptance criteria).
  - **Section 8**: architecture (React + Django REST API) and the core data model.
  - **Section 9**: security rules.
  - **Section 12.1**: the 10 problem-statement scenarios that must pass.

If either PDF is missing, **stop and ask your human** to save it into `planning/` at the repository root. Do not guess the plan from memory.

If you cannot open PDFs directly, extract the text:

```bash
pdftotext -layout planning/team-task-allocation.pdf -
```

```bash
python -c "from pypdf import PdfReader; print('\n'.join(p.extract_text() for p in PdfReader('planning/team-task-allocation.pdf').pages))"
```

The task summaries in section 4 of this file are a convenience copy. **If they differ from the PDFs, the PDFs win.** Tell your human about the difference.

Also read these repository documents before touching an area:
- `README.md`
- `docs/architecture.md`
- `docs/handover/completed/code-map.md`
- the feature docs (`docs/checks.md`, `docs/maturity.md`, `docs/renewals.md`, `docs/releases.md`)
- the platform docs (`docs/api-conventions.md`, `frontend/README.md`, `docs/scheduled-rules.md`, `docs/review-build.md`)

---

## 3. Work out the current stage

Use today's date and time in **IST (Asia/Kolkata)**. If the review time on 25 Oct is unknown, ask your human for it.

| Stage | When | What you may do |
|---|---|---|
| **1 · Build** | Until the review on **Sun 25 Oct 2026** | Your P0 tasks first, in the order of section 4. Start P1 tasks only after **all** your P0 tasks are merged. Feature freeze **Sun 10:00** (if the review is earlier than 12:00, shift the freeze back by the same amount). |
| **2 · Stabilise** | After the review → final submission **Wed 28 Oct 2026** | **No new features.** Only bug fixes, tests, reliability, error and empty states, documentation and verification. The one exception is a feature the reviewers explicitly asked for, agreed by all three, at most 2 hours of work, behind a flag. |
| **3 · Extend** | Offline SIH round, **only after your human confirms the team was selected** | Remaining features and improvements from section 2.5 of the plan PDF and section 5 of the allocation PDF, tier A first. |

Problem-statement requirements always come before extras.

---

## 4. Task summaries (the PDFs are authoritative)

Times are Saturday 24 / Sunday 25 Oct 2026, IST. The team rests from 02:00 to 06:00. Merge windows: **Sat 10:30 · 14:00 · 18:00 · 23:30 · Sun 02:00 · 08:00 · 10:00**.

### Yash (Y)

| ID | Pri. | Task | Due | Needs |
|---|---|---|---|---|
| Y1 | P0 | `portal` migration 0005. `Instrument` gains `obligation` (nullable FK to Saksham's `DepositObligation`), `mode` (FDR/RTGS/RPGF), `ifsc`, `branch`, `holder_names`, `utr`, `lien_marked`, `verification_level`. Expand document types and add `page_count`. | Sat 10:30 | S1 |
| Y2 | P0 | PDF validation in `portal/uploads.py`. Parse with pikepdf under a timeout. Reject encrypted files and files with JavaScript or embedded files. Store the page count. An observation's page must be ≤ the page count. | Sat 11:30 | Y1 |
| Y3 | P0 | Instrument REST API.<br>• List with search (`q`), filters and pagination; create and edit (multipart); submit; review; observations; renew; officer correction (reason required); document upload and download.<br>• An `actions` object on every detail response. `notify()` calls on submit and review.<br>• API tests: allowed, denied and stale (409) for every endpoint. | Sat 14:00 | K1, Y1, `notify()` signature |
| Y4 | P0 | Records UI in React.<br>• List with search, filters and CSV export. Form with mode-specific fields and typed upload.<br>• Detail page with tabs: Details · Documents (inline viewer, `#page=N`) · Checks & observations · Lineage · History.<br>• Officer panels (review, observations, correction) and the renewal form. | Sat 21:00 | K2, Y3 |
| Y5 | P0 | Dashboard and search.<br>• PS categories: active, expiring, matured, renewed, released, pending.<br>• Intervention queue: overdue renewal, unresolved blocking observation, ageing corrections, shortfall, discrepancy.<br>• Maturity chart and the header search. | Sat 23:30 | Y3, S2 |
| Y6 | P0 | Verification backend (`verification/` app).<br>• `VerificationEvidence` is append-only. Officer acceptance sets "Reviewed".<br>• Statement CSV import auto-matches on UTR + amount: a match sets "Confirmed"; a mismatch sets "Discrepancy" and calls `notify()`.<br>• `ISSUER_UNKNOWN` check (IFSC prefix list). Officer-only cross-institution duplicate check. | Sun 01:30 | Y3, K5 |
| Y7 | P0 | Verification UI: verification tab (ladder and evidence) and reconciliation page (upload, matched and unmatched lists). | Sun 08:00 | Y6 |
| Y8 | P1 | AI document extraction.<br>• Shared `ai/` module: `AI_ENABLED` flag, `AiRun` log, Google Gemini model `gemini-3.5-flash-lite` (`AI_MODEL`).<br>• `POST /api/documents/{id}/ai-extract`: PDF in, schema-constrained fields out.<br>• "Use extracted values" pre-fill on the form. Advisory `AI_MISMATCH` findings for officers. | Sun 10:00 | Y3, Y4 |

**Stage 2 (Yash):**
- Sun 25: fix P0 bugs in your areas.
- Mon 26: cross-test **Saksham's** areas.
- Tue 27: API tests for the records and verification endpoints. Playwright specs for PS scenarios 1, 2, 5 and 6. AI off and timeout fallback for extraction.
- Wed 28: README and setup notes, final pass on your scenarios.

**Stage 3 (Yash), tier A first:**
- **A:** AI officer copilot (read-only, user-scoped tools, every tool call audited). Bank-branch confirmation portal (signed link + OTP).
- **B:** Scanned-document extraction with an evaluation set. Bank statement feed (SFTP, MT940 / CAMT.053). DigiLocker / Entity Locker. Structured observations.
- **C:** Fuzzy duplicates. Manual reconciliation matching UI.

### Saksham (S)

| ID | Pri. | Task | Due | Needs |
|---|---|---|---|---|
| S1 | P0 | `obligations/` app models: `InstitutionProfile` (AICTE ID, trust, type, region, state, contact email), `ProgrammeApproval`, `RuleSet`, `DepositObligation`. Merge the model file early: Yash's migration depends on it. | Sat 10:00 | — |
| S2 | P0 | Rules and obligation API.<br>• Seed `RuleSet` with: Table 1.4 amounts (×2 when the land or building is leased), late-proof penalty 10%/20%, premature encashment 10%, closure penalties 10%/50%, release checklist per path, escalation matrix and reminder days.<br>• `required_amount()` and `coverage()` with parametrised tests.<br>• Checks v3: `AMOUNT_SHORTFALL`, `TERM_GAP`, `PROOF_OVERDUE`. Institution and obligation endpoints, `/api/calculator`. | Sat 14:00 | K1, S1 |
| S3 | P0 | Institution UI.<br>• Institutions list.<br>• Institution page: profile, programmes, obligation card (required / held / shortfall), coverage timeline against the 10-year term, open actions.<br>• Requirement calculator. | Sat 18:00 | K2, S2 |
| S4 | P0 | Reports, KPIs and import.<br>• XLSX reports: pending verifications, upcoming maturities, missing documents, intervention, released register.<br>• `/api/kpis` and a KPI page.<br>• AICTE institutions CSV import (labelled SIMULATED) with preview, then commit. | Sat 21:30 | Y3, S2 |
| S5 | P0 | Release case backend.<br>• `portal` migration 0006 (`path`, `declarations` on `ReleaseRequest`): create it **only after pulling `main` at the 23:30 sync, and announce it first**.<br>• `casework/` app: `ClearanceTask` (PGRC, Vigilance, Grants), `PenaltyAssessment` (proposed → confirmed or waived), `IssuedLetter`.<br>• Decision gates in `portal/releases.py`. NOC or sanction-order PDF (reportlab + QR). Public `/api/public/verify/{token}`. `notify()` calls. | Sun 02:00 | K4, K5, Y2 |
| S6 | P0 | Release UI.<br>• Wizard: path → declarations → documents → review.<br>• Release case page: clearances, penalties, decision, letter, completion.<br>• Clearance-unit queue and the public `/verify/:token` page. | Sun 09:00 | S5, K2 |
| S7 | P1 | AI release summary. `POST /api/releases/{id}/ai-summary`: structured case JSON in (no PDFs); a short summary and at most five risk flags out. Labelled AI-generated, cached per version. Reuses Yash's `ai/` module. | Sun 10:00 | S5, Y8 |

**Stage 2 (Saksham):**
- Sun 25: fix P0 bugs in your areas.
- Mon 26: cross-test **Kushagra's** areas (roles, notifications, audit).
- Tue 27: API tests for the obligation, release and report endpoints. Playwright specs for PS scenarios 3, 7 and 9. AI fallback for the summary.
- Wed 28: demo video (5–7 min), final pass on your scenarios.

**Stage 3 (Saksham), tier A first:**
- **A:** Forfeiture and term-extension actions. Digitally signed NOC (pyHanko + DSC). AI compliance pre-check of release documents.
- **B:** AICTE portal API integration. eSign for affidavits. Hindi interface and GIGW / WCAG audit. Legacy bulk import.
- **C:** ICS calendar feed. Data-quality score. KPI baseline study.

### Kushagra's tasks you depend on (do not implement them)

| ID | What it provides | Due |
|---|---|---|
| K1 | DRF setup, auth endpoints (`/api/auth/csrf · login · logout · me`), exception handler (`WorkflowError` → 409, `PermissionDenied` → 403), `/api/docs/`, old UI under `/legacy/` | Sat 10:30 |
| K2 | React shell in `frontend/`: Vite, TypeScript, Ant Design, router, `api/client.ts`, `AuthProvider`, `RequireRole`, AppShell | Sat 12:30 |
| K3 | CI (GitHub Actions) and run scripts | Sat 14:00 |
| K4 | Clearance and Auditor roles, scoped helpers, `AccessLog` | Sat 17:00 |
| K5 | `notify(recipients, template, context, key)`: signature published 14:00, full feature 21:00 | Sat 21:00 |
| K6 | `run_due_rules` scheduler command (uses Saksham's `RuleSet` and obligations) | Sun 01:30 |

**Platform contracts that already exist (read [docs/api-conventions.md](docs/api-conventions.md) and [frontend/README.md](frontend/README.md) before writing endpoints or screens):**
- **Routes without editing shared files:** backend endpoints go in `portal/api/instrument_urls.py` (Y3), `portal/api/dashboard_urls.py` (Y5), `verification/api_urls.py` (Y6), `obligations/api_urls.py` (S2, S4), `casework/api_urls.py` (S5), `ai/api_urls.py` (Y8, S7): each exposes `urlpatterns` relative to `/api/` and is picked up automatically. React screens go in `frontend/src/features/<area>/routes.tsx` (plus optional `HeaderSearch.tsx`).
- **Errors:** raise `WorkflowError` (409), `PermissionDenied` (403) or `ObjectDoesNotExist` (404) from services; the API returns `{detail, code, errors?}`. Lists use `portal.api.pagination.StandardPagination`.
- **Roles and scope:** use the helpers in `portal/permissions.py` (`scoped_instruments`, `scoped_documents`, `scoped_release_requests`, `clearance_unit`, `require_*`). The clearance unit lives in `access.UnitAssignment` (not `UserProfile`), so there is no extra `portal` migration.
- **Access log:** every document download, export, report, NOC view and staff search must call `access.logging.log_access(...)` before responding.
- **Notifications:** `notifications.service.notify(recipients, template, context, key)` with recipient helpers in `notifications/recipients.py`; templates are in `notifications/catalog.py`.
- **Scheduler:** `run_due_rules` reads thresholds from a `RuleSet` with code `escalation-matrix` (shape in [docs/scheduled-rules.md](docs/scheduled-rules.md)); its clearance SLA adapter is marked `TODO(S5)`.
- **Seed data for the review build:** ship idempotent management commands named `seed_review_<area>`; `seed_review` runs them (see [docs/review-build.md](docs/review-build.md)).
- **Run everything:** `./run.sh` (macOS/Linux) or `.\run.ps1` (Windows); the old UI is at `/legacy/`. Audit events must go through `portal.services.event()` (sealed in the audit hash chain); never `bulk_create` them.

If a dependency is not on `main` yet:
1. Build the parts that don't need it (models, services, pure functions, tests).
2. Code against the agreed contract (signature, endpoint or role name) with a clear `# TODO(<dependency-id>)` marker.
3. Tell your human.

Never write a competing implementation of someone else's task.

---

## 5. Inspect before you change anything

Do this at the start of every task:

1. `git status`, then `git pull --ff-only` on `main`, then create your branch: `y/<task-id>-<slug>` or `s/<task-id>-<slug>` (for example `y/Y3-instrument-api`).
2. Check what already exists, so that you neither duplicate nor break it:
   - Backend workflow: `portal/services.py`, `portal/releases.py`, `portal/permissions.py`, `portal/validation.py`, `portal/deadlines.py`, `portal/exports.py`, `portal/uploads.py`, `portal/models.py`, plus any new apps (`obligations/`, `verification/`, `casework/`, `notifications/`, `ai/`, `portal/api/`).
   - Frontend: `frontend/src/` (api client, auth, layout, pages, components).
   - Search before adding: `grep -rn "<function or field name>" portal/ frontend/src/`.
3. Check the migration state: `python manage.py showmigrations` and `python manage.py makemigrations --check --dry-run`.
4. Run the baseline tests (section 7) and note any failures **before** your change, so you never report someone else's failure as your own.
5. Read the matching feature design (F#) in plan section 7 and the acceptance criteria for your task.

---

## 6. Implementation rules

### Architecture contract (shared by all three)
- **Backend:** Django 5.2 LTS with Django REST Framework under `/api/`.
  - **Views validate input, then call service functions.** No business logic in views or serializers. Reuse the existing services (`save_draft`, `submit`, `review`, `add_observation`, `resolve_observation`, `request_release`, `decide_release`, `complete_release`) instead of re-implementing them.
  - **Scope first:** every queryset starts from `scoped_instruments(user)` or the scoped helper for your entity. Never trust an institution ID or owner from the request body.
  - **Optimistic locking:** every write takes `version`. A stale version must return **409** via `WorkflowError`.
  - **Server-computed permissions:** detail responses include an `actions` object (`can_edit`, `can_submit`, `can_review`, …) so React shows only allowed buttons. The server still enforces every rule.
  - **Audit:** every state change writes an `AuditEvent` through `services.event()`.
  - **Data conventions:** money in integer **paise**; dates in the business timezone (`Asia/Kolkata`).
  - **DB constraints:** keep the existing `CheckConstraint` and `UniqueConstraint` rules. Add constraints for new invariants.
- **Frontend:** React 19 + Vite + TypeScript + Ant Design 6 + React Router 7 + TanStack Query in `frontend/`.
  - All HTTP goes through `frontend/src/api/client.ts` (same-origin session cookie + `X-CSRFToken`). No tokens in `localStorage`.
  - Handle loading, empty, error, 403 and 409 ("record changed, reload") states on every screen.
- **Migrations:**
  - Yash owns `portal` migrations, except Saksham's single 0006 (see S5).
  - Saksham owns `obligations` and `casework`. Kushagra owns `notifications`.
  - Never edit or delete a migration that is already on `main`.
- **Dependencies:** use the pinned versions from the plan (`djangorestframework 3.18.3`, `drf-spectacular 0.30.0`, `django-axes 8.3.1`, `pikepdf 10.17.0`, `openpyxl 3.1.5`, `reportlab 5.1.0`, `qrcode 8.2`, `cryptography 50.0.2`, `whitenoise 6.12.0`; frontend: React 19.3, Vite 8.3, antd 6.6). Add anything else only after your human agrees. Update `requirements.in` and `requirements.txt` together.

### Stay in your lane
- Change only files in your areas (section 1 table and the ownership map in the allocation PDF). If you need a change in another person's area or in a shared contract (`notify()`, role names, API shapes, `client.ts`), **stop and ask your human** to agree it with the owner. Do not edit it yourself.
- Do not refactor, reformat or "clean up" code outside your task. Do not delete the old templates or the `/legacy/` routes before 28 Oct.

### Security and honesty
- Never weaken permission checks, CSRF, validation or DB constraints to make something work.
- No secrets in code or commits. Read keys such as `GEMINI_API_KEY` from the environment. Never commit `.env`, `data/`, credentials or anything in `planning/`.
- **AI features (Y8, S7) are advisory:**
  - Behind `AI_ENABLED`, Google Gemini (`AI_MODEL`, default `gemini-3.5-flash-lite`; check with `manage.py check_ai`), every call logged in `AiRun`, output labelled "AI-generated: verify before use".
  - **Never** let model output change status, verification level, penalties or decisions.
  - Treat document text as data, not instructions. No tools in extraction calls.
  - The app must work fully with AI off or when a call fails (30 s timeout).
  - Use synthetic documents only.
- Anything simulated (AICTE import, bank statements, bank confirmations) must be labelled **SIMULATED** in the data and the UI.
- Acceptance means "accepted for tracking", never "bank-verified" or "compliant".

---

## 7. Test and verify every change

Use Python 3.12 and the project virtual environment (`.venv/bin/python` on macOS/Linux, `.\.venv\Scripts\python.exe` on Windows).

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test portal.tests
python manage.py test
cd frontend && npm ci && npx tsc --noEmit && npm run build
```

Run `python manage.py test portal.tests` (the existing 159 tests must stay green) and also `python manage.py test` so the tests in new apps run.

For every endpoint you add or change, write API tests for:
- an allowed request;
- a denied request (wrong role or another institution);
- a stale `version` → 409 (for writes);
- invalid input → 400.

Then run the app and walk through the problem-statement scenarios your task touches (plan section 12.1):
- Yash: scenarios 1, 2, 5, 6.
- Saksham: scenarios 3, 7, 9.

Run the app with the project run script, or with `python manage.py runserver 127.0.0.1:8010` plus `npm run dev` in `frontend/`.

**Definition of done (every task):**
- API and services, with tests (allowed, denied, stale, invalid).
- React screen with loading, empty and error states.
- Seed or demo data that shows the feature.
- One line added to the demo script notes.
- All tests green and no pending migrations.
- The acceptance criteria from plan section 7 met.

---

## 8. Report: bugs, incomplete work, blockers

1. **Pull request description**, for every PR:
   ```
   Task IDs: Y3 (or S2, …)            Stage: 1 / 2 / 3
   What changed: <files and behaviour>
   API changes: <new or changed endpoints, request and response shape>
   Migrations: <app and number, or none>
   Tests run: <commands and pass/fail counts>
   PS scenarios checked: <numbers and result>
   Known issues / incomplete: <list, or none>
   Blockers / waiting on: <task IDs, for example K5>
   ```
2. **GitHub issues** for every bug you find (including in others' areas: report it, don't fix it). Labels: `P0` (crash, data loss, permission leak, broken PS flow), `P1` (wrong behaviour), `P2` (cosmetic), plus the owner (`yash`, `saksham`, `kushagra`).
3. **Session notes (local only):** keep `planning/agent-notes-<yash|saksham>.md`, which is git-ignored, with what you finished, what is next, open questions and blockers. Read it at the start of each session to continue.
4. Tell your human immediately if a **P0 task will be more than an hour late**. The plan then drops your P1 work and others may help.

---

## 9. Coordinate to avoid conflicts

- Merge only in the merge windows (section 4). Keep pull requests small and focused on one task ID. Pull `main` after every window and rebase your branch: `git pull --rebase origin main`.
- Reviewers: Kushagra reviews Yash's records and dashboard work. Saksham reviews Yash's verification work. Yash reviews Saksham's obligations, reports and import work. Kushagra reviews Saksham's release work. The other AI developer reviews the shared AI work.
- **Kushagra merges to `main` only when CI is green.** Never push directly to `main`. Never force-push shared branches. Never rewrite other people's commits.
- **Before creating a migration,** pull `main`. If someone else added one in the same app, rebase and regenerate yours; don't hand-merge numbering.
- **Contract changes:** if your API shape changes after another person started using it, keep it backward compatible or agree the change first. The OpenAPI schema at `/api/docs/` is the shared contract.
- **Shared frontend files** (`frontend/src/api/client.ts`, `layout/`, `auth/`, theme) belong to Kushagra. Add your routes and menu entries only through the agreed registration point; ask if there isn't one.
- **Hand-offs to honour** (do these on time, because others are blocked on them):
  - S1 → Y1 at Sat 10:00.
  - Y1 → everyone at Sat 10:30.
  - Y3 → S4, S5 and K8 at Sat 14:00.
  - S2 → Y5 and K6 at Sat 14:00.
  - Seed data for your scenarios → Kushagra by Sun 08:00.

---

## 10. Stop and ask your human when

- A planning PDF is missing, or the task is unclear or contradicts the code.
- You need to change another person's area, a shared contract, or a migration already on `main`.
- Tests fail in code you did not touch, or the baseline is already red.
- An action is destructive or hard to reverse: deleting data or files, `git reset --hard`, force-push, dropping or rewriting migrations, changing `.gitignore`.
- Real (non-synthetic) data, real credentials, or sending documents to an external service is involved.
- You are about to start a P1 task while any of your P0 tasks is unmerged, or a new feature during Stage 2.

---

## 11. Never

- Commit or push anything in `planning/` (the PDFs, notes or other local planning files), `.env`, `data/`, credentials or generated builds.
- Disable, skip or delete existing tests to get a green run.
- Implement Kushagra's tasks or the other AI developer's tasks without being asked.
- Present AI output, simulated data or "accepted for tracking" as bank-verified or legally compliant.
- Start Stage 3 work before your human confirms selection for the offline round.
