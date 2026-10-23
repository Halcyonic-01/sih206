# How we built it, step by step, and why

This is a reconstruction from the approved milestone sequence, current implementation and recorded verification. It is not a Git history: no commits/timestamps are invented. Files below refer to current locations; some grew across multiple milestones. Do not replay historical schema work against the current database or regenerate old migrations.

## Step 0 — understand the problem and remove unnecessary scope

**Need:** a demonstrable FDR administration workflow within a short hackathon, without assumed access to government/bank APIs or confidential data.

**Decision:** build one small application with real data persistence, protected document handling and human decisions. Treat lifecycle tracking, bank authentication and regulatory compliance as different claims. Choose deterministic checks where rules are clear; leave document interpretation manual rather than adding an unevaluated LLM.

**Why:** a disconnected set of screens would not prove the journey, and unavailable integrations would make the demo fragile. SQLite, templates and local files let us finish the vertical slice with little infrastructure.

**Artifacts to read now:** [requirements](requirements-and-scope.md), root requirements.txt, config/settings.py, [architecture](../../architecture.md).

## Step 1 — inspect and establish the environment

The initial workspace was empty and not a Git repository. On the original machine the py launcher had no registered runtime; default Python was an unsuitable MSYS 3.10.11. A bundled Python 3.12.14 was used. Normal ensurepip setup failed there, so the original environment used a venv without pip and uv to install the pinned dependencies. These machine-specific workarounds are historical, not requirements for a teammate.

**What exists:** manage.py; config/settings.py/urls.py/asgi.py/wsgi.py; requirements.in/txt; .env.example; .gitignore; local data directory conventions.

**Why:** establish a known Python and dependency set before debugging application behavior. Avoid making another developer copy a nonportable .venv. The later offline setup bootstraps pip from its wheel and does not need that original uv workaround.

**Current equivalent:** follow the root README's GitHub clone and Python 3.12 source setup. Run system checks before proceeding.

## Step 2 — Milestone 1: one working submission-to-decision slice

**Requirement:** an institution can create a record, attach a PDF, submit, receive officer correction/acceptance and see a preserved result.

**Implementation order:**

1. Define Institution, UserProfile, Instrument, Document and AuditEvent.
2. Add initial migration 0001_initial.
3. Implement Django authentication and group/profile scope.
4. Validate reference/bank, positive two-decimal amount and ordered dates in forms.
5. Store generated PDF paths and metadata; permit reads only through scoped downloads.
6. Implement draft/save → submit → request corrections or accept; save old/new values with actor and reason.
7. Add server-rendered register, entry/edit/detail, login and conflict pages plus local CSS.
8. Add idempotent synthetic account seeding and tests before expanding scope.

**Files:** models.py, permissions.py, forms.py, uploads.py, services.py, views.py, urls.py; templates/registration and templates/portal; static/css/app.css; test_submission.py, test_documents.py, test_permissions.py; seed_demo.py; smoke_http.py.

**Why these controls early:** an Institution field from a submitted form is not a trustworthy owner; derive ownership from the session. A missing PDF may be allowed in a draft but cannot pass submission. Review is a separate role. Transactions and versions prevent partial/stale updates. Files must survive correction without being silently replaced.

**Acceptance:** create/upload/submit, correction/resubmission, reasoned acceptance, protected download, cross-institution denial, old/new history and persistence after restart. The live script uses actual cookies, CSRF and HTTP uploads, not a mocked browser success flag.

## Step 3 — Milestone 2: scrutiny with explicit evidence

**Requirement:** deterministic findings and manual observations with page references.

**Implementation order:**

1. Add named missing-document and possible-duplicate checks with code, severity, explanation and values.
2. Add ReviewObservation and 0002_reviewobservation.
3. Require observations to reference a document belonging to that instrument.
4. Allow officer comments, optional positive page, warning/blocking severity and later explicit resolution.
5. Block acceptance while a blocking observation remains unresolved.
6. Snapshot rule version/findings during submissions/decisions; keep GET calculations read-only.

**Files:** validation.py; observation/resolution forms and service/view functions; detail template; test_validation.py, test_observations.py; scrutiny-fdr.pdf; smoke_scrutiny.py; docs/checks.md.

**Why:** the MVP needs explainable flags, not an unexplained AI verdict. Manual findings can honestly cite a source document/page even without OCR. Editing values must not erase a prior objection or pretend someone reviewed the correction.

**Acceptance:** fake cross-record evidence rejected; positive page requirement; blocking acceptance; correction followed by explicit resolution; preserved originals/audit; HTML escaping; self-scrutiny denial. A generated PDF visibly states INR 600000.00 for a manual discrepancy against INR 500000.00.

## Step 4 — Milestone 3: one shared maturity definition

**Requirement:** visibility of upcoming/today/matured instruments, scoped dashboard and due-action report.

**Implementation order:**

1. Put date/category/band logic in deadlines.py rather than duplicating it across views.
2. Define six categories: all, pending, accepted current, approaching, today and matured.
3. Link each dashboard card to the matching scoped register filter.
4. Add explicitly labeled DEBUG-only evaluation dates for repeatable demonstrations.
5. Add a trusted-operator CLI report with no delivery/scheduling side effect.

**Files:** deadlines.py; dashboard/register/report templates and view helpers; due_actions.py; test_deadlines.py, test_dashboard.py; smoke_maturity.py; docs/maturity.md.

**Why:** one instrument must not be counted differently by a card, CSV and command. Thresholds 30/15/7 are demo configuration, not asserted regulatory timelines. Recalculating dates on read avoids a fake background processing system.

**Acceptance:** -1/0/7/15/30/31-day boundaries, timezone/current date, matching card/list counts, institution scope, invalid filter/date errors and identical repeated read-only report output.

## Step 5 — Milestone 4: renewal as lineage, not overwriting

**Requirement:** link a successor instrument and preserve the original.

**Implementation order:**

1. Add predecessor/superseded_at/version-related lineage handling through 0003_instrument_renewal.
2. Create a new successor draft with its own reference, dates and PDF; do not reuse an old upload as new evidence.
3. Keep the parent current through draft, submission and correction.
4. On successor acceptance, atomically supersede the parent and accept the child with both histories preserved.
5. Hide private successor details from staff until submission, even through parent audit snapshots.

**Files:** Instrument lineage validation, RenewalForm, services.save_draft/review, renewal view and detail links; test_renewals.py; smoke_renewals.py; docs/renewals.md.

**Why:** a renewal is a new instrument, not an edit that erases the original. A one-to-one retained successor is a deliberate MVP restriction; cancellation/branches were not added.

**Acceptance:** one successor, no reparenting/cycles/cross-institution links, stale/competing proposal rejection, atomic rollback if acceptance audit fails, historical PDFs intact and only accepted successor in current monitoring.

## Step 6 — Milestone 5: release authorization and completion are different

**Requirement:** institution release request, independent authority decision and evidence-backed completion.

**Implementation order:**

1. Add ReleaseRequest, released_at and Document.Kind through 0004_release_workflow.
2. Add an Authority role separately from Officer, preserving old account credentials.
3. Permit request only for an accepted current record without conflicting renewal/open release.
4. Record authorization or rejection with an independent actor and reason.
5. Keep authorized records monitored until completion with a newly uploaded evidence PDF and explanation.
6. Preserve rejected/completed histories; block stale/replayed/conflicting transitions.

**Files:** releases.py; release forms, queue/panel and endpoints; release-evidence.pdf; test_releases.py; smoke_releases.py; docs/releases.md.

**Why:** authorization must not imply payment, discharge, eligibility or bank settlement. Separating document kinds prevents a completion PDF from satisfying a missing FDR upload. Separate authority responsibilities and self-action checks make consequential decisions explicit.

**Acceptance:** institution/officer cannot decide/complete; requester cannot act on own request after role changes; missing evidence blocks completion; authorization keeps monitoring active; completion excludes it; failed audit rolls back state and removes new evidence.

## Step 7 — Milestone 6: reproducible demo and scoped export

**Requirement:** export only the current authorized view, offline dependencies, synthetic scenarios and final verification.

**Implementation order:**

1. Share register filtering and role scope between HTML and CSV.
2. Format exact INR decimals, CSV quoting and spreadsheet formula-text protection; exclude private storage paths/audit blobs/credentials.
3. Seed 17 synthetic instruments through the real workflow services; record an idempotency manifest without resetting later presenter actions.
4. Package allowlisted source/assets/tests/docs and pinned wheels, excluding local runtime data.
5. Verify fresh install, repeated setup, actual HTTP exports/downloads, rollback cleanup and backup/recovery.

**Files:** exports.py, filtered_register helper, test_exports.py, test_demo_workflow.py; seed_scenarios.py; build_offline_demo.py, setup_offline.py, smoke_exports.py; root PowerShell wrappers and offline documentation.

**Why:** a hackathon demonstration should work without a live API/package index or the creator's credentials. Python remains an explicitly installed prerequisite. A ZIP checksum detects changed bytes; it does not certify the source of a package.

**Acceptance:** earlier tests preserved; 143 tests at M6 completion; correct scope/filter export; 18 seeded PDF downloads; clean ZIP; wheel-only setup; idempotency; recovery checks. Visual QA remained manual.

## Step 8 — release audit: verify the implementation, fix defects

**Need:** distinguish written code from a verified release and avoid unsupported accuracy/security claims.

**What the audit did:**

1. Map the actual implementation to the scoped requirements and expose missing broader capabilities.
2. Re-run the existing 143-test baseline and inspect config/migrations, workflows, permissions and storage.
3. Reproduce unhandled database/storage failures and missing cache headers; add generic operational 503/no-store middleware with rollback/log-redaction tests.
4. Create 24 labeled metadata boundary cases and 10 upload-envelope cases. Measure before fixing anything: four duplicate false negatives.
5. Fix SQLite/Python normalization mismatch using scoped strip/casefold comparison, mark new snapshots technical-v2, retain old snapshots.
6. Make invalid upload limits/timezones fail at startup and test non-DEBUG missing-secret behavior.
7. Join correction, renewal and release on one lineage in an integration test; repeat real HTTP journeys in isolation.
8. Audit pinned dependencies, check deployment warnings, exercise fresh setup and restore, and leave unverified manual gates open.

**Files:** middleware.py, settings.py validation, validation.py normalization/version; test_reliability.py, test_configuration.py, test_evaluation_contract.py, test_complete_journey.py; evaluate_release.py; evaluation/; release-readiness.md; architecture/demo documents.

**Actual recorded result:** 159 tests passed; frozen two-rule cases match labels after correction; known unreadable-body upload limitation remains; six demo deployment warnings; no public deployment; manual visual/disconnected rehearsal unverified. Do not convert this into a claim of real-world extraction or regulatory accuracy.

## Step 9 — live explanation and teammate handover

A separate copy was seeded and used to demonstrate real HTTP corrections, blocked acceptance, resolution, renewal and evidence-backed release. The resulting replay was read-only captured responses, not verified browser video or an extra product feature. The source application was not rewritten for that demonstration.

The present handover preserves the old README, supplies a clean new onboarding README, creates this completed-work folder, and separates an executable testing guide from proposed next work and improvement ideas. GitHub is the current handover path; reviewed source excludes old local databases, passwords and replay servers. The earlier offline package remains a historical/optional capability.

## How to study or rebuild without damaging existing work

Read milestones in order, but run only the current setup/verification commands in a fresh clone. Never delete current migrations to imitate an earlier milestone. To learn a small subsystem, open its model/form/service/view/template/test together, trace one request, and run its test module. Use the [code map](code-map.md) and [testing guide](../testing/README.md) for exact current commands.
