# Final local submission checks - 25 October 2026

Source: main `a1b990b` (PR #21). Checks only; no application or teammate source code changed, no push or remote issue created. Reports are local. Runtime checks use SQLite, not the private remote database.

## Verified results

| Check | Actual outcome |
|---|---|
| Django system check | No issues |
| Migration generation check | No changes detected |
| Migration application check | No pending migrations |
| Python dependency consistency | No broken requirements |
| Frontend build including TypeScript | Passed |
| Full frontend unit/component suite | 120 passed, 13 files, 91.74 seconds |
| Full Django suite | 670 tests in 424.146 seconds; 1 failure, 1 teardown error, 1 skipped. NOT GREEN. Notification failure came from the run's NOTIFY_SEND_ON_COMMIT=false override; it passed on focused rerun without that override. |
| Focused backend recheck | 3 test bodies passed in 6.880 seconds, but ConfirmationAndCoverage teardown still errors with WinError 32 (locked PDF). |
| Local home/API health | HTTP 200; health status ok |
| Current demo audit chain | OK; 221 sealed, 82 sealed late, zero unsealed |
| S2 synthetic calculations | 76/76 passed; 10 finding scenarios; shortfall, term gap and overdue-proof precision/recall 1.0 each, zero FP/FN; total case time about 0.046 seconds |
| CSV synthetic labels | 7/7 passed |
| KPI synthetic snapshots | 10/10 passed |
| Release prerequisite labels | 40/40 passed |
| Frozen historical evaluation | 24 metadata cases and 10 upload-envelope cases passed; not current PDF-parser or AI accuracy evaluation |
| Demo PS7 release | Case 1 COMPLETED, monitoring false (read-only inspection) |
| Secret tracking | .env and data files not tracked |

Evaluation datasets are author-labelled synthetic regression sets, not independent or held-out real-world benchmarks. Their perfect scores do not establish regulatory correctness, bank authenticity or AI accuracy. No fresh external AI calls were made in this final run; earlier live smoke checks are historical evidence only.

## Remaining before submission

1. **Blocker: clean backend regression.** Kushagra/scenario-test owner: `scenarios/tests/test_ps_review_fixes.py`, `ConfirmationAndCoverage.test_record_download_and_export_write_explicit_access_rows`, obtains a streaming PDF response without consuming/closing it. On Windows, class cleanup cannot delete the temporary PDF (WinError 32). It reproduced in a focused rerun. Close/consume the response through its normal test lifecycle; do not disable cleanup. Then rerun the complete suite. Also run with NOTIFY_SEND_ON_COMMIT=true (or no override); the notification on-commit test expects that setting. The notification test passed with its intended setting; the initial failing run is not a passing full-suite result.
2. Yash/platform owners: update `frontend/tests/records.spec.ts` after the redesign. Static inspection finds old status expectations (`SUBMITTED`, `CHANGES_REQUESTED`, `ACCEPTED`), old `Checks & observations` tab and an extraction control used without expanding `Read details from this document`. The spec expects AI off while the current demo is enabled. Run the updated Playwright journeys on a disposable seeded instance with explicit AI/OCR settings, not the recorded demo database. No browser suite was executed in this check.
3. Saksham/shared API owners: complete OpenAPI serializer declarations. Schema generation emits diagnostics for several APIViews (including release case/actions/summary) and colliding operation IDs. This is incomplete contract documentation, not by itself proof the endpoints fail.
4. Review the final edited video: playable from start to end, readable, audible, required duration, no visible credentials or keys. Confirm all required submission fields, links and access permissions on the competition portal.
5. Preserve a consistent local database/document backup and a tested fallback. A physically disconnected rehearsal and a fresh-machine setup have not been repeated in this run. Do not claim offline AI; external AI requires network/provider availability.
6. Preserve synthetic/draft/unsigned labels. Do not claim live bank confirmation, money transfer, approved regulatory policy, production digital signatures or independently evaluated AI accuracy.

## Public deployment remains separate

`manage.py check --deploy` reports W004, W008, W012, W016 and W018: HSTS off, HTTP-to-HTTPS redirect off, secure session/CSRF cookies off, DEBUG on. These are appropriate for this localhost run, not public hosting. Public deployment needs a production configuration, HTTPS, private secrets/storage and its own verification. No deployment was performed.

## Reproduce locally

```powershell
$env:DATABASE_BACKEND='sqlite'
$env:NOTIFY_SEND_ON_COMMIT='true' # expected by the notification on-commit regression test
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate --check
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe manage.py test --verbosity 0
.\.venv\Scripts\python.exe manage.py verify_audit_chain
.\.venv\Scripts\python.exe -m evaluation.s2.run --output data\final-s2-results.json
.\.venv\Scripts\python.exe -m evaluation.s4.run
.\.venv\Scripts\python.exe -m evaluation.s4.kpis.run
.\.venv\Scripts\python.exe -m evaluation.s5.run
Set-Location frontend
npm run build
npm test
```

Captured logs: `data/final-backend-tests.log`, `data/final-backend-recheck.log`, `data/final-frontend-tests.log`, `data/final-frontend-build.log`, `data/final-deploy-check.log`. Results are private local artifacts, not committed proof of future runs.

## Follow-up: requested test fixes verified

The user authorized the previously restricted test changes. The streaming PDF response is now consumed/closed in `finally`; the redesigned browser labels/routes, required source label and collapsed extraction panel are updated. Full backend rerun: **670 tests, OK (1 skipped), 482.848 seconds**. Full Chromium browser run on a disposable seeded database/server: **4 passed, 23.6 seconds**, including responsive layout and PDF rendering. TypeScript check passed. See `REGRESSION_FIXES_2026-10-25.md`. Earlier failed results above are retained as historical evidence; those two test blockers are now resolved. All changes remain local and unpushed.

## Release decision (initial run; superseded for those two test blockers by the follow-up above)

The local synthetic demo remains available, but final all-tests-green sign-off is withheld. No teammate-owned source was changed. Fix the reproducible scenario test teardown and rerun the full backend suite; update and rerun browser journeys on disposable data; complete the manual submission checklist. No public deployment or production readiness is claimed.
