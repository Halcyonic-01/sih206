# Release-readiness audit — 23 October 2026

## Decision

**NO-GO for an unconditional release or public/real-data deployment.** Automated acceptance for the approved localhost FDR MVP passes. Final target-browser visual, PDF-viewing and offline presentation rehearsal remains open. Do not describe the project as a general AICTE application-validation, OCR, bank-authentication or regulatory-compliance system.

This audit inspected actual source, tests, settings, migrations, fixtures, package scripts and local HTTP behavior rather than treating milestone code as proof. It preserved the original database, backed it up, reproduced defects before fixes, and tested corrections. No new product workflow, external integration, AI model or architecture replacement was added.

## 1. Requirements and milestone matrix

The original problem statement concerns security deposits/FDRs. The subsequent approved six milestones narrowed that problem to a feasible administrative lifecycle demonstration. Broad official capabilities and approved MVP capabilities are distinguished below.

| Approved milestone / requirement | Actual implementation | Evidence and completion judgment |
|---|---|---|
| M1: institution entry, PDF, submission, officer review/correction, acceptance, audit | Instrument/Document/AuditEvent; forms; services; institution scope; protected download | Existing submission/document/permission tests; fresh real HTTP correction/resubmission and restart checks. Locally verified. |
| M2: deterministic findings; manual observations with document/page reference | Two named checks; ReviewObservation; explicit resolution; unresolved blocking observations prevent acceptance | Validation/observation tests and real HTTP mismatch/correction/resolution. Unicode/whitespace false negatives found and fixed. Locally verified within narrow rule contract. |
| M3: maturity, dashboard and due-action report | Shared deadlines functions, six filtered categories, 30/15/7 demo thresholds, trusted-operator CLI | Boundary/scope/read-only tests; HTTP dashboard-to-list checks; repeated CLI output. Locally verified. No delivered reminders. |
| M4: renewal lineage | One retained successor; parent remains current until child acceptance; atomic supersession | Renewal tests and real HTTP; old PDFs/history retained; recovered histories rechecked. Locally verified. No cancellation/branching. |
| M5: requests, authority decision, evidence-backed completion | Separate request/authorize/reject/complete services; independent Authority; new completion PDF required | Release tests and live HTTP; authorization remains monitored; completion excludes current monitoring; database-failure rollback tested. Locally verified administrative state, not bank settlement. |
| M6: scoped CSV, offline package, synthetic scenarios and final verification | Shared register/export scope, spreadsheet-text protection, pinned wheel ZIP, 17 seeded instruments, operational scripts | Export/package/scenario tests; fresh wheel-only setup; 24 role/category comparisons and 18 seeded PDF downloads. Automated portion verified; visual/target rehearsal open. |
| Human oversight and evidence | Officer decision with reason; document-linked observations; blocking resolution; separate authority action | Same-lineage integration test traverses conflicting amount → correction → acceptance → renewal → authorized release → evidence-backed completion. Verified supported workflow. Human interpretation itself is not evaluated. |
| General application/cross-document/regulatory validation | No application aggregate, OCR, extractor, policy engine or authorized rule dataset | Not implemented; outside approved six-milestone MVP. Cannot be marked complete against a broader product claim. |
| Authorized-source/bank/AICTE integration | No connectors or verification-success simulator | Not implemented; all records explicitly unverified. No external-service failure tests are applicable to runtime integrations that do not exist. |
| Automated alerts/escalations, payment/refund execution, encryption at rest | None | Deferred from the MVP; official problem statement is not fully delivered. Maturity views and release records do not constitute these capabilities. |

There are no TODO/FIXME feature stubs or mock network-success responses in the inspected runtime code. Deliberate simplifications include fixed technical rules, synthetic seed data/date, a DEBUG-only local secret fallback, SQLite, local files and development serving. These are not evidence of production readiness.

## 2. Defects reproduced and fixed

| Finding | Reproduction | Fix and actual verification |
|---|---|---|
| Database/storage failures escaped views; DEBUG could expose exception content | Initial six reliability tests produced five errors, including OperationalError and storage permission/disk failures | New OperationalSafetyMiddleware returns generic 503 for view-level DatabaseError/OSError after atomic service rollback. No automatic write retry. Failure log contains exception class only. Scrutiny, renewal and completion rollback/file-cleanup tests pass. |
| Sensitive edit/login forms lacked consistent no-store headers | New cache-control assertion failed | Middleware applies never-cache headers to all responses; regression tests pass. |
| Duplicate matching normalized inputs differently in Python and SQLite | Fixed dataset: duplicate TP 9, FP 0, FN 4, TN 11; missed accented uppercase, tabs, non-breaking spaces and casefold cases | Same strip/casefold normalization on both sides, scoped streamed values; technical-v2 snapshot version. Unchanged dataset: TP 13, FP 0, FN 0, TN 11. Old snapshots not rewritten. |
| Invalid upload limits/timezone passed settings import | Zero/negative MAX_UPLOAD_MB and Invalid/Zone returned import exit code 0 | Startup now fails with clear configuration errors; subprocess tests cover invalid limits/timezones and missing non-DEBUG secret. |
| Isolated first HTTP journey had no port argument | First smoke script assumed port 8000 | Added --base-url, consistent with other journey scripts; verified on isolated port 8003. Operational test tooling only. |

Application dependencies remain unchanged. No schema migration was added. Global database/storage exception handling does not guarantee recovery from process termination, failed cleanup, session middleware writes or every unexpected programming error. Those remain limitations.

## 3. Test and integration evidence

Environment: Windows, Python 3.12.14, Django 5.2.18, SQLite, local filesystem, Asia/Kolkata. Current source gate: **159 tests passed in 53.632 seconds**. Baseline before audit: **143 tests passed in 28.774 seconds**. The original 143 tests remain; 16 added tests cover operational failures, configuration, the frozen rule contract and a complete same-lineage journey. Timing differences are observations, not performance regressions or improvements measured under controlled load.

Commands actually run include:

```powershell
.\.venv\Scripts\python.exe manage.py check --database default
.\.venv\Scripts\python.exe manage.py showmigrations --plan
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate --check
.\Verify-Demo.ps1
```

System checks passed. All four portal migrations are applied; no model drift or pending migrations. Verify-Demo also runs all tests, the bounded evaluation command and fixed-date due-action report. Expected 400/403 test cases log DEBUG diagnostics; this does not mean the suite failed.

Coverage includes required fields, invalid amounts/dates, missing FDR attachments, wrong extensions/MIME, invalid/truncated/oversized files, stored-file absence/permission failure, conflicting declared/document amounts through manual observations, blocking acceptance, explicit resolution, audit preservation, unauthorized/cross-institution/ambiguous/self-role actions, CSRF, stale requests, competing lineage/release actions, database constraints, rollback and evidence cleanup, output escaping and CSV formula protection. These are form HTTP endpoints, not a public JSON API. No external API, OCR or AI backend exists to test.

Fresh real HTTP runs passed all five existing smoke journeys using cookies, login, CSRF and actual uploads/downloads. Initial seeded scope/CSV checks passed 24 role/category comparisons and all 18 distinct PDF downloads. Initial visible counts: institution_a 16, institution_b 1, Officer 16, Authority 16. The five journey runs then added their own 16 synthetic instruments in the isolated database, leaving 33 total and 37 PDFs. They did not touch the original development records.

The original seven portal tables were compared row-for-row with the pre-audit SQLite backup and were unchanged. Authentication sessions/last-login metadata may change during read-only HTTP verification; no claim is made that the whole SQLite byte stream remains constant while serving requests.

After restoration into a new package folder, Verify-Demo.ps1 also completed successfully using the packaged tests and evaluation files. All five saved HTTP journeys passed again after restart/recovery, followed by another 24 scoped CSV comparisons. The original development database independently passed all five read-only restart checks and its 24 CSV comparisons against the restarted audited source. These are verified local results, not deployment or browser-visual claims.

Known testing gaps: visual/accessibility/responsive browser QA, real encrypted/scanned/malformed PDF corpus testing, independent ground-truth adjudication, browser-driven automation, sustained load/concurrent-writer stress, power-loss recovery and production infrastructure failures. The test client and urllib HTTP suites are not visual/browser verification.

## 4. Measured evaluation

Dataset and raw results: `evaluation/cases.json`, `results-before.json`, `results-after.json`. SHA-256: `30897f7f0f5dabd07d51d521047d0dba60670326544ba95e3b38d0988b81521a`. All data is generated synthetic metadata or locally generated fixture content; no third-party corpus, confidential records or real bank instruments were used.

Expected labels were manually reviewed by the implementation author against the explicit two-rule contract. They are not outputs generated by the implementation and are not independently certified by AICTE/bank experts. The set represents MVP boundary conditions, not the distribution of real applicant documents. It was reused after defect correction, so no held-out generalization claim is supported.

| Rule / run | TP | FP | FN | TN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| Missing FDR metadata, before and after | 5 | 0 | 0 | 19 | 100% | 100% |
| Possible duplicate, technical-v1 | 9 | 0 | 4 | 11 | 100% | 69.23% |
| Possible duplicate, technical-v2 | 13 | 0 | 0 | 11 | 100% | 100% |

The metadata rule input uses synthetic Document rows; it does not parse file contents or test file existence. Uploads are evaluated separately using actual bytes: **10/10 cases match the existing envelope policy**. That includes a deliberately unreadable PDF-shaped body which the policy accepts. Empty/plain-text/truncated bytes are rejected. Thus a policy pass is not a readability, safety or authenticity pass.

Technical-v2's recorded post-fix rule timing: median **0.6722 ms**, range **0.6408–1.1187 ms**, n=24. A later full-gate rerun measured median 0.7479 ms. These timings cover only two metadata checks against small in-memory SQLite fixtures; setup, ingestion, PDF viewing, human scrutiny and network time are excluded. Fresh localhost CSV HTTP checks measured median **10.51 ms**, range **8.32–34.30 ms**, n=24. Neither is a load test.

Extraction precision/recall, OCR quality, automated conflicting-value detection accuracy, regulatory-validation accuracy, bank-authentication accuracy and manual-review accuracy are **not applicable/not measured**, because those automated systems are not implemented. Manual processing-time savings and turnaround improvements were not measured. No impact percentage is claimed.

Reproduce: `.\.venv\Scripts\python.exe scripts\evaluate_release.py --output data\release-evaluation.json`. It uses an isolated in-memory database and exits nonzero on a contract mismatch; it never evaluates against or resets the demo database.

## 5. Security findings and real versus simulated functionality

| Area | Verified control | Remaining risk / release implication |
|---|---|---|
| Authentication and authorization | Django password/session auth; fail-closed roles; institution scope; staff private-draft exclusion; protected files; self-review/decision restrictions; CSRF and POST-only mutations tested | No login throttling/MFA/account lifecycle. Demo seed originally uses one generated password for the original three accounts. Individual passwords and access governance required for shared/real deployment. |
| Uploads | Extension/MIME/size/header/trailer checks; generated storage names; attachment/nosniff; no direct media route | Marker checks accept unreadable PDF bodies; no malware scanning, parsing sandbox, encrypted-file handling or request-body proxy limits. Do not accept real/untrusted documents under this security model. |
| Sensitive data and secrets | Runtime scope checks, no-store responses, local credential files excluded from source/ZIP, no real applicant data used | SQLite/files/backups/credentials are plaintext with inherited filesystem permissions; no verified encryption/ACL/retention scheme. DEBUG and fallback key are for isolated synthetic localhost use only. |
| Errors and logs | Known view-level DB/storage failures return generic 503; regression test confirms exception-message redaction; no submitted document content logged by application code | Unexpected DEBUG errors and Django access/error logs can expose diagnostic/context information. No centralized redaction/retention/monitoring policy. Keep localhost-only. |
| Injection/output | ORM usage; no inspected raw SQL, csrf_exempt, mark_safe or template safe override in runtime; HTML escaping and CSV formula-text tests | This is a scoped code review, not a penetration test. Downloaded PDFs are still opened by a separate viewer. |
| Prompt injection / unsupported AI findings | No LLM/OCR/tools pipeline exists; uploaded text is not executed as instructions; explicit bank-unverified UI and human decisions | Prompt injection is not applicable to this implementation. Do not present manual findings or metadata checks as AI extraction or authorized-source confirmation. |
| Audit and consistency | Supported views preserve prior documents/observations/history; optimistic versions/constraints/transactions; failure rollback tested | Direct DB access can modify history. File/DB commit is not crash-atomic; orphan/corrupt files require operator investigation. Hashes do not prove bank authenticity. |
| Dependencies/supply chain | pip-audit **2.10.1** queried public advisories: zero known advisories for asgiref 3.12.1, Django 5.2.18, sqlparse 0.6.0, tzdata 2026.5, and bootstrap pip 26.2.1 | Point-in-time advisory result only; excludes OS/browser/interpreter assessment. Requirements have version pins, not trusted upstream hash pins. Package hashes detect corruption, not malicious-source authenticity. |

Raw application and bootstrap advisory results are in `evaluation/dependencies*.json`. The tool was run in an isolated uv tool environment; it did not add application dependencies. [Django's official 5.2.18 release notes](https://docs.djangoproject.com/en/6.0/releases/5.2.18/) document that patch's security fixes; an advisory audit does not guarantee future safety.

Real functionality: database workflows, authentication/authorization, PDF byte storage/retrieval, metadata rules, manually entered evidence links, human review, dashboards, lineage, release records, exports and local packaging. Synthetic functionality: sample institutions/accounts/instruments, fixture PDFs, fixed demo dates and prepared review/release histories. No simulated integration reports a successful bank/AICTE connection. Completed release means a human-recorded administrative event with synthetic evidence, not a financial transaction.

## 6. Deployment, health and recovery

No public/cloud deployment was attempted or configured. The appropriate hackathon target is loopback-only development serving with synthetic data. The audited original application was restarted on 127.0.0.1:8000. Separate integration/recovery checks use 127.0.0.1:8003. These are local processes, not production deployments.

`check --deploy` under the actual demo settings reported **six warnings**: HSTS absent, HTTPS redirect absent, local fallback secret, insecure session cookie, insecure CSRF cookie and DEBUG enabled. A separate process with a temporary random secret, DEBUG=false and secure cookies still reported the two HTTPS/HSTS warnings. No actual TLS infrastructure was configured. `runserver` and current static-file settings are not production hosting. Follow the [official deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/) before any shared hosting; upload protections also have the limits described in [Django's security guidance](https://docs.djangoproject.com/en/5.2/topics/security/#user-uploaded-content-security).

Reproducible current-workspace commands:

```powershell
Set-Location -LiteralPath 'C:\Saksham\Code files\SIH3rd'
.\Verify-Demo.ps1
.\Start-Demo.ps1
```

If the existing server is running, stop it with Ctrl+C before starting another on the same port. For a separate seeded demo, extract the new offline ZIP into a new writable folder and run:

```powershell
# On a machine with a registered Python 3.12:
.\Setup-Offline.ps1
# On this machine, where py has no registered runtime, use instead:
.\Setup-Offline.ps1 -Python 'C:\Users\sriva\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
.\Verify-Demo.ps1
.\Start-Demo.ps1 -Port 8003
```

Use exactly one setup invocation. Python 3.12 must already exist on the target. Setup verifies packaged hashes, creates a venv without ensurepip, bootstraps pip from its bundled wheel, installs with --no-index, migrates and generates random credentials locally. Existing accounts/scenarios are not reset. The archive excludes data, uploads, credentials, .env and venv. Current .env.example documents OS variables; merely editing that file does not load them.

No health endpoint was added. Operational checks are `manage.py check --database default`, `migrate --check`, SQLite integrity_check, login-page HTTP 200, local CSS HTTP 200 and authenticated dashboard/CSV checks. Login-page success alone does not prove database readiness. Tests and evaluation use separate/in-memory databases; credentials are never printed by the verification scripts.

Recovery procedure remains: stop serving, back up data/database/documents/credentials together privately, restore into a **new** extraction with no existing data directory, run setup and verify. The release audit stopped its isolated server, copied all data, matched every copied file hash, ran SQLite integrity_check=ok and matched all **37 PDFs** to stored SHA-256 metadata. Restored setup preserved all seven portal tables, both credential files and the scenario manifest. Recovery contains **33 instruments, 37 documents, 2 observations, 6 release requests and 120 audit events**. Original development data was not overwritten. See offline-demo.md for copy commands; session activity can change whole-database hashes after startup.

## 7. Demo and handover checklist

- [x] Synthetic scenarios, locally generated PDFs and private random credentials available through fresh setup.
- [x] Five-minute account/click/explanation script and read-only seeded fallback documented in demo-script.md.
- [x] Implemented architecture, scope boundaries and error behavior documented in architecture.md.
- [x] Setup/run/verify/recovery commands documented; wheel-only installation and idempotent setup exercised.
- [x] Automated tests, real HTTP flows, frozen rule evaluation, advisory results and limitations recorded.
- [ ] Rehearse form readability, scrolling, errors, downloaded PDFs and screen sharing in the actual target browser.
- [ ] Rehearse with the physical network disconnected if the presentation will claim verified disconnected operation.

The browser tool failed to initialize with “failed to write kernel assets … path specified”; no visual verification, screenshots or browser video were produced. Package-index-disabled installation and local stylesheet requests were verified, but they are not a substitute for a physically disconnected target rehearsal.

## 8. Release blockers, priorities and completion gate

**Open sign-off blocker for the hackathon:** target-browser/PDF presentation rehearsal. A physically disconnected rehearsal is also required before claiming that exact test succeeded. These are explicitly unverified, not presumed failures. The automatic gates below do not close them.

**High-priority blockers for real/public use:** DEBUG/local secret/development server; absent TLS/deployment hardening; weak file-envelope trust/no scanning; no login throttling or real account governance; plaintext storage/credentials/backups; no independent domain ground truth or regulatory rules/authorized-source verification; no operational alerting/retention/crash-reconciliation scheme. Do not handle real institutional data or advertise general application/document correctness until the relevant controls and scope are agreed and independently verified.

**Optional improvements after sign-off:** CI/version-control provenance (this workspace has no Git repository), load/concurrency measurements, accessibility automation, normalized database indexing if scale warrants, and improved operator diagnostics without sensitive logging. These are backlog items, not implemented features or prerequisites for another architecture rewrite.

| User completion criterion | Current judgment |
|---|---|
| Core workflow | PASS for the approved FDR lifecycle; not a general application-validation pipeline. |
| Correctness | PASS on the frozen two-rule boundary set; broader document/regulatory correctness not established. |
| Evidence | PASS for document-linked manual findings and rule/value explanations; page correctness is manual. |
| Human oversight | PASS for supported officer/authority workflow; no automatic consequential decision. |
| Reliability | PASS for tested invalid input, conflicts and injected operational errors; crash/cleanup/infrastructure limits remain. |
| Security | Conditional for isolated synthetic localhost only; NO-GO for public/real-data use. |
| Evaluation | PASS for honest bounded measurements; extraction/regulatory metrics remain N/A. |
| Demo | OPEN until target visual/PDF and applicable disconnected rehearsal are recorded. |
| Handover | Automated setup/verification exercised; target operator rehearsal remains part of final sign-off. |

The project can be called finished **as this explicitly scoped hackathon MVP** once the remaining target-demo sign-off passes and the limitations are accepted. It cannot be called a finished production system or an automated AICTE document-verification solution on the evidence available here.
