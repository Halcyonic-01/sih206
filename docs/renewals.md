# Milestone 4: renewal lineage

This document covers Milestone 4 renewal behavior, preserved in Milestone 5. Release requests, authority decisions and completion evidence are documented in `releases.md`. Payment execution is not implemented; Milestone 6 CSV and packaging are documented in offline-demo.md.

## Workflow

1. An institution opens an **accepted current** instrument and chooses **Create renewal draft**.
2. The form pre-fills bank and amount for convenience. Enter the successor's own reference/dates and upload its supporting PDF. No predecessor document is copied.
3. Saving creates a separate draft linked to the predecessor. The old instrument remains current and in maturity monitoring.
4. Submit the successor through the existing workflow. Officers can request corrections and record document observations; all Milestone 2 blocking/resolution behavior still applies.
5. Only successful officer acceptance of the successor supersedes the predecessor. Both state changes and their audit events commit in one transaction.
6. Both detail pages show authorized links to the other record. Original documents, values, observations and prior audit events remain available.

A successor can later receive its own successor, producing a linear chain such as A → B → C. After C is accepted, A and B are historical and C is current.

## Schema and invariants

The additive `0003_instrument_renewal` migration adds:

- `Instrument.predecessor`: optional protected one-to-one relation to another instrument. The database prevents two successors of the same predecessor.
- `Instrument.superseded_at`: server-set timestamp recording the lifecycle cutover.
- Database checks preventing self-links and supersession of an instrument that is not accepted.

Review and lifecycle states remain separate. A superseded record keeps review status `ACCEPTED`; the UI explicitly labels it **Superseded**. In Milestone 5, `is_current` means accepted with neither a supersession nor a completed-release timestamp. Pending/approved release requests block renewal while keeping maturity monitoring active.

The application creates links only for new drafts in the same institution. Link fields are absent from ordinary create/edit forms. Existing records cannot be reparented through the service or validated model API. Model validation traverses ancestors to reject cycles and cross-institution chains; the service rechecks lineage/current-predecessor state before submission and acceptance. SQLite does not independently enforce arbitrary multi-node graph constraints against direct database modification. Direct SQL changes remain outside the supported workflow.

There is **one retained proposal per predecessor**, including while it is draft, submitted or awaiting corrections. Continue that proposal instead of opening a competing one. Cancellation, proposal deletion, branching, merging and reparenting are deliberately outside this milestone. No renewal fee, minimum amount, mandatory tenure extension, regulatory eligibility or bank authenticity rule is invented.

## Acceptance and audit

Creating the draft advances the predecessor's optimistic version and records `RENEWAL_STARTED`. Its audit message deliberately does not contain the private draft's reference, ID or documents. An officer may see the generic fact that a proposal was opened, but draft details/downloads/lineage links remain private until submission.

Successor acceptance performs all of the following atomically:

- Validates reviewer permissions, current submitted state, expected successor version, document presence and resolved blocking observations.
- Rechecks that the predecessor still belongs to the same institution and is accepted/current.
- Accepts the successor.
- Marks the predecessor superseded and advances its version.
- Records a predecessor `SUPERSEDED` event with actor, timestamp, reason and accepted successor ID.
- Records the successor acceptance with predecessor ID, checks and observation snapshots.

Any failure rolls back both instruments and both audit writes. Repeated approval is rejected; it cannot change the cutover time or create a second supersession event. Stale draft-creation requests fail, with the one-to-one database constraint providing an additional guard against competing proposals.

Institution users cannot review successors. Officers cannot approve their own successor submission or a renewal of an original submission they created after changing roles. Backend role and institution ownership checks apply to all lineage and document actions.

## Monitoring and history

Current dashboard counts, date filters and `due_actions` now include only accepted records with `superseded_at IS NULL`. While a successor is pending or awaiting correction, the predecessor stays in those views. After acceptance, the predecessor is excluded and the successor is counted once according to its own maturity date.

The **All visible records** register preserves historical records with a Superseded badge. Detail pages retain original declared maturity facts while explaining that the historical instrument is no longer monitored.

`--as-of` and dashboard demo dates calculate maturity relative to a selected date against the **current** administrative state. They do not reconstruct the database's historical lifecycle state before a supersession. Both instruments remain **Not independently bank-verified**; acceptance and renewal are administrative actions, not bank confirmation or release.

## Apply and run

No new dependencies or configuration are needed. A private SQLite backup was taken under ignored `data/backups/` before the migration. Existing instruments get null predecessor/supersession fields; no relationships or historical decisions are inferred.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test portal.tests --verbosity 2
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

With the local server running and generated demo accounts available:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_renewals.py
# Stop and restart the server, then:
.\.venv\Scripts\python.exe scripts/smoke_renewals.py --verify
```

The live scenario adds two new synthetic `RENEWAL-...` instruments. It demonstrates a pending proposal, blocked competitor, correction/resubmission, acceptance, bidirectional lineage, preserved original/successor PDF versions, institution isolation and current dashboard/report behavior. The verify phase reuses the saved scenario without adding records. Fixed-date report checks use the explicitly labeled local demo date 2026-10-23. Existing records are not renewed or edited by this script.

## Acceptance coverage

`portal/tests/test_renewals.py` covers linked drafts, independent documents, pending/correction monitoring, atomic cutover/audit rollback, competing proposals, stale versions, request forgery, unauthorized access, private draft links, self/cross-institution/cyclic lineage, multi-generation chains, replay rejection and dashboard/report exclusion of superseded predecessors. All prior milestone tests remain in the full acceptance suite.

Visual browser QA remains manual. Live HTTP checks do not establish visual correctness or production concurrency readiness.

## Verified results

- All **103 tests passed**, including the original 79 regression tests and 24 renewal tests.
- Django configuration and migration drift checks passed; migration `0003_instrument_renewal` is applied.
- The live renewal scenario passed, as did all three earlier saved-scenario checks.
- All four verification scripts passed after a server restart.
- Existing domain/account values and original PDF hashes matched the pre-update backup; no existing instruments were renewed by the live script.

Two synthetic `RENEWAL-...` instruments remain available for demonstration. The Milestone 5 suite now retains these tests within 134 passing tests. Release interactions are documented in `releases.md`; Milestone 6 CSV and packaging are documented in offline-demo.md.
