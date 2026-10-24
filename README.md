# AICTE Security Deposit / FDR Portal

A localhost, synthetic-data MVP for **institution submission → protected PDFs → manual scrutiny/corrections → officer acceptance → maturity monitoring → linked renewal or authority-controlled release**.

**New teammate: start here.** GitHub is the source of truth. Clone the repository to get editable source, tests, documentation, synthetic PDFs and evaluation data; install the pinned Python dependencies locally. You do not need the previous developer's database, passwords, virtual environment or conversation history.

## 1. Current status and boundaries

All six approved implementation milestones are present. The release audit recorded **159 passing tests**, real HTTP workflow checks, measured rule evaluation and a recovery drill. These are dated results, not a guarantee for every future edit or machine.

This is a **synthetic localhost demonstration candidate**. Public/real-data deployment is blocked. Target-browser visual/PDF and physically disconnected rehearsal still require manual sign-off. Read the [release-readiness report](docs/release-readiness.md).

This is an FDR lifecycle portal, not a general AICTE application-validation engine. There is **no OCR, AI model, automatic PDF extraction, bank connection, regulatory policy engine, notification delivery or payment execution**. Officers manually inspect documents. Acceptance means **accepted for tracking**, not bank-authenticated or legally compliant.

S1 adds the [institution and obligation model foundation](obligations/README.md): four new tables, validation and migration tests. Existing records receive no inferred requirements or exemptions. Run `manage.py test` to include the new app's tests alongside the original portal suite.

The [independent S2 backend portion](obligations/S2.md) now provides draft demo rule configuration, read-only amount/coverage calculations, evidence-linked obligation findings and penalty proposals. It is not connected to the current browser workflow. APIs and instrument adapters await teammate dependencies; policy publication and S3 screens are not implemented. Existing `technical-v2` checks and decisions are unchanged.

The newer local [S1–S6 owned implementation](docs/owned/README.md) adds tested services,
an opt-in DRF API harness, transactional imports, reports/KPIs, guarded release
casework and isolated React components. These are built against provisional ports;
they are not mounted in the default app or integrated with the teammates' stack.
Read its contract and verification records before using it. Install
`requirements-saksham.txt` to run the **full current test suite**; the original
`requirements.txt` still supports the preserved legacy runtime. No S7 work is added.

## 2. Read these documents in order

| Your question | Document |
|---|---|
| What should I receive? Where do I start? | [Handover index](docs/handover/README.md) and [transfer checklist](docs/handover/transfer-checklist.md) |
| What was required and why did we narrow it? | [Requirements and scope](docs/handover/completed/requirements-and-scope.md) |
| How and why did we build each milestone? | [Step-by-step build history](docs/handover/completed/build-history.md) |
| What does each file do? How do I edit safely? | [Code map and developer workflow](docs/handover/completed/code-map.md) |
| What has actually been completed? | [Completed-work folder](docs/handover/completed/README.md) |
| How do I test everything from zero? | [Beginner testing walkthrough](docs/handover/testing/README.md) and [test-record template](docs/handover/testing/test-record-template.md) |
| What should I do next? | [Sequenced next steps](docs/handover/next-steps.md) |
| What could strengthen the hackathon entry? | [Prioritized improvement backlog](docs/handover/improvements.md) |
| How do I present it? | [Five-minute demo and fallback](docs/demo-script.md) |
| How does the system fit together? | [Implemented architecture](docs/architecture.md) |

Roadmap/backlog items are **proposals**, not existing features. Start with baseline verification and manual sign-off.

## 3. Technology

| Part | Implemented choice |
|---|---|
| Language | Python 3.12; tested development runtime 3.12.14 |
| Backend, forms, auth, ORM | Django 5.2.18 |
| Frontend | Django templates, HTML and local CSS; no separate React/Node build |
| Database | Local SQLite |
| Documents | Private local files, generated storage names, size and SHA-256 metadata |
| Checks | Two deterministic metadata rules and manually entered observations |
| Application dependencies | asgiref 3.12.1, Django 5.2.18, sqlparse 0.6.0, tzdata 2026.5 |
| Optional offline tooling | Existing wheel/package scripts remain available; ordinary GitHub setup uses requirements.txt |

No Node, API key, cloud account, external database service or Docker installation is needed. A read-only replay created for an earlier demonstration is not an application dependency and is not included in the clean handover.

## 4. Recommended Windows setup: clone from GitHub

### A. Clone and open the correct folder

Install/locate Git and Python 3.12. The project repository is [Saksham-189/sih206](https://github.com/Saksham-189/sih206).

Open PowerShell in the parent folder where you want the project, then run:

```powershell
git --version
py -3.12 --version
git clone -- https://github.com/Saksham-189/sih206.git fdr-portal
Set-Location -LiteralPath .\fdr-portal
Test-Path -LiteralPath .\manage.py
git rev-parse HEAD
```

Expected: Git/Python versions, a successful clone, True for manage.py, and the checked-out commit ID. If fdr-portal already exists, choose a different new destination; do not overwrite/delete existing work. For a private repository the owner must grant your GitHub account access. Authenticate through your normal Git credential manager; never put tokens in documentation or committed files.

### B. Create your environment and synthetic data

Internet access is needed for GitHub and the first dependency download. These commands assume a fresh clone with no existing .venv:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo --generate-password
.\.venv\Scripts\python.exe manage.py seed_demo --authority-only --generate-password
.\.venv\Scripts\python.exe manage.py seed_scenarios
```

Expected: pinned dependencies installed, migrations applied, four accounts created with private local passwords, and **17 synthetic instruments / 18 PDFs**. No API key or previous developer's data is needed. Do not run Setup-Offline.ps1 in a normal clone: it expects a separately generated package manifest/wheelhouse, which are not committed.

If py does not locate Python 3.12, replace it with the actual installed Python 3.12 executable, for example `& 'C:\path\to\Python312\python.exe' -m venv .venv`. Do not copy a former developer's runtime path or .venv.

### C. Verify

```powershell
.\Verify-Demo.ps1
```

Expected baseline: 159 tests pass; system/migration checks pass; synthetic evaluation passes; due-action report prints. If PowerShell blocks .ps1 execution, use the individual Python commands in section 7 without weakening global policy.

### D. Run

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8010 --noreload
```

Alternatively use .\Start-Demo.ps1 -Port 8010. Leave the terminal open. Visit **http://127.0.0.1:8010/**. Stop with Ctrl+C. Restart after Python edits when using --noreload; browser refresh alone does not reload Python modules.

8010 is the example port throughout this handover. If occupied, select a free port and update all URLs. Earlier ports 8000/8005/8006 were processes on the outgoing developer's computer, not hosted services.

## 5. Accounts and first visit

Passwords are generated on **your machine**. Open these files privately; never commit, screenshot or redistribute them:

- data/demo-credentials.txt: institution_a, institution_b, officer.
- data/authority-credentials.txt: authority.

| Account | Purpose |
|---|---|
| institution_a | A's submissions, corrections, renewal proposals and release requests |
| institution_b | B's isolated records; access-control test account |
| officer | Review, document observations, resolution and acceptance |
| authority | Independent release decision and evidence-backed completion |

Sign out before changing roles. Tabs in one browser profile share login; use separate profiles for simultaneous roles. There is no public registration/admin UI. Seed commands create demo accounts.

As institution_a: Dashboard → Optional demo evaluation date **2026-10-23** → View report. Before changing sample records, expect A counts: all 16, pending 1, accepted current 11, approaching 7, today 1, matured 1. The last three are subsets of accepted current; do not add all cards together. Detail pages use the actual business date.

## 6. Everyday GitHub collaboration

Before editing, check your branch and working tree. Coordinate with the team on the real branch/review policy; no remote or branch name is invented here.

```powershell
git status
git branch --show-current
git pull --ff-only
```

Commit or safely set aside local work before pulling; do not force-reset to make a pull succeed. Work on an agreed branch, run affected tests and the full gate, then share a reviewed commit/pull request. If requirements change, reinstall them deliberately in your local environment. If new migrations arrive, back up needed local data and run manage.py migrate before using the updated code.

The original three demo accounts initially share a generated demo password; this is not public-use account governance. Seeds preserve accounts/decisions and do not reset a rehearsal.

macOS/Linux equivalents use python3.12 -m venv .venv and .venv/bin/python. PowerShell wrappers are Windows conveniences; target-specific non-Windows behavior has not been manually verified.

## 7. Individual checks

These do not require a running browser server:

```powershell
.\.venv\Scripts\python.exe manage.py check --database default
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate --check
.\.venv\Scripts\python.exe manage.py test portal.tests --verbosity 1
.\.venv\Scripts\python.exe scripts\evaluate_release.py --output data\release-evaluation.json
.\.venv\Scripts\python.exe manage.py due_actions --as-of 2026-10-23
```

Tests use separate databases/temporary files; evaluation uses in-memory SQLite. They do not reset demo data. The due-action CLI is for a trusted operator and defaults to all institutions. It sends no notifications.

With server 8010 running, on a **fresh untouched seeded demo**:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_exports.py --base http://127.0.0.1:8010 --scenarios
```

Expected: PASS, 24 role/category comparisons, 18 distinct PDF downloads. After creating/changing records, omit --scenarios; it intentionally asserts the initial state. See the testing walkthrough for HTTP scripts that add records and later --verify checks.

## 8. Repository guide

```text
config/                 Django settings and root routes
obligations/            S1 institution profiles, approvals, rule records and obligations
portal/
  models.py             institutions, instruments, documents, observations, releases, audit
  forms.py              field/upload validation
  permissions.py        role and institution scope
  services.py           submission/scrutiny/review/renewal transactions
  releases.py           release request/decision/completion transactions
  validation.py         technical-v2 metadata findings
  deadlines.py          shared maturity calculations
  exports.py            CSV formatting and formula-text protection
  middleware.py         operational-error handling and no-store headers
  views.py, urls.py      HTTP form endpoints and page contexts
  management/commands/  seed commands and due-action report
  migrations/           four ordered schema migrations
  tests/                automated tests and complete-lineage journey
templates/              actual Django frontend
static/css/app.css      local styling
fixtures/               three generated synthetic PDFs
evaluation/             frozen labels, measured results and audit evidence
scripts/                packaging/setup, live HTTP checks, evaluation
docs/handover/          teammate onboarding, history, roadmap and testing
data/                   ignored local database, files, credentials and results
dist/                   ignored generated packages/isolated copies
```

## 9. Start development safely

1. Finish baseline setup/tests before editing.
2. Read the code map and choose one approved task from next-steps.md.
3. Back up needed local data and retain a separate fresh clone for demonstrations.
4. Edit one authoritative source folder; do not unknowingly edit an obsolete dist copy. Use the team's actual GitHub repository, branch and reviewed commits.
5. Run affected tests after small changes and the complete gate before handover.
6. Preserve transactions, role scope, version conflicts, evidence history and human approval.

Ordinary GitHub development uses the source commands above, not the optional offline installer. Review git diff before committing and never force-add ignored runtime files. If you later use an offline bundle, its original manifest becomes stale after edits; that separate integrity check is intentional.

## 10. Configuration and recovery

Settings read operating-system environment variables. .env.example is a reference, not an automatically loaded file. Variables: DJANGO_DEBUG, DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, DJANGO_SECURE_COOKIES, MAX_UPLOAD_MB, BUSINESS_TIMEZONE, REMINDER_DAYS. See the code map for defaults and boundaries.

Database: data/portal.sqlite3. Documents: data/documents. Stop the server and back them up **together**. Restore into a new folder, never over the only working copy. Credentials/backups remain private. The testing walkthrough provides safe commands.

Reset a rehearsal by using a **new clone**, not deleting a database. Seeding is intentionally idempotent and does not reset decisions.

## 11. Share through GitHub

Follow the [GitHub upload and handover checklist](docs/handover/transfer-checklist.md). Share the actual repository URL and grant your teammate access if private.

Commit source, migrations, templates, CSS, synthetic fixtures, evaluation, requirements and documentation. The .gitignore excludes local data/uploads/passwords/backups, .venv, .env variants, wheel/cache directories, logs and generated archives. .env.example and synthetic fixtures remain versioned.

**Do not drag the entire working directory into GitHub's browser upload.** Browser uploads do not apply .gitignore. Use reviewed Git staging, or explicitly select only the source/documentation paths listed in the checklist. The source handover repository is [Saksham-189/sih206](https://github.com/Saksham-189/sih206); uploading source does not deploy the application.

The existing offline build/setup scripts remain optional tools for disconnected rehearsals. They are not needed for GitHub handover. The testing guide explains preparing local dependency wheels from a clone before going offline; generated wheels/data stay ignored.

## 12. Troubleshooting

| Symptom | Action |
|---|---|
| manage.py missing | Open the cloned project folder and reopen PowerShell there. |
| py has no Python 3.12 | Install/locate 3.12; do not substitute an unrelated default 3.10 runtime. |
| .ps1 blocked | Use equivalent Python commands, without weakening global policy. |
| Port occupied | Stop your old server or choose another port consistently. |
| Checksum mismatch after editing | Use the installed environment; review and rebuild a new package. |
| Credentials/scenario collision | Preserve existing data; use a fresh clone for a clean demonstration. |
| --scenarios fails after mutations | It expects initial state; use a fresh clone/setup or omit that flag. |
| --verify JSON missing | Run that script's creation check first in the same folder. |
| 409 conflict | Reload and inspect version/workflow constraints before retrying. |
| 503 unavailable | Operation could not be confirmed; reload and inspect status before retrying. |
| 400/403 test diagnostics | Some tests deliberately exercise denied requests. Read final OK/FAILED. |
| Deployment warnings | These are public-deployment blockers; read the release report. |

The previous milestone diary is preserved verbatim as [README-before-handover.txt](docs/handover/completed/README-before-handover.txt). Its old machine-specific commands/historical counts are context, not the current onboarding path.
