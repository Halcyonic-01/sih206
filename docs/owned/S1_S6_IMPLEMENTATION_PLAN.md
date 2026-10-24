# Saksham S1–S6: remaining implementation and integration plan

Prepared 25 October 2026 against merged commit `e789c30`.
Status: **plan only; no implementation authorized or performed by this document**.

## Objective and boundaries

Finish the existing institution → obligation → reporting → release journey in
the merged application. Reuse the delivered services, calculations, fixtures and
components. Do not rebuild the architecture or treat merged code as integrated.

Saksham owns the feature adapters, endpoints, screens and tests described below.
Kushagra owns shared API/auth/client/shell, access, notification infrastructure,
scheduler, CI and launch/packaging. Yash owns instruments, documents, parsing and
verification. Consume their published interfaces; do not implement their tasks.

Keep all work local until Saksham separately authorizes a push/PR. Use a new local
feature branch from the inspected merged baseline when implementation starts;
preserve the existing S1–S6 branch and untracked verification report. Never work
directly on main, rewrite applied migrations or reset existing work.

Read AGENTS.md and the private planning PDFs before implementation. Check the
current review/freeze stage: integration defects and verification are the focus;
this plan does not authorize new features after the freeze. S7, AI, signatures,
bank connections, new payment flows and unrelated improvements are excluded.

## Verified starting point

- Models, pure calculations, persisted release services, CSV imports, partial
  reports/KPIs and React components exist.
- K1/K2/K4/K5 infrastructure is present; our code must now consume it.
- Y1's Instrument.obligation field/migration and Y2–Y6 document/verification
  surfaces are absent in this checkout. Reinspect before each dependent slice.
- Normal institution/release/KPI URLs resolve to NotFoundView. The platform loads
  `obligations.api_urls` and `casework.api_urls`, while we supplied a harness using
  `obligations.api.urls`.
- No owned frontend route module is registered. Strict compilation fails in
  `features/saksham/client.ts`; its old isolated checker also fails under ESM.
- Full backend: 529/530 passed; portal: 159/159 passed. Frontend: 23/27 passed,
  four repeatable audit-screen timeouts; build/type-check fail. Synthetic S2–S6
  gates all pass. See [actual check report](MERGED_CHECKS_2026-10-25.md).

The red baseline is known. Do not silently fix teammate tests, weaken compiler
checks, relax timeouts, skip tests or alter fixture labels. Record and report
external failures separately. Full release sign-off requires their resolution.

## Delivery order

| Package | Task coverage | Outcome | Prerequisite |
|---|---|---|---|
| P0 | All | Baseline, ownership and contract decisions recorded | Existing checkout |
| P1 | S3/S6 | Owned code compiles and tests under the shared frontend | P0 |
| P2 | S2 + S1 reads | Institution API uses the real platform conventions | P0 |
| P3 | S3 | Smallest browser slice: login → institution → obligation/calculator | P1, P2 |
| P4 | S1/S2 | Actual linked holdings, receipts and findings | Y1–Y3 + P2 |
| P5 | S4 | Integrated import/reports/KPIs, with complete or explicit partial sources | P2, P3; Y3/Y6 for complete sources |
| P6 | S5 | Release APIs/storage/permissions/audit aligned | P0, P2; storage decisions |
| P7 | S5 | Real fact/document gates, notifications and lifecycle verified | P4, P6; Y2/Y3 + canonical policy/template |
| P8 | S6 | Complete release journey mounted and browser-tested | P1, P7; Y4 document capabilities |
| P9 | All | Reproducible synthetic demo and release acceptance | P3–P8 + owner fixes/packaging |

Execute one package at a time and report its acceptance evidence before advancing.
If P4 is blocked, continue available P5/P6 work; do not build Yash's missing sources.
Within a package, commit only a coherent tested slice when authorized; a local
checkpoint is not permission to push or mark a task complete.

## P0 — Establish the integration baseline and decisions

Work:

1. Preserve working changes, record HEAD and inspect current merged interfaces.
2. Reproduce relevant failures before fixes and retain logs in ignored data/.
3. Turn C01–C11 and S5-D01–D09 into a decision register with owner, proposal,
   accepted evidence, affected files and blocked acceptance tests.
4. Confirm URL/slash, money encoding, master permissions, pagination, source
   completeness, version ownership and public field contracts. Existing shared
   conventions take precedence over our provisional ones where compatible.
5. Report shared setup gaps: requirements.txt/CI/launcher omit optional owned
   dependencies; audit test timeouts and Windows credential-permission assertion
   need Kushagra's review. Do not edit those files.

Files: update owned CONTRACTS.md and this plan as decisions become real; read
docs/api-conventions.md, frontend/README.md and docs/scheduled-rules.md.

Acceptance: each open item is either backed by an existing published interface or
explicitly blocked on a named decision. No invented policy or assumed approval.

## P1 — Repair owned frontend compilation and test integration

Files to edit/create:

- `frontend/src/features/saksham/client.ts`
- Owned `client.test.ts` and component `*.test.tsx` files beside the features
- Owned `verify.py`, tests.cjs and README.md only as needed for migration

Responsibilities:

- Narrow parsed whole/fraction values correctly under noUncheckedIndexedAccess;
  retain exact paise arithmetic and reject malformed/unsafe inputs.
- Move the 11 existing isolated assertions into K2/K3's Vitest/testing-library
  setup, or retain a compatible owned wrapper. Do not create another package/app.
- Preserve tests for identity races, unknown values, no fake data fallback,
  permission-controlled actions, public allowlisting and saved-state reload.
- Remove obsolete execution instructions only after equivalent assertions pass;
  do not silently delete behavioral coverage.

Acceptance: shared `npm run typecheck` and `npm run build` pass. All owned tests
pass in the shared runner. Existing unrelated audit timeouts remain reported if
not owner-resolved; no claim that the complete suite is green.

## P2 — Integrate the institution/obligation API foundation

Files:

- Create `obligations/api_urls.py`, an owned platform extension
- Edit `obligations/api/views.py`, report_views.py and existing URL organization
- Edit `obligations/services.py`; add owned API serializers/schema annotations
  only where they reduce duplication or document the actual contract
- Add `obligations/tests/test_platform_api.py`

Responsibilities:

- Register institution/approval/obligation/calculator/rules endpoints through the
  existing discovery hook without changing portal/api/urls.py or config/urls.py.
- Reuse K1 session authentication, CSRF, shared errors and StandardPagination.
  Stop overriding these with the old provisional envelope/403 login behavior.
- Preserve reason/version/audit/transaction guards and unknown-state semantics.
- Define master read/write permissions explicitly, including auditor/clearance
  access. Add access logging to applicable staff searches/reports/downloads using
  K4 helpers; do not invent geographic restrictions absent from the shared model.
- Include accurate request/response schemas; preserve required integer paise
  semantics and agree lossless large legacy-value encoding.

Acceptance tests against **default config.urls**, not only the harness:

1. Institution A sees only A; foreign and missing IDs both return generic 404.
2. Signed-out read returns 401; wrong-role mutation 403; missing CSRF rejects a
   session write; invalid input 400; stale write 409; database failure safe 503.
3. Allowed officer mutation requires reason/current version and writes audit in
   the same transaction; failed audit leaves no partial change.
4. Lists contain count/page/page_size/total_pages/results; schema includes routes.
5. An obligation with no holding source reports unavailable, never zero coverage.

## P3 — First complete browser slice (S3)

Files:

- Create `frontend/src/features/saksham/routes.tsx`
- Create owned page wrappers and `platformTransport.ts` alongside existing code
- Edit institutions.tsx, shared.tsx and owned component tests as required

Responsibilities:

- Register institutions/list/detail/calculator routes using K2's feature registry.
  Adapt existing shared get/post/patch/upload/download helpers; no direct fetch,
  replacement auth provider, token storage, shared-router or AppShell changes.
- Derive identity invalidation from actual auth/session events. If same-user
  re-login cannot be detected through existing hooks, raise that precise contract
  issue; do not fabricate a stable identity key.
- Supply route params, navigation, current versions, error states and protected
  download behavior. Add actual coverage/timeline/open-action presentation required
  by S3; label unavailable facts and suggested actions accurately.
- Integrate visual components into the existing shell/theme without a redesign.

Acceptance: sign in → institutions → own profile/programmes/obligation → calculator
works in a target browser. A labeled calculation matches the API. A failed source
shows unavailable. Direct route reload works; wrong institution is hidden; old
identity responses are discarded. Verify loading/empty/400/401/403/404/409/503,
keyboard focus and 360px/desktop layout.

This slice may pass before Y1 arrives; real holdings coverage is a separate P4 gate.

## P4 — Finish S1/S2 source and rule integration

Dependencies: actual Y1 relationship plus Y2/Y3 complete scoped document metadata;
reviewed policy decisions where calculations depend on interpretation.

Files:

- `obligations/services.py` and a new owned source-adapter module
- catalogue.py, rule seeding and policy docs only for reviewed changes
- Owned model/adapter/migration integration tests; no edits to Yash's migration

Responsibilities:

- Verify FK target, null legacy behavior, obligation identity and upgrade order.
  No inferred legacy association or redesign of already-applied S1 tables.
- Assemble complete holdings/receipt snapshots from actual source fields. Prevent
  double counting superseded/released holdings and foreign evidence.
- Separate missing integration, incomplete data and known absence. Receipt dates
  must have reviewed semantics; arbitrary uploads are not proof receipts.
- Reconcile seeded `escalation-matrix` schema with K6. Agree how obligation status
  updates and proof reminders interact; do not silently mutate status on reads or
  invent a competing scheduler.
- Resolve applicable rule edition, exemptions, conversion offsets, tenure multiplier,
  term start/leap days, rounding/penalty stacking and cross-year interpretation.
  Until reviewed, keep draft labels and unsupported cases blocked.

Acceptance: fresh and upgrade databases preserve legacy data; actual linked
synthetic holdings reproduce required/held/shortfall/term/proof labels. Test renewal
lineage, released holdings, unknown dates, duplicate/foreign links and source failure.
Existing 76 S2 cases still pass; K6 can read the owned rule seed with agreed shape.

## P5 — Complete S4 imports, reports and KPI integration

Files:

- `obligations/imports.py`, reports.py, kpis.py and api/report_views.py
- Owned report/source adapter module and platform integration tests
- Existing reports.tsx plus route/page wrappers
- Create `obligations/management/commands/seed_review_obligations.py`

Responsibilities:

- Mount CSV preview/commit, report downloads and KPI routes/screens with shared
  auth, error, pagination and access logging.
- Preserve expiring actor-bound previews, context/hash freshness, atomic commit,
  audit and replay protection. Agree preview retention/cleanup with platform owner;
  no automatic destructive cleanup of existing previews during this work.
- Finish report membership using actual Y3/Y6 typed-document/verification data,
  obligations and agreed SLA rules: pending verifications, upcoming maturities,
  missing documents, intervention, released register.
- Keep source limitations visible until each adapter is complete. Confirm cohort
  denominators, time boundaries, incomplete histories and renewal eligibility for
  turnaround, correction cycles, confirmation and renewal KPIs.
- Seed idempotent synthetic institutions/obligations through reviewed services;
  invoke only via the existing seed_review hook.

Acceptance:

- Preview is labeled SIMULATED and does not create institutions; valid commit
  creates all intended rows once; replay, expiry, stale context or injected failure
  leaves no partial rows. Cross-actor preview access is denied.
- Each of five reports matches labeled real-model snapshots and cannot expose
  another institution's data. XLSX strings resist formula injection; paise remain
  exact. Measure a bounded synthetic export without claiming production scale.
- KPI results match verified event cohorts; unavailable confirmation history is
  not zero. CSV 7/7 and KPI 10/10 gates remain green; scenario 9 browser pass logged.

## P6 — Align S5 storage, API, scope and audit

Files:

- Create `casework/api_urls.py`; update casework/api.py and services.py
- Owned adapter modules and obligations/tests release integration tests
- Model changes/migrations **only if explicitly agreed and necessary**

Responsibilities:

- Register owned release routes through the shared loader, with shared auth/errors
  and accurate schemas. Keep legacy unextended requests and renewals working.
- Agree the current ReleaseCase → ReleaseRequest extension and registration of
  case models under obligations. Document migration dependencies; never relocate
  tables or allocate a reserved portal number opportunistically.
- Wire K4 unit assignment/require_clearance to own-task access. Recheck requester,
  clearance-decision-maker and authority independence on the server.
- Agree entity MasterAudit visibility/integrity with the instrument-centric
  platform audit contract. Do not attach master events to a fake instrument.
- Access-log protected letter/evidence reads and searches through K4's helper.
- Coordinate the scheduler model/path mismatch with Kushagra. Provide an agreed
  owned adapter if sufficient; do not create a duplicate ClearanceTask model or
  edit notifications/rules.py unilaterally.

Acceptance: default-route API tests cover allowed/denied/invalid/stale for every
write. Unassigned/wrong-unit accounts are denied; foreign cases are 404. Replays
cannot duplicate active cases/tasks. Legacy direct actions cannot bypass gates;
old unextended requests retain behavior. Audit/access records survive rollback
correctly; scheduler can discover actual open tasks under the agreed contract.

## P7 — Finish S5 facts, decisions, notifications and evidence

Dependencies: P4/P6, Y2/Y3 parsing/metadata, reviewed source/template policy.

Files:

- Create owned `casework/facts.py` and integration adapters as appropriate
- Edit services.py, api.py, letters.py only for verified feature gaps
- Add source-freshness/failure/API tests in obligations/tests
- Create `obligations/management/commands/seed_review_release.py` once legitimate
  synthetic document facts can be assembled through actual source interfaces

Responsibilities:

- Implement the Saksham-owned facts assembler using actual complete metadata,
  reviewed holds/basis, scoped links and immutable source revisions. Fixture ports
  remain test-only; browser assertions never prove document validity.
- Obtain canonical Affidavit-6 text/version, exact eleven questions and answer/
  contradiction policy from the authorized human source. Missing template blocks.
- Map five release paths and FDR/RTGS/RPGF prerequisites to actual typed documents;
  verify parse/page/evidence references through Y2/Y3. Reject foreign, substituted,
  unreadable or stale evidence. Agree when changed facts invalidate clearances.
- Connect K5 notify via recipient helpers and valid catalog/template contract,
  inside the same database transaction with stable idempotency keys. Do not add
  shared templates yourself or claim queued email was delivered.
- Keep penalties proposed until authorized human confirmation. Implement waiver
  only if required powers/reasons/independence are agreed; otherwise it is a
  recorded requirement blocker. Confirmed is not paid and no settlement is inferred.
- Revalidate versions/rules/sources at decision, issuance and completion. Keep
  approval separate from completion; completion needs new parsed evidence, notes
  and the applicable refund reference.
- Preserve unsigned synthetic letters, private storage, token hashing, minimal
  public fields, explicit revocation and rollback/file cleanup.

Acceptance: test all five paths and three modes where supported with explicit
prerequisites, plus blocking holds, missing/malformed metadata, partial clearances,
proposed penalties, wrong actors and stale sources. Exercise request → clearance →
review → approval/rejection → issue → completion through normal APIs. Approval
keeps monitoring; only valid completion stops it. Generation/parser/storage/DB/
outbox failures must not leave partial financial state, duplicate letters or lost
evidence. Notifications queue once; public lookup reveals only approved fields.
The 40 S5 labels remain unchanged unless separately reviewed policy requires a
versioned new corpus; never relabel to conceal a defect.

## P8 — Complete S6 screen and evidence integration

Files:

- Owned routes/page wrappers, releases.tsx and shared transport adapters
- Owned wizard/case/queue/public `*.test.tsx` and browser acceptance specifications

Responsibilities:

- Mount protected release wizard/case/clearance queue and public verify route.
- Inject actual questionnaire/template and Y4 typed uploader/viewer. Path or
  instrument/source version changes invalidate prior document readiness.
- Render server actions, saved status, independent readiness and protected
  page-linked evidence. Require reasons/current versions; disable pending writes.
- After 409 or ambiguous 503, reload saved state without automatically replaying
  a consequential action. Handle logout/session/scope changes without stale data.
- Show queue units and public issued/revoked/not-found/unavailable states correctly.

Acceptance: actual browser journey with institution, three clearance accounts and
independent authority reaches evidence-backed completion; also rehearse rejection,
hold, wrong unit, stale tab and revocation. Direct routes/reloads work. Inspect
protected PDFs and page links, missing viewer/parse failure, keyboard focus and
mobile layout. Re-run all 53 S6 fixtures and equivalent mounted component tests;
unmounted or fixture-only UI does not satisfy scenario 7.

## P9 — Final integration and release verification

Files: owned integration/browser tests, seed hooks, docs/owned, demo/setup notes.
Coordinate shared CI/dependency/package changes with K3; do not edit them yourself.

Work:

1. Test against a fresh isolated database and a backed-up existing database, with
   synthetic documents and original account/data preservation checks.
2. Run commands below and preserve exact results; distinguish known external
   failures from new failures. Release requires all critical failures resolved.
3. Verify PS scenarios 3, 7 and 9 on the normal API/router and real integrated
   synthetic metadata, not fake trusted source ports.
4. Verify audit/backfill expectations, public-token disclosure/log behavior,
   export/upload/access controls and actual notification outbox state.
5. Confirm K3 includes optional dependencies, casework and new frontend assets;
   rehearse cold startup with network disconnected, private PDF viewing, exports
   and public verification. No network or fake-bank dependency may be hidden.
6. Update README, architecture/contracts, demo script, limitations and a task-by-
   task completion matrix. Document recovery and offline fallback actually tested.

Acceptance: fresh setup instructions work; normal browser journeys pass; original
regressions remain green; all critical access/evidence/state tests pass. Missing
policy, external owner defects, unverified browser behavior or packaging failures
remain blockers, never papered over by successful synthetic unit tests.

## Test commands

PowerShell from repository root, with the already-installed merged dependencies:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test obligations.tests --noinput
.\.venv\Scripts\python.exe manage.py test portal.tests --noinput
.\.venv\Scripts\python.exe manage.py test --noinput
.\.venv\Scripts\python.exe manage.py spectacular --validate --fail-on-warn --file data/s1-s6-schema.yml
.\.venv\Scripts\python.exe -m evaluation.s2.run --output data/s2-current-results.json
.\.venv\Scripts\python.exe docs/s3/validate_fixtures.py
.\.venv\Scripts\python.exe -m evaluation.s4.run
.\.venv\Scripts\python.exe -m evaluation.s4.kpis.run
.\.venv\Scripts\python.exe -m evaluation.s5.run
.\.venv\Scripts\python.exe docs/s6/validate_fixtures.py
```

From frontend/, use `npm.cmd run typecheck`, `npm.cmd test` and
`npm.cmd run build`. Run focused owned Vitest files after each relevant edit,
then the complete suite at integration gates. Use the team's agreed browser runner
if available; otherwise record exact manual steps/results instead of inventing a
Playwright setup or claiming automated browser coverage.

## Required inputs and owner handoffs

| Needed input | Owner | Blocks |
|---|---|---|
| Y1 FK/mode/holding metadata and migration | Yash | P4 and complete P7 |
| Parsed typed documents, versions, dates, page counts and evidence/upload APIs | Yash | Proof checks, complete reports, P7/P8 |
| Verification/discrepancy and cohort events | Yash | Complete P5 reports/KPIs |
| Shared credential/audit test fixes and dependency/CI/packaging consolidation | Kushagra | Fully green baseline and P9 |
| Notification template/recipient and clearance scheduler compatibility decisions | Kushagra + Saksham | P6/P7 scheduler/outbox integration |
| Storage/entity-audit/publication/version agreements | Relevant team owners | P6 and consequential release operations |
| Canonical Affidavit-6 and policy interpretation/waiver authority | Authorized human/policy source | Complete P4/P7/P8 |

Request precise missing interfaces or decisions, not a blanket request that a
teammate finish Saksham's feature. Do not contact them automatically.

## Completion rule

A package is complete only when its code is integrated, meaningful tests pass,
manual checks are recorded where needed, and no requirement is silently replaced
with unavailable or synthetic runtime facts. Keep separate statuses for built,
integrated, tested and blocked. Finish P1 first; do not begin all packages at once.
