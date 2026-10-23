# Final verification — Milestone 6

Historical Milestone 6 evidence follows. The subsequent release audit, fixes, 159-test gate, measured rule evaluation and remaining sign-off blockers are documented in [release-readiness.md](release-readiness.md).

Verified on 23 October 2026 (Asia/Kolkata), Windows, Python 3.12.14, Django 5.2.18, local SQLite and localhost development server. These are synthetic local checks, not production capacity or regulatory validation.

| Check | Observed result |
|---|---|
| Baseline Milestones 1–5 | 134 tests passed before changes |
| Final complete suite | **143 tests passed**, 45.346 seconds on the final source; original 134 tests retained |
| Django system checks | No issues |
| Migration drift | No changes detected; no Milestone 6 migration |
| Existing milestone HTTP checks after restart | Submission/correction, scrutiny/page reference/resolution, maturity/report, renewal lineage and release/evidence checks all passed |
| Existing data preservation | All rows in all seven portal tables exactly equal the pre-Milestone-6 SQLite backup: 20 instruments, 25 documents, 2 observations, 2 release requests, 82 audit events, 2 institutions, 2 profiles |
| Scoped CSV HTTP checks | 24 role/category comparisons passed against the existing database; invalid dates/categories returned 400; anonymous requests redirected to login |
| Fresh offline install | New venv without ensurepip; pip bootstrapped from bundled wheel; all dependencies installed using `--no-index`; migrations, four random-password accounts and synthetic scenarios created successfully |
| Packaged acceptance script | System checks and migration check passed; all 143 packaged tests passed (44.462 seconds); fixed-date due-action command succeeded |
| Synthetic scenarios | 17 instruments, 18 PDFs; A sees 16, B sees 1, Officer/Authority see 16 each; 24 role/category comparisons and all 18 document downloads passed |
| Repeat offline setup | No migrations needed; existing accounts unchanged; existing scenario manifest retained; no data reset |
| Backup/recovery | Stopped isolated server, copied data, restored into a new extraction; all copied file SHA-256 values equal before setup; SQLite integrity_check = ok; all 18 document hashes match stored metadata |
| Recovered setup and HTTP | Both credential files, scenario manifest and 18 PDFs preserved; 24 role/category comparisons and 18 document downloads passed against recovered server |
| Archive contents | No live data directory, database, uploaded document, credentials, .env or venv included; local assets and five pinned wheels included |

The nine new tests cover CSV scope/filter parity for all four roles and all six categories, invalid inputs, anonymous/unassigned access, spreadsheet text protection, Unicode/CSV round-trip, exact currency precision, historical lifecycle exclusion, empty/read-only export, synthetic workflows and reminder boundaries, rerun preservation, transaction/file rollback, namespace collision, DEBUG restrictions, checksums and path traversal rejection. Expected 400/403 cases log tracebacks in DEBUG mode while the test suite passes.

## Local measurements

The HTTP verifier measured one CSV request for each of four roles × six categories. Existing database: 20 instruments, median **10.15 ms**, range **8.09–29.52 ms**, n=24. Fresh isolated synthetic database: 17 instruments, median **19.46 ms**, range **8.23–33.85 ms**, n=24. Recovered synthetic database: median **12.48 ms**, range **8.18–32.33 ms**, n=24. Measurements include localhost HTTP overhead; the fresh run overlapped the acceptance suite. They are observations from this workstation, not load tests or service guarantees. Manual processing time, bank turnaround and operational savings were not measured; no speedup claim is made.

## Remaining manual checks and limits

Visual browser QA remains manual; authenticated HTTP checks do not establish layout quality. A target-machine rehearsal with the physical network disconnected was not performed; wheel-only installation with pip's package index disabled and local asset requests were verified. Python 3.12 must already be installed on the target machine. A fresh extraction generates its own credentials; the ZIP contains none from this workspace.

No new product features were added beyond the agreed scoped CSV export. Existing manual scrutiny, maturity calculations, renewal and release semantics remain in place. No bank verification, OCR, notifications or payment execution is introduced. For exact commands, file responsibilities, synthetic walkthrough and recovery instructions, see [offline-demo.md](offline-demo.md).
