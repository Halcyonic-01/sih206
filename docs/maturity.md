# Milestone 3: maturity visibility and due actions

This document covers read-only maturity reporting introduced in Milestone 3. Renewal lineage is documented in `renewals.md`; Milestone 5 release handling is in `releases.md`. Notification storage, delivery and scheduling remain unimplemented. Milestones 1 and 2 retain their review and scrutiny workflows.

## Date and scope semantics

The default evaluation date is the current date in `BUSINESS_TIMEZONE` (default `Asia/Kolkata`, configured as Django `TIME_ZONE`). Calculations use date-only arithmetic, including leap days and year boundaries. Dates never change the instrument's review state or bank-verification status.

Browser dashboard/register overrides use `?as_of=2026-10-23` only in local `DEBUG` mode. They are visibly labeled **Demo evaluation date**, and dashboard links preserve that date. Without the parameter, the actual business date is used. Instrument detail pages always show the actual business date with an explicit label; a report override does not change the application clock. Invalid dates/categories return HTTP 400. Outside local DEBUG mode, nonempty browser date overrides are rejected.

## Dashboard and filtered register

Open `/dashboard/` after signing in. Institution accounts see only their institution. Officer accounts see the existing authorized scope, excluding private drafts. Each card links to the same scoped records using a `category` query parameter on the existing register.

| Category | Meaning |
|---|---|
| `all` | All records visible to the current account |
| `pending` | Submitted, awaiting officer review |
| `accepted` | Accepted instruments that have not been superseded or completed release, including matured ones |
| `approaching` | Accepted, maturity strictly after evaluation date and within the largest configured reminder threshold |
| `today` | Accepted, maturity equals evaluation date |
| `matured` | Accepted, maturity precedes evaluation date |

Maturity categories are disjoint subsets of accepted current records; accepted and all cards overlap these subsets. Do not sum every dashboard card together. Drafts and changes-requested/submitted records do not enter maturity action lists until accepted. Superseded predecessors leave current monitoring only when their successor is accepted. This is an explicit prototype monitoring policy, not an assertion that unaccepted documents have no maturity risk. Declared maturity facts and historical records remain visible in the register/detail views.

The original landing behavior is preserved: institution accounts see their register; officer accounts see pending submissions. Both have Dashboard/Records navigation. Officers can now explicitly select `accepted` or `all` to find accepted instruments.

## Reminder bands

`REMINDER_DAYS=30,15,7` is demo configuration, not an AICTE-prescribed requirement. Thresholds are positive integers; order/duplicates are normalized when used.

For the defaults:

- 1–7 days remaining: within 7-day band.
- 8–15 days: within 15-day band.
- 16–30 days: within 30-day band.
- More than 30 days: outside the reminder window.
- 0 days: matures today, reported separately.
- Negative days: matured, with the signed number of days remaining.

These are current action bands, not claims that notifications were sent on exact threshold dates. No renewal eligibility, minimum amount, breach or penalty is inferred from maturity.

## Due-action command

```powershell
.\.venv\Scripts\python.exe manage.py due_actions --as-of 2026-10-23
.\.venv\Scripts\python.exe manage.py due_actions --as-of 2026-10-23 --institution DEMO-A
.\.venv\Scripts\python.exe manage.py due_actions
```

The report uses the same classification functions as the UI. It includes accepted instruments that are approaching maturity, mature today or have matured. It prints the evaluation date/source, timezone, thresholds, scope, reference, institution code, maturity, signed days remaining, category, reminder band and suggested human follow-up. Rows are ordered by maturity date, institution code, reference and ID.

The CLI is for a trusted local operator with filesystem/database access, not a remotely authenticated user. By default it reports all institutions; `--institution CODE` restricts the report. Unknown institution codes and invalid dates fail explicitly. Do not distribute the report beyond authorized users.

The command only reads: it does not create alerts, audit events, files, status transitions or notification rows. Repeated runs for the same data/date produce the same output and no duplicate records. No email/SMS is sent. A local OS scheduler could invoke this command later, but unattended scheduling and delivery have not been deployed or demonstrated.

## Configuration

No dependency or database migration is needed. Optional PowerShell configuration, set before starting the application:

```powershell
$env:BUSINESS_TIMEZONE = 'Asia/Kolkata'
$env:REMINDER_DAYS = '30,15,7'
```

`.env.example` documents these names but is not auto-loaded. Configuration changes require restarting the server.

## Verification

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test portal.tests --verbosity 2
```

New tests cover all threshold boundaries, timezone crossings, leap/year changes, dashboard/card list agreement, institution/role isolation, unchanged landing behavior, custom windows, read-only repeated runs, safe input errors, terminal control characters, and date overflow. Existing Milestone 1/2 tests remain part of this suite.

With the local server and generated demo accounts available:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_maturity.py
# Restart the server, then:
.\.venv\Scripts\python.exe scripts/smoke_maturity.py --verify
```

The live script creates nine new synthetic `MATURITY-...` records through actual submission/review HTTP requests, covering yesterday, today, 7/15/30/31 days, another institution, pending review and a draft. It leaves existing records unchanged. It follows dashboard links, compares card counts with actual table rows, checks the command against officer dashboard counts, and compares database hashes around repeated command runs. The `--verify` phase reuses the saved scenario without creating more records. Local date overrides must be enabled (`DEBUG=true`), and generated credentials must be present in ignored `data/demo-credentials.txt`.

For the fixed evaluation date **23 October 2026**, maturity on **22 October** is matured, **23 October** is today, **30 October** is seven days away, **22 November** is thirty days away, and **23 November** is outside the default window.

## Verified results

- All **79 tests passed**, including the previous 49 regression tests.
- Django checks passed and migration drift check reported no changes.
- All three live HTTP workflows passed, including dashboard/list/report agreement.
- Repeated command output was identical and database hashes remained unchanged during those runs.
- All three restart verification scripts passed.
- Pre-existing instruments, documents, observations, audit events, account credentials and role assignments were preserved against the pre-update database backup; original PDF hashes matched.

The Milestone 5 full suite includes 134 passing tests, retaining all 79 Milestone 1–3 tests. Approved releases remain monitored until completion; completed releases are excluded. Selected evaluation dates calculate maturity against current lifecycle state; they do not rewind supersession/release history. Live checks add synthetic demo records only. Visual browser QA remains manual; HTTP checks do not establish visual correctness. Milestone 6 CSV and packaging are documented in offline-demo.md.
