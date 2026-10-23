# Beginner testing walkthrough: every step and expected result

This guide assumes you have never used Django. Read one numbered step, do it, compare the result, then continue. All examples are synthetic. Do not test by corrupting the only database, removing permissions from real folders or uploading real confidential records.

Use a **fresh Git clone** of the team's repository and record its commit. Earlier developers' demos changed their local sample records. Running the source setup in a new clone creates the predictable starting state. Seeding does not reset old decisions.

## Before you start: three windows and a notebook

1. Clone the repository using root README section 4A, then open the cloned folder containing manage.py in File Explorer.
2. Click its address bar, type `powershell`, press Enter. Call this **Terminal A**. It will run the server.
3. Repeat to open **Terminal B** in the same folder. It will run checks while A stays open.
4. Open your target browser. Call it **Browser**.
5. Copy [test-record-template.md](test-record-template.md) into a private local note and fill in actual results. Do not pre-mark passes.

When this guide says “run”, paste the command in PowerShell and press Enter. Do not paste it in the browser's address bar. Do not type the prompt text such as PS C:\...>. A password is case-sensitive; copy only its value, not the username, colon or trailing space.

The example server uses port **8010**. Browser address: **http://127.0.0.1:8010/**. A restored copy later uses 8011. Different ports in old documents belong to old local processes; use one port consistently per copy.

## Optional five-hour learning session

Times are a learning allowance, not a measured installation/test duration. Pause when a result differs.

| Minutes | Activity |
|---|---|
| 0–30 | Fresh setup, locate folders, Python and credentials |
| 30–50 | Automated baseline and reading results |
| 50–70 | Untouched seeded dashboard, PDFs and CSV |
| 70–110 | Create, validate, submit and accept one record |
| 110–150 | Manual discrepancy → correction → explicit resolution |
| 150–175 | Maturity/report boundary checks |
| 175–210 | New linked renewal and stale-edit behavior |
| 210–245 | Release request, rejection, authorization and evidence |
| 245–265 | Unauthorized access and safe failure cases |
| 265–290 | Disconnected rehearsal and backup/restore |
| 290–300 | Evidence record, optional HTTP commands and handover decision |

## Phase 1 — setup (0–30 minutes)

### T01. Confirm the folder and Python

In Terminal B:

```powershell
Get-Location
Test-Path -LiteralPath .\manage.py
py -3.12 --version
```

**Expected:** the folder is your cloned project, True, and Python 3.12.x. If False, open the cloned project folder, not its parent. If Python is missing, follow the root README before continuing. Do not copy another machine's .venv.

### T02. Install and seed the fresh clone

The clone contains source, not the previous developer's .venv, database or offline wheelhouse. Internet is needed for the first dependency download. In Terminal B:

```powershell
git rev-parse HEAD
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo --generate-password
.\.venv\Scripts\python.exe manage.py seed_demo --authority-only --generate-password
.\.venv\Scripts\python.exe manage.py seed_scenarios
```

Expected: pinned packages installed, migrations applied, four accounts created and 17 synthetic instruments/18 PDFs seeded. Record the commit ID. Do not run Setup-Offline.ps1 in an ordinary clone; its package-manifest/wheelhouse are intentionally not committed. Do not recreate an existing .venv or delete existing data to force these commands through.

### T03. Find the private passwords

In File Explorer, open data, then demo-credentials.txt. It lists institution_a, institution_b and officer. authority-credentials.txt lists authority. Keep them private and leave the files unchanged during testing. A fresh source setup generates its own random passwords; there is no password printed in this guide.

## Phase 2 — automated baseline (30–50 minutes)

### T04. Run the complete gate before changing sample data

In Terminal B:

```powershell
.\Verify-Demo.ps1
```

**Expected:** system checks pass; no model drift/pending migrations; the baseline reports 159 tests and OK; evaluation all_contract_cases_pass is true; due-action output appears. Some forbidden/bad-request diagnostics and injected Operational request failure lines are expected test cases. The final OK versus FAILED result matters. Save any failure text privately; do not just mark it passed because most tests ran.

If .ps1 execution is blocked, run individually:

```powershell
.\.venv\Scripts\python.exe manage.py check --database default
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate --check
.\.venv\Scripts\python.exe manage.py test portal.tests --verbosity 1
.\.venv\Scripts\python.exe scripts\evaluate_release.py --output data\release-evaluation.json
.\.venv\Scripts\python.exe manage.py due_actions --as-of 2026-10-23
```

Tests/evaluation use separate or in-memory databases. They do not reset the seeded demo. The data/release-evaluation.json output is the new run's measurement; recorded historical results in evaluation/ are separate evidence.

### T05. Start the web server

In Terminal A:

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8010 --noreload
```

**Expected:** Starting development server at http://127.0.0.1:8010/. Leave A open; new lines appear when the browser makes requests. Its development-server warning is expected and is not an instruction to expose it publicly.

In Browser, enter http://127.0.0.1:8010/. Expected: login page with styling. If connection refused, check A is still running and the port matches. If port occupied, choose another free port and change every URL/--base argument in this guide.

## Phase 3 — check the untouched synthetic baseline (50–70 minutes)

### How to change accounts throughout this guide

Click **Sign out** in the top navigation, then log in with the named username and its locally generated password. Ordinary tabs share the login. Use separate browser profiles if you want multiple roles at once. After changing role, refresh old tabs before using them.

### T06. Institution A dashboard

1. Log in as institution_a.
2. Click Dashboard.
3. Enter 2026-10-23 into Optional demo evaluation date.
4. Click View report.
5. Compare each card:

| Card | Expected initial A count |
|---|---:|
| All visible records | 16 |
| Pending officer review | 1 |
| Accepted current records | 11 |
| Approaching maturity | 7 |
| Matures today | 1 |
| Matured | 1 |

The maturity subsets overlap with accepted current as explained on the page. No email is sent. The selected date is a report date, not a change to the computer clock or a rewind of decisions.

### T07. Click a card and export

1. Click Approaching maturity.
2. Count seven rows. Check the page still says demo evaluation date 2026-10-23.
3. Click Export this view as CSV.
4. Find instrument-register.csv in your browser's Downloads. A browser may rename repeated downloads with a suffix.
5. Open it in a text editor or spreadsheet. Expect seven data rows plus one header, all A's institution, the chosen evaluation date and exact two-decimal INR amounts.
6. The bank-verification column must not claim the bank verified anything.

Do not confuse a spreadsheet's display formatting with the raw CSV text. Formula protection is covered by automated tests; do not remove protective apostrophes from suspicious entered text before opening a spreadsheet.

### T08. Download and inspect real sample bytes

1. Click Records and open M6-DISCREPANCY. If you have a filtered list, choose All visible records and Apply filters first.
2. Under Supporting documents, click scrutiny-fdr.pdf.
3. Open the downloaded PDF in the actual viewer you will present with.
4. Confirm one page, a synthetic notice and INR 600000.00.
5. Return to the detail page. It declares INR 500000.00 and has a blocking page-1 manual observation.
6. Open M6-RELEASE_COMPLETED and download its completion evidence too.

**Expected:** PDFs open/read correctly and evidence links match the record. A successful download/hash does not prove readable layout; inspect it. Nothing here proves bank authenticity or malware safety.

### T09. Untouched HTTP baseline

While A keeps the server running, use Terminal B:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_exports.py --base http://127.0.0.1:8010 --scenarios
```

**Expected:** PASS, 24 role/category comparisons and 18 distinct PDF downloads. This command creates login sessions but does not change domain decisions. Run this **before** the next phases add records. Later, omit --scenarios because it asserts the initial 17-record seed state.

## Phase 4 — create, validate, submit and accept (70–110 minutes)

### T10. Create a private draft without a PDF

1. Log in as institution_a.
2. Click New FDR.
3. Enter:

| Field | Value |
|---|---|
| FDR reference | HANDOVER-NORMAL-001 |
| Issuing bank | Fictional Test Bank |
| Deposit amount (INR) | 500000.00 |
| Issue date | 2026-01-01 |
| Maturity date | 2027-01-01 |
| FDR PDF | Leave empty for this first save |

4. Click Save draft. Expected: Draft detail and history, missing-FDR blocking technical finding.
5. Copy the record address into your private notes as **normal record URL**. Its numeric ID is generated; do not assume it is 18.
6. Click Submit for review. Expected: blocked because an FDR PDF is missing; status remains Draft.
7. Sign in as officer and paste that URL. Expected: 404 while the draft is private.

### T11. Required fields, amount/date and invalid upload

1. As institution_a, start a separate New FDR form.
2. Try saving empty required fields. Expected: browser/form errors and no success.
3. Fill values but try amount 0, then -1, then 1.001. Expected: rejection of nonpositive/excess-decimal input.
4. Try maturity 2025-01-01 with issue 2026-01-01. Expected: date-order error.
5. In Terminal B create a harmless invalid test file:

```powershell
Set-Content -LiteralPath .\data\not-a-document.pdf -Value 'This is plain text, not a PDF.' -Encoding ascii
```

6. Use the file picker to choose data/not-a-document.pdf. Try saving with otherwise valid details. Expected: document validation error; no valid new submission created.
7. Close/discard this invalid form without trying to work around validation. Automated document tests cover MIME/extension/oversize cases too.

### T12. Add a PDF and submit

1. Reopen the normal record URL as institution_a.
2. Click Edit / add PDF.
3. Choose fixtures/sample-fdr.pdf from your cloned project folder; Save draft.
4. Click Submit for review. Expected: Submitted, with original draft and submit history.
5. Sign in as officer → Records. Expected: the record is now visible in the pending queue.

The normal PDF is a synthetic transport fixture, not a detailed bank-issued FDR. Its successful upload is not proof that financial fields match. This test demonstrates the administrative workflow.

### T13. Officer acceptance and retained bytes

1. As officer, open HANDOVER-NORMAL-001 and download the supporting PDF.
2. Under Officer decision, choose Accept for tracking.
3. Enter reason: “Tested the synthetic document transport and manual-review workflow; accepted for tracking only.”
4. Click Record decision. Expected: Accepted for tracking, actor/reason/history retained, bank remains explicitly unverified.
5. As institution_a, reopen it. Expected: same accepted status; ordinary editing is locked; the PDF still downloads.

## Phase 5 — full discrepancy and correction flow (110–150 minutes)

Use a new record so the preseeded discrepancy remains available as a fallback.

### T14. Submit a known conflicting amount

1. As institution_a → New FDR, enter reference HANDOVER-DISCREPANCY-001, bank Fictional Test Bank, amount 500000.00, issue 2026-01-01, maturity 2027-01-01.
2. Attach fixtures/scrutiny-fdr.pdf and Save draft → Submit for review.
3. Save its address as **discrepancy URL**.
4. As officer, open it and download the PDF. Page 1 shows 600000.00; declared amount is 500000.00.

**Expected:** no automated amount-mismatch finding appears merely from that PDF. The prototype does not read PDF contents. The next action is a human observation.

### T15. Record a blocking observation and demonstrate the safeguard

1. As officer, scroll to Manual document observations → Add an observation.
2. Select the attached document in the Document dropdown.
3. Enter Page number 1; choose Blocking severity.
4. Enter comment: “Page 1 states INR 600000.00; declared amount is INR 500000.00. Please correct.”
5. Click Record observation. Expected: document/page, actor, comment and Unresolved status appear.
6. Under Officer decision, try Accept for tracking with a reason.
7. Click Record decision. Expected: acceptance blocked with a resolve-blocking-observations message; status stays submitted.
8. Now choose Request corrections with reason “Correct the amount using page 1.” Click Record decision.

**Expected:** Changes requested and preserved observation/history.

### T16. Correcting is not the same as resolving

1. As institution_a, open the discrepancy URL → Edit / add PDF.
2. Change amount to 600000.00. Attach scrutiny-fdr.pdf again to demonstrate a retained additional upload. Save draft.
3. Click Submit for review.
4. As officer, reopen it. Expect two retained documents and the original unresolved observation.
5. Attempt acceptance again with a reason. Expected: still blocked, despite the corrected amount.
6. Locate the original observation's resolution form.
7. Enter “Manually rechecked original page 1 against the corrected INR 600000.00 declaration.” Click Resolve observation.
8. Now choose Accept for tracking, enter “Manually reviewed corrected synthetic declaration.” Click Record decision.

**Expected:** accepted; original and resolved observation, both PDF uploads, previous values, correction and decision history remain. A later edit did not erase the earlier evidence.

### T17. Duplicate warning

1. As institution_a open the Draft entry named M6-DUPLICATE; there are two references with that name, so use its status to distinguish it.
2. Under Technical checks, locate POSSIBLE_DUPLICATE.
3. Confirm it is Warning and refers only to this record's bank/reference, without leaking a different institution's details.

Expected: advisory duplicate behavior, not a fraud verdict or bank verification. Unicode/whitespace normalization is tested automatically against frozen labels.

## Phase 6 — maturity and reports (150–175 minutes)

### T18. Fixed-date boundaries

1. As institution_a → Dashboard → evaluation date 2026-10-23 → View report.
2. Click each maturity card and locate these seed references:

| Seed reference | Expected at fixed date |
|---|---|
| M6-MATURED | Matured: -1 day |
| M6-TODAY | Matures today: 0 days |
| M6-SEVEN | Approaching: within 7 days |
| M6-FIFTEEN | Approaching: within 15 days |
| M6-THIRTY | Approaching: within 30 days |
| M6-FUTURE | Accepted current but outside approaching window: 31 days |

3. Confirm M6-RENEWAL_OLD and M6-RELEASE_COMPLETED remain in All visible records but not accepted-current monitoring.
4. Confirm M6-RELEASE_APPROVED is still current/monitored.

Counts may now differ from the original baseline because you added/accepted records. Check definitions and named cases rather than blindly expecting the old totals.

### T19. CLI and invalid filters

In Terminal B:

```powershell
.\.venv\Scripts\python.exe manage.py due_actions --as-of 2026-10-23
.\.venv\Scripts\python.exe manage.py due_actions --as-of 2026-10-23 --institution DEMO-A
```

Expected: first covers all institutions for the trusted operator; second only A. No messages/notifications are sent. Repeating produces the same report if domain state has not changed. Do not compare whole-database hashes during concurrent browser logins: sessions can change independently.

In Browser visit http://127.0.0.1:8010/?category=invalid and http://127.0.0.1:8010/dashboard/?as_of=invalid. Expected: clear 400 error pages. Return to the correct dashboard afterward.

## Phase 7 — renewal and stale edits (175–210 minutes)

### T20. Create a linked successor

1. As institution_a, open the accepted **normal record URL** from T10–T13.
2. Click Create renewal draft.
3. Enter reference HANDOVER-RENEWAL-001, bank Fictional Test Bank, amount 500000.00, issue 2026-10-23, maturity 2027-10-23.
4. Attach fixtures/sample-fdr.pdf. Save draft.
5. Save the new address as **successor URL**.
6. Open the parent's detail in another tab, as the same institution. Expected: it still remains current while the successor is a draft.
7. A second new proposal is not offered; follow the retained successor link. Staff must not see the private draft's details before submission.
8. Return to successor and Submit for review.
9. As officer, open successor, inspect its PDF, accept with reason “Manually reviewed synthetic linked successor.”

Expected: parent now Superseded, with successor link; child accepted with predecessor link; original documents/history intact; only child is current. Record review status and lifecycle are separate.

### T21. Stale edit without damaging real records

1. As institution_a, create a separate draft HANDOVER-STALE-001 using valid dates/amount. PDF is optional for this draft test.
2. Open its Edit page in two ordinary tabs while logged in as the same account.
3. In the first tab change its bank to Fictional Bank First Save and save.
4. Without reloading the second tab, change its bank to Fictional Bank Stale Save and save.

Expected: second save returns a 409 conflict; the first saved value remains. Reload before further action. Do not alter hidden version values manually. Do not use this draft for subsequent acceptance/release tests.

## Phase 8 — release workflow (210–245 minutes)

### T22. Request and independently authorize release

1. As institution_a, open the accepted **successor URL**. It has no successor proposal of its own.
2. Find Request release. Enter “Synthetic handover release request for human assessment.” Click Submit release request.
3. Expected: Pending authority decision, still monitored. A renewal proposal is blocked while an open release exists.
4. As officer, open it. Expected: read-only release visibility and no authority decision/completion controls. Automated tests separately verify forged POST denial; hidden buttons alone are not proof of security.
5. As authority, click Release requests → open this request.
6. Choose Authorize release, reason “Independent human assessment of the synthetic request.” Click Record authority decision.

Expected: Release authorized; completion pending. It is still monitored. No financial transfer or bank confirmation occurred.

### T23. Require evidence before completion

1. As authority, enter a Completion explanation but leave New completion evidence PDF empty.
2. Click Record release completion. Expected: required-file error; no completed state.
3. Attach fixtures/release-evidence.pdf.
4. Enter “Manually inspected synthetic completion evidence and recorded completion.” Click Record release completion.
5. Expected: Release completion recorded, new evidence download link and preserved authority decision/history.
6. Download/open evidence in the target viewer.
7. Visit accepted-current list and All visible records. Expected: successor excluded from current, retained in all/history.
8. Refresh detail. Completed actions must not become editable/replayable; parent remains superseded.

### T24. Rejection is retained and does not end monitoring

1. As authority → Release requests, set status Pending authority decision if needed, Apply filter.
2. Open seed M6-RELEASE_PENDING, which this manual guide has not otherwise changed.
3. Choose Reject request and enter “Synthetic rejection: supporting confirmation is missing.” Record authority decision.
4. Filter queue to Rejected → Apply filter and reopen it.

Expected: rejection reason and actor persist; instrument remains current; it has no evidence-backed completed state. This changes the seed's initial state, so --scenarios is no longer appropriate for this copy.

## Phase 9 — access controls and failure handling (245–265 minutes)

### T25. Institution isolation

1. As institution_a, copy a normal/discrepancy detail URL and one document-download link into private notes.
2. Sign out; paste the document URL. Expected: login required.
3. Sign in as institution_b. Records should contain only B's seed record unless you deliberately created B records.
4. Paste A's detail and document URLs. Expected: 404, no A data/download.
5. Export B's view. Expected: B's rows only.
6. As officer or authority, try /instruments/new/. Expected: forbidden for those roles.

### T26. Wrong login, errors and operational failure tests

1. Sign out. Enter a deliberately wrong password once. Expected: login error, no protected page. Use the correct password afterward.
2. Inspect displayed form errors, not just the terminal. Confirm entered safe fields remain understandable and errors do not look like success.
3. In Terminal B run:

```powershell
.\.venv\Scripts\python.exe manage.py test portal.tests.test_reliability portal.tests.test_configuration --verbosity 2
```

Expected: tests pass; injected DB/storage failures return safe responses, preserve state and clean up known new files; invalid config fails early. These tests use isolated state. Do not simulate disk/database failure by damaging your running demo.

### T27. State the upload limitation honestly

The automated reliability/evaluation cases include a deliberately unreadable PDF-shaped body with valid markers. The current envelope policy can accept it into a draft. It is not automatically bank-verified or accepted for tracking. Mark this as a **known limitation**, not a successful readability/security validation. Do not open unknown malicious PDFs or claim this prototype is safe for untrusted real documents.

## Phase 10 — offline and recovery rehearsal (265–290 minutes)

### T28. Fully disconnected operation and fresh installation

Prepare before disconnecting:

1. Keep the current server running. While online, make a separate fresh Git clone for the offline rehearsal using the root README clone instructions; do not seed it yet.
2. In that separate clone, create .venv and download the pinned application wheels locally:

```powershell
py -3.12 -m venv .venv
py -3.12 -m pip download --only-binary=:all: --dest data\offline-wheels -r requirements.txt
```

3. data/offline-wheels is ignored; do not commit it. Keep Python 3.12 already installed. Optionally prepare one more unseeded clone for recovery before disconnecting, since GitHub itself requires connectivity.
4. Turn Wi-Fi off, unplug Ethernet and disable tethering. Try a new external page with a hard refresh; it should fail. Do not mistake a cached page for connectivity.
5. Refresh the already-running localhost dashboard, download a PDF and export CSV. Expected: all work.
6. In the separate offline-rehearsal clone, install and seed without reconnecting:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --find-links data\offline-wheels -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo --generate-password
.\.venv\Scripts\python.exe manage.py seed_demo --authority-only --generate-password
.\.venv\Scripts\python.exe manage.py seed_scenarios
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8012 --noreload
```

7. Open localhost:8012, use that clone's credentials and rehearse the short demo. Expected: complete operation with physical connectivity disabled.
8. Record the actual disconnected result. Local-only package installation is not a substitute for performing the full manual rehearsal.

Label folders/terminals so you do not confuse this fresh copy with the manual-test copy containing HANDOVER records. Reconnect when the disconnected test is finished. No ZIP is required for this procedure.

### T29. Back up the manual-test copy safely

Return Terminal B to the original manual-test folder; confirm Get-Location. Stop its server first. Run:

```powershell
$manualRoot = (Get-Location).Path
$backupRoot = Join-Path (Split-Path -Parent $manualRoot) ('fdr-private-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
if (Test-Path -LiteralPath $backupRoot) { throw 'Backup destination already exists.' }
Copy-Item -LiteralPath (Join-Path $manualRoot 'data') -Destination $backupRoot -Recurse
$backupRoot
```

Expected: a new private folder beside the project containing portal.sqlite3, documents, credentials and scenario manifest. Save its path privately. Do not commit or upload this backup to GitHub; it includes local credentials/sessions. Never back up only SQLite and forget the PDFs.

### T30. Restore into another fresh clone, without overwriting

1. Clone the same GitHub commit into another new folder while online, or use the separate clone prepared before disconnecting. **Do not migrate/seed it yet.**
2. Find the cloned project folder containing manage.py. Copy its full path from Explorer.
3. In the original Terminal B, set the path below by replacing the placeholder, then copy the backup:

```powershell
$restoreRoot = 'PASTE-THE-NEW-CLONED-PROJECT-FOLDER-PATH-HERE'
if (-not (Test-Path -LiteralPath (Join-Path $restoreRoot 'manage.py'))) { throw 'Not a project folder.' }
$restoreData = Join-Path $restoreRoot 'data'
if (Test-Path -LiteralPath $restoreData) { throw 'Restore data already exists. Choose a fresh clone.' }
Copy-Item -LiteralPath $backupRoot -Destination $restoreData -Recurse
$originalDbHash = (Get-FileHash -LiteralPath (Join-Path $backupRoot 'portal.sqlite3') -Algorithm SHA256).Hash
$restoredDbHash = (Get-FileHash -LiteralPath (Join-Path $restoreData 'portal.sqlite3') -Algorithm SHA256).Hash
if ($originalDbHash -ne $restoredDbHash) { throw 'Restored database hash differs before startup.' }
Set-Location -LiteralPath $restoreRoot
```

4. Create a local environment if absent, install requirements, then apply migrations in the restored clone:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
```

If still offline, replace the pip install line with --no-index --find-links followed by the **full path to the prepared wheels** from T28, then -r requirements.txt. Never copy another clone's .venv. Expected on the same commit: no migrations needed; restored accounts, scenario manifest and decisions remain. No reseeding is needed to restore them.
5. Verify database integrity and document hashes:

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; print(sqlite3.connect('data/portal.sqlite3').execute('PRAGMA integrity_check').fetchone()[0])"
.\.venv\Scripts\python.exe -c "import sqlite3,hashlib; from pathlib import Path; rows=sqlite3.connect('data/portal.sqlite3').execute('SELECT file,sha256 FROM portal_document').fetchall(); assert all(hashlib.sha256((Path('data/documents')/name).read_bytes()).hexdigest()==digest for name,digest in rows); print('All stored document hashes match:',len(rows))"
```

Expected: ok and all stored hashes match. The number depends on your manual uploads, not the old 18-PDF starting state.

6. Start restored server on 8011, log in using the **restored** private credentials and open http://127.0.0.1:8011/.
7. Locate HANDOVER-DISCREPANCY-001 and HANDOVER-RENEWAL-001. Expected: corrected/accepted history, superseded parent, completed successor release, original PDFs and completion evidence survive.
8. Compare record/document/history behavior, not the whole SQLite hash after logins—sessions/last-login activity can change it.

If any step fails, preserve the private backup and failure notes. Do not erase data to get a green checkmark. Return to the known-good copy for presentation.

## Phase 11 — final record and optional HTTP walkthrough (290–300 minutes)

### T31. Optional repeatable live HTTP checks

These scripts add new synthetic records and store their own result manifests in the project folder from which they run. Run only in a disposable synthetic copy, with its server running. Substitute its actual port consistently:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_http.py --base-url http://127.0.0.1:8010
.\.venv\Scripts\python.exe scripts\smoke_scrutiny.py --base-url http://127.0.0.1:8010
.\.venv\Scripts\python.exe scripts\smoke_maturity.py --base-url http://127.0.0.1:8010
.\.venv\Scripts\python.exe scripts\smoke_renewals.py --base-url http://127.0.0.1:8010
.\.venv\Scripts\python.exe scripts\smoke_releases.py --base-url http://127.0.0.1:8010
```

Expected: each prints PASS and says synthetic records remain. Stop/restart that same server, then repeat the same five commands with `--verify` added. This checks saved records without creating them again. Fresh clones intentionally do not contain old result manifests, so --verify cannot run first. After mutations, use smoke_exports with --base and **without** --scenarios.

### T32. Decide honestly

1. Fill in every actual result and the machine/browser/viewer/date.
2. Mark failed, skipped and not-applicable checks separately. Attach relevant error text and synthetic-only screenshots if permitted; exclude passwords.
3. Name each blocker, the exact reproduction, expected versus actual behavior and its owner.
4. Use a separate fresh clone for the five-minute presentation, because this testing copy now contains extra records and changed decisions.
5. If all target-demo checks pass, sign off the **scoped synthetic localhost demo**. Public deployment/real-data use still requires the controls in the release report; bank authentication, OCR and regulatory accuracy remain outside the implementation.

## Quick answers when you get stuck

- Blank/failed page: confirm terminal/server/port, then read the actual error. Do not keep clicking a consequential button.
- Wrong account: Sign out, log in as the named role, refresh old tabs.
- Missing record: choose All visible records and Apply filters; staff cannot see private drafts.
- Missing release request: check queue status filter and correct account.
- Seed counts wrong: confirm a fresh clone and fixed report date; seeding does not reset decisions.
- Old code still running: --noreload requires stopping and restarting after Python edits.
- Optional offline-installer checksum mismatch: ordinary Git clones use source setup, not the separate bundle installer. Do not remove its integrity check.
- No PDF preview: the app intentionally downloads attachments; inspect the downloaded file in your viewer.
- Tests show errors in console: some are intentional fault/permission cases. A final FAILED is not acceptable; final OK plus an actual target-browser rehearsal is the goal.
