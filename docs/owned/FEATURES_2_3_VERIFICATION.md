# Features 2 and 3 — local verification

27 October 2026. Feature 1 remains paused at its offline prototype. No release pre-check API, model migration or review UI was added. No commit, push, PR update or main-branch change was made during this work.

## Implemented

Feature 2 adds a six-item institution deposit-readiness checklist backed by scoped records, typed document metadata, existing obligation calculations, officer receipt records and current issuer evidence. It provides accessible progress, applicable-step counts, due dates, Hindi labels and permitted links to exact existing forms. Unknowns, simulated responses and discrepancies remain visible. See [the guide](../readiness/README.md).

Feature 3 adds personalized role-specific summaries, a protected own-account preview, saved opt-out with version protection, Monday 09:00 IST scheduling with same-week catch-up, frozen weekly outbox rows and existing leased email retries. Before sending, the worker rechecks activation, role, institution/unit scope, email and preference. The launcher and Docker worker check digest dispatch every five minutes, independently of the daily rule stamp. See [the runbook](WEEKLY_DIGEST_PLAN.md).

## Rehearsal

The isolated app is available while its local server remains running at `http://127.0.0.1:8016/`. Its private profile is `tmp.readiness_settings` and its database/media are under ignored `data/readiness-browser/`. It uses the existing synthetic demo credentials; no passwords are included here. Restart it with:

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8016 --settings=tmp.readiness_settings --noreload
```

The profile and its generated data are local rehearsal artifacts, not tracked installation requirements. For a fresh checkout, use the normal README setup and migrations to create your own local synthetic environment.

1. Institution account: **Institutions → your institution → Deposit readiness**. Open an editable deposit's Affidavit-3 upload link or a new-deposit link and check the selected record/category/obligation.
2. Officer account: use the receipt-review link, enter synthetic receipt dates and a reason, save, and observe refreshed readiness.
3. Another institution: the first institution's readiness and receipt details must be unavailable.
4. Open **Notifications → Weekly email digest → Preview my digest**. Toggle the preference, reload and reopen the panel to verify persistence.

The browser tests checked actual HTTP and UI behavior on disposable data: **4/4 passed in 22.3 seconds**. They cover eight-day deadlines, upload-dialog category selection, new-deposit prefill, Hindi and mobile layout, officer receipt saves, foreign-scope denial, digest preview and persisted preference. The upload test opens the correct form; it does not upload or authenticate an affidavit. Screenshots were visually inspected. The notification migration was applied only to this disposable database.

Dry-run preparation on all eight synthetic accounts returned `prepared=8, queued=0, failed=0`. A subsequent rehearsal temporarily enabled dispatch only inside a process using that disposable database and a forced memory email backend: eight weekly rows were queued, all eight were delivered to memory, a repeated dispatch created zero duplicates, and repeated delivery sent zero additional messages. No external emails were sent. Results are in ignored `data/readiness-browser/digest-delivery.json`; the server's normal dispatch flag remains off.

## Verification evidence

- Readiness calculation/API tests: **29 passed** in 18.842 seconds.
- Readiness/records/institution component tests: **24 passed** in 71.84 seconds.
- Digest calculation/integration/sender tests: **58 passed** in 9.215 seconds.
- Notification and launcher regression checkpoint: **101 passed** in 37.234 seconds; later digest hardening is covered by the final 58-test run.
- Launcher scheduling tests: **6 passed** in 0.081 seconds, including dispatch after the daily stamp exists and safe subprocess arguments.
- Final combined feature/notification/launcher tests: **134 passed** in 51.472 seconds, after the last digest hardening.
- Final full frontend suite: **147/147 passed**, 18 files, in 283.17 seconds with `npm test -- --maxWorkers=1`. The earlier parallel run had 146 passes and one existing audit-screen timeout; no test or timeout setting was changed.
- Full backend checkpoint: **809 tests run in 795.620 seconds: 807 passed, one optional OCR skip, one intermittent audit timestamp-test failure**. This is not an entirely green full-suite result. That run began before the final digest test additions; the final 134-test targeted run above covers those changes.
- Unchanged audit-chain suite rerun: **20/20 passed** in 21.722 seconds. A separate local diagnostic confirmed that the fixture's first and fourth events can have identical timestamps on this Windows machine: copying that unchanged value correctly leaves the chain valid. Changing the timestamp by one second was detected. The audit implementation and existing test were not edited. The owner should make that test's timestamp mutation deterministic before relying on a fully green CI run.
- Django check, migration drift check, strict OpenAPI validation, TypeScript/build and Hindi coverage checks passed. Hindi coverage: 575 explicit UI keys and 767 catalog entries. `git diff --check` passed.

Logs live under ignored `data/features23-*`, `data/readiness-*` and `data/digest-focused-final.log`; logs are verification artifacts, not files required to install the application.

## Deliberate boundaries

### Audit timestamp test follow-up

The user subsequently authorized the small audit test fix. `audit/tests/test_chain.py` now changes the event's own timestamp by exactly one second instead of copying another event's potentially identical timestamp. Audit implementation and assertions are unchanged. The complete audit app suite passed **38/38 tests in 51.466 seconds**. Django check and diff whitespace checks passed. The full backend suite was not rerun for this test-only change; its earlier checkpoint above remains the historical result. Feature 1 remains paused and no changes were pushed.

- A full readiness bar is not a compliance certificate. Upload metadata and acceptance for tracking do not authenticate a deposit.
- Existing accepted records cannot upload Affidavit-3/payment-proof categories. The checklist preserves that permission boundary and explains unavailable shortcuts. Changing that policy is separate work.
- Digests are English plain text; the preference/preview UI supports Hindi labels. No email-verification subsystem is invented.
- PGRC escalation and auditor incident counts remain unavailable until canonical sources exist. Authority metrics use existing human-review action gates.
- `WEEKLY_DIGEST_ENABLED` is off by default. Real SMTP delivery and a deployed scheduler have not been verified. The bundled loop must be running for automatic dispatch; stopping the app stops that local scheduler.
- Docker scheduler wiring was inspected and edited; no Docker image build or deployed-container test was performed in this session.
- Per-source bounds return unavailable or safe failures; no production-scale performance claim is made. SMTP does not guarantee exactly-once delivery across a crash after provider acceptance.
- No normal database, `.env`, credential, Feature 1 source or remote branch was changed. The new preference migration must be applied to a chosen deployment database before enabling that feature there.
