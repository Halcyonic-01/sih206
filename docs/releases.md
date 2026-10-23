# Milestone 5: release requests, authority decisions and completion evidence

This document describes the preserved Milestone 5 workflow. Milestone 6 CSV, offline packaging and final verification are documented in offline-demo.md.

## State and trust boundaries

```text
Institution requests → PENDING → Authority rejects → REJECTED
                             → Authority authorizes → APPROVED
                                                        ↓ new evidence PDF + explanation
                                                    COMPLETED
```

Approval means **release authorized; completion pending**. It does not set the instrument's `released_at`, stop maturity monitoring, discharge an FDR, confirm bank authenticity or execute a payment. A separate completion action records a human-reviewed PDF and explanation, and only then removes the instrument from current monitoring.

Completion is a portal record based on uploaded evidence, not an independently confirmed bank settlement. The timestamp is when the authority recorded completion, not an inferred bank transaction date. Every instrument continues to say **Not independently bank-verified**. Eligibility under applicable regulations must be assessed by the competent authority; this prototype contains no invented regulatory eligibility rules.

## Roles

| Role | Release permissions |
|---|---|
| Institution | Request release of its own accepted current instrument; read its request/decision/evidence history |
| Officer | Read submitted records and release histories; no release decision or completion permission |
| Authority | Read submitted/accepted records, approve/reject with reasons, record completion with new PDF evidence |

Authority is a separate Django group. Multiple recognized portal roles fail closed. An authority cannot act as an institution or scrutiny officer, and cannot decide or complete a request they submitted before a role change. The same independent authority may authorize and later record completion; a second authority approver is not invented as an MVP requirement.

Unsubmitted institution drafts remain private from officers and authorities. All release endpoints apply role and instrument ownership checks on the backend. Evidence downloads use the existing protected download route and no-store/attachment headers.

## Requests and decisions

- Release can be requested only for an accepted current instrument: neither superseded nor previously completed release.
- A nonblank reason is required. Supporting eligibility review is human work, not an automatic determination.
- At most one pending/authorized request can exist per instrument, enforced by service checks and a database constraint.
- Authority decisions require a reason and a current expected instrument version.
- Rejection preserves the instrument as current. It does not overwrite or delete the request.
- A new request may be submitted after rejection; it gets a separate ID/history. There is no reopening or rewriting an earlier decision.
- Decisions cannot be replayed or changed after leaving pending status.

## Evidence-backed completion

Only an authorized request can be completed, by an independent Authority account. Completion requires a nonblank explanation and a **new PDF upload**. A client-supplied existing document ID cannot substitute for evidence.

The evidence is stored as `Document.Kind.RELEASE_EVIDENCE`, linked to this instrument/request with uploader, size, SHA-256 and server timestamp. Existing documents are migrated as `FDR` and remain unchanged. Evidence does not satisfy FDR submission checks or silently replace the original financial document.

The existing bounded PDF checks are shared through `portal/uploads.py`: extension, declared MIME, PDF header/trailer and size. These are not malware scanning, page counting or authenticity verification. The evidence must be inspected manually; use synthetic files in the prototype.

Completion atomically updates the release request, instrument `released_at`, evidence metadata and audit event. A known failure rolls back database state and removes a newly stored file. A process crash during file writing may still leave an orphan file, as with the existing prototype upload design.

No completion overwrite/delete endpoint exists. Repeated actions fail without altering the original evidence, completion timestamp or audit history.

## Renewal and monitoring interaction

Pending and approved requests leave the instrument in current maturity monitoring but block new renewal proposals. An existing successor proposal also blocks a release request, preventing a release from stranding a pending renewal. Finish the supported renewal or obtain rejection of a release request as appropriate; cancellation/reopening is outside this scope.

These conditions are rechecked in services, not only in the UI. Successor acceptance rechecks the predecessor's current state and absence of an active release request. Instrument version checks serialize workflow mutations alongside the existing one-to-one renewal and one-open-release constraints. This single-instance SQLite prototype is not claimed to be load-validated for production concurrency.

After completion, accepted-current dashboard cards, maturity lists and `due_actions` exclude the instrument. All visible records, protected original/evidence documents, lineage and audit history remain available. Demo evaluation dates calculate maturity against current administrative state; they do not reconstruct historical state before completion.

## Run and account setup

No new dependencies or environment variables are needed. A private pre-update SQLite backup is under ignored `data/backups/`. Apply the additive migration:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

Existing institution/officer accounts and passwords are preserved. The default seed command still provisions the original three accounts. Add only the Authority account explicitly:

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo --authority-only --generate-password
```

In local DEBUG mode this saves a random password for `authority` in ignored `data/authority-credentials.txt`, without printing it or modifying `data/demo-credentials.txt`. To choose the new account's password interactively, omit `--generate-password`. Existing accounts/passwords are never reset and existing credentials files are never overwritten.

Start the local server and open `/releases/` through the Release requests navigation link:

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Authority/Officer queues default to pending requests. Institution queues default to all their requests. Use the status filter to find approved requests awaiting completion, rejections, or completed cases. Authority decisions and completion actions are on the instrument detail page.

## Verification

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test portal.tests --verbosity 2
```

`portal/tests/test_releases.py` covers request/decision/completion states, role separation, requester self-approval denial, one-open-request constraints, evidence validation and protection, stale/replayed requests, read-only queues, preservation of original FDRs, audit rollback/file cleanup, authority-only seeding, renewal conflicts and monitoring cutover. All Milestone 1–4 tests remain in the suite.

For live HTTP acceptance checks with the server and generated demo credentials:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_releases.py
# Restart the server, then:
.\.venv\Scripts\python.exe scripts/smoke_releases.py --verify
```

This adds two new synthetic `RELEASE-...` instruments, one completed with evidence and one rejected. It verifies approval does not stop monitoring, missing evidence blocks completion, institution/officer decision attempts fail, completion preserves original PDFs, rejected records remain current, and cross-institution evidence access fails. The verify phase reuses the saved scenario without creating new records. `fixtures/release-evidence.pdf` is marked synthetic; it is not bank-issued evidence.

Visual browser QA remains manual. Live HTTP checks do not establish visual correctness, bank confirmation or production readiness.

## Verified results

- All **134 tests passed**, including the original 103 regression tests and 31 release tests.
- Django checks and migration drift checks passed; `0004_release_workflow` is applied.
- The live approval/rejection/completion scenario passed, along with all four preserved scenario checks.
- All five saved scenarios passed after a server restart.
- Existing domain rows, observations, lineage, audit history, account credentials/roles and original PDF hashes matched the pre-update backup. The Authority account was added separately without changing earlier credentials.

Two new synthetic `RELEASE-...` instruments remain: one completed with evidence and one rejected. No existing instrument was released by the check. Milestone 6 CSV and packaging are documented in offline-demo.md.
