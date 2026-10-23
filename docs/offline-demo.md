# Milestone 6: final local demonstration

Scope: one CSV export of the current authorized register view, an offline source/dependency package, synthetic scenarios and verification. No schema change or additional workflow. Milestones 1–5 retain their acceptance tests.

## Run the existing application

From the project folder in PowerShell:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\Start-Demo.ps1
```

Open http://127.0.0.1:8000/. Credentials remain in the ignored `data/demo-credentials.txt` and `data/authority-credentials.txt`. Never commit or distribute these files. Select register filters, Apply filters, then **Export this view as CSV**. The link preserves category and the optional demo evaluation date. Default Officer export is pending submissions; Institution export is its own records; Authority and Officer cannot export private drafts. Forged institution parameters cannot expand scope. Invalid filters return HTTP 400. Exports do not change records or history.

CSV uses UTF-8 with a BOM, standard comma/quote/newline escaping, exact two-decimal INR amounts, review/lifecycle states and the evaluation date. Entered text that could be interpreted as a spreadsheet formula is prefixed with an apostrophe. A leading negative **numeric** days-remaining value is intentionally a number. The export explicitly says bank verification has not occurred. It contains no PDFs, credentials, storage paths or audit snapshots. CSV text protection is for direct spreadsheet import; do not strip its protective apostrophes before opening.

## Build the distributable (Internet required once)

Python **3.12** is a prerequisite on both build and demo machines. The archive does not include a Python interpreter. Use a Python 3.12 executable with pip for the download. On this machine, the registered `py` launcher has no installed runtimes; the available base executable is:

```powershell
$python312 = 'C:\Users\sriva\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python312 -m pip download --only-binary=:all: --dest .offline-wheels -r requirements.txt pip==26.2.1
.\.venv\Scripts\python.exe scripts\build_offline_demo.py
```

On another machine with a registered Python 3.12, replace the first command with `py -3.12 -m pip download ...`. The builder requires exactly the pinned application wheels plus pip 26.2.1; stale/extra wheel versions fail validation. It creates a **new** `dist/fdr-demo-<UTC>/` directory, ZIP and ZIP SHA-256 file; it never replaces a prior build.

The package contains source, migrations, tests, local CSS, synthetic fixture PDFs, scripts, docs and five wheels. It excludes the live `data/`, credentials, database, uploads, `.env`, `.venv` and Git state. SHA-256 detects accidental corruption; it does not authenticate a package from an untrusted sender. Dependency licenses are retained inside their wheel files.

## Install and run offline

Extract the ZIP to a new writable local folder. Do not run setup inside the ZIP viewer. In PowerShell in that extracted folder:

```powershell
# When Python 3.12 is registered:
.\Setup-Offline.ps1
# Alternatively specify its executable, e.g. on this development machine:
.\Setup-Offline.ps1 -Python 'C:\Users\sriva\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
.\Verify-Demo.ps1
.\Start-Demo.ps1
```

Setup checks packaged file hashes, creates a venv without downloading pip, installs only bundled wheels using `--no-index`, migrates SQLite, generates random local passwords, creates the four accounts and seeds scenarios. It never resets existing accounts, passwords or decisions. A second setup verifies the same files and leaves the data unchanged. Missing/corrupt files or a conflicting scenario namespace fail rather than overwriting work. Use a fresh extraction to reset a demonstration. The package is intended for localhost synthetic data with DEBUG enabled; it is not a deployment package.

All stylesheet assets are local. Application operation uses no bank service, cloud API, email service, OCR, JavaScript CDN or remote font. Offline installation was verified with pip's index disabled; physical network disconnection must be checked on the target demo machine if required. Python must already be installed there.

## Synthetic walkthrough

Only run `seed_scenarios` in a synthetic demo database after both `seed_demo` commands. Do not run it against real institutional data. The packaged setup does this in its own new database. Manifest: `data/scenarios-v1.json`; fixed evaluation date **2026-10-23**. Dates affect maturity calculations only; they do not rewind workflow decisions.

| Manifest key | What to demonstrate |
|---|---|
| valid | Submitted FDR ready for manual officer review |
| discrepancy | Correction requested; unresolved blocking observation on page 1: PDF INR 600000 versus entered INR 500000 |
| duplicate_original / duplicate_proposal | Accepted record and private draft with identical institution/bank/reference; deterministic duplicate warning |
| matured / today / seven / fifteen / thirty / future | Accepted records at -1, 0, 7, 15, 30 and 31 days; default reminder boundaries |
| renewal_old / renewal_successor | Linked accepted successor; predecessor preserved and superseded |
| release_pending | Awaiting authority decision, still monitored |
| release_approved | Authorized, awaiting evidence-backed completion, still monitored |
| release_rejected | Rejected with reason; instrument remains monitored |
| release_completed | Evidence PDF attached, completion recorded; no longer monitored |
| other_institution | Institution B record, inaccessible to Institution A |

Initial data: **17 instruments, 18 PDFs**. Institution A sees 16 records, Institution B 1, Officer and Authority 16 each (private duplicate draft excluded). At the fixed evaluation date, Institution A dashboard counts are all 16, pending 1, accepted current 11, approaching 7, today 1, matured 1. Counts describe initial state; presenter decisions will change them.

In another terminal while the server is running:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_exports.py --scenarios
```

Success: `PASS`, 24 role/category comparisons, 18 distinct synthetic document downloads, exact initial role scope, local stylesheet HTTP 200, invalid filter HTTP 400. The script is read-only apart from authentication sessions. For the existing development database without scenario seeding, omit `--scenarios`.

## Verify all milestones

```powershell
.\Verify-Demo.ps1
```

This runs system checks, checks migration drift, runs every acceptance test and renders the due-action report at the fixed date. On the original development database, retain the earlier saved smoke manifests and verify preserved flows against a restarted server:

The release-audit version of Verify-Demo.ps1 also rejects unapplied migrations and runs the frozen synthetic evaluation set, writing data/release-evaluation.json. See release-readiness.md for current results and limitations; the earlier milestone verification document is historical.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_http.py --verify
.\.venv\Scripts\python.exe scripts\smoke_scrutiny.py --verify
.\.venv\Scripts\python.exe scripts\smoke_maturity.py --verify
.\.venv\Scripts\python.exe scripts\smoke_renewals.py --verify
.\.venv\Scripts\python.exe scripts\smoke_releases.py --verify
.\.venv\Scripts\python.exe scripts\smoke_exports.py
```

The old `--verify` scripts require their saved manifests and records; a clean package intentionally does not contain them. The full test suite and new scenario verification cover the fresh package.

## Backup and recovery

Stop the demo server with Ctrl+C before copying a consistent backup. Keep the **database and documents together**. Store backups privately because they also include local credentials. Never include them in the distributable ZIP. The backup path must be new:

```powershell
$backupPath = Join-Path $PWD ('private-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
if (Test-Path -LiteralPath $backupPath) { throw 'Backup destination exists.' }
Copy-Item -LiteralPath .\data -Destination $backupPath -Recurse
```

For recovery, extract a second copy of the same ZIP into a **new** folder; do not run setup yet. Copy the backup into that new folder as `data` (fail if a `data` directory already exists), then run setup with Python 3.12. Existing accounts, credentials, scenarios and decisions are retained. Setup will not erase missing or inconsistent scenario data; investigate any manifest error rather than rerunning seed commands to replace it.

Verify recovery with `Verify-Demo.ps1`, the fixed-date due-action report, and `smoke_exports.py --scenarios` against the restored server (initial scenarios only). Compare SHA-256 for the backup/restored SQLite file before starting either server, and for every document; run `PRAGMA integrity_check` with SQLite. Once either server runs, authentication sessions can change the database hash. Preserve the backup until recovery has passed. Never restore over the only copy of existing work.

## File responsibilities

`portal/exports.py` formats CSV and protects spreadsheet text. `portal/views.py` shares authorization/filter selection between HTML and CSV. `test_exports.py` verifies permissions, filters, precision, escaping and read-only behavior. `seed_scenarios.py` builds synthetic cases using the existing services and saves an idempotency manifest, with file cleanup on rollback. `test_demo_workflow.py` checks scenario lifecycle, boundaries, rerun preservation, rollback and package integrity. `build_offline_demo.py` copies an allowlisted source tree and pinned wheels into a checksummed ZIP. `setup_offline.py` validates and installs that package. The three root PowerShell scripts provide setup, localhost startup and acceptance verification. `smoke_exports.py` checks actual authenticated HTTP behavior.

Limitations remain unchanged: uploaded PDF checks do not prove authenticity or malware safety; page references are manual; no bank verification or transaction occurs. Release completion is a manual evidence-backed record. SQLite, DEBUG and localhost serving are suitable for this synthetic demonstration.
