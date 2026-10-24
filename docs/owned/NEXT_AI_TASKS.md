# Instructions for the next AI: complete Saksham's remaining S1–S6 work

Prepared 24 October 2026. This is a work request from Saksham for the AI receiving
this file. Complete the remaining work below incrementally, using the actual
repository and agreed team contracts. Do not merely propose another plan.

This file does not say that the integration prerequisites already exist. Finish
everything available within Saksham's ownership, and record exact blockers for
anything requiring a teammate's implementation or a human policy decision.

## 1. Read and inspect before changing anything

1. Read root `AGENTS.md` in full. You work for **Saksham**, owning S1–S7.
2. Read the private planning PDFs and session notes as required by AGENTS.md.
   They are deliberately excluded from Git. If missing, request them from the
   human rather than inventing requirements or copying private plans into Git.
3. Read `README.md`, `docs/architecture.md`, the handover code map, relevant
   workflow docs, and these current implementation guides:
   - `docs/owned/README.md`
   - `docs/owned/CONTRACTS.md` (C01–C11 are proposed, not agreed)
   - `docs/owned/VERIFICATION.md`
   - `frontend/src/features/saksham/README.md`
   - S2 policy/API documents and `docs/s3` through `docs/s6` specifications,
     contract reviews and labeled fixtures.
4. Inspect Git status, branch, history, actual implementation and migration state.
   Preserve all local commits and uncommitted changes. Do not switch, reset,
   overwrite, pull into, or rebase a dirty checkout to obtain teammate code.
   Check remote main read-only if access is available; report the exact commit
   and which dependency implementations actually exist. A task title or merged
   PR alone is not proof that its API satisfies the contract.
5. Run and record baseline checks before editing. Explain findings and proposed
   fixes before each implementation slice. Obey the current stage/feature-freeze
   rules in AGENTS.md; this handoff does not authorize bypassing them.

Keep work local. Do not push, merge, deploy, contact teammates, or create remote
issues without separate human authorization. Do not implement K or Y foundations,
change their shared files/contracts, or invent agreement on their behalf. Use
their agreed extension points; request coordination for a missing shared hook.

## 2. Existing implementation to preserve

At preparation, the implementation checkpoint was local commit `1851080` on
`s/S1-S6-owned-implementation`. Recheck this rather than assuming it is still HEAD.

- S1 models and additive obligations migrations exist.
- S2 calculation/check services and scoped APIs exist against provisional ports.
- S3/S4/S6 React feature components exist under
  `frontend/src/features/saksham/`; they are not a standalone frontend application.
- S4 CSV preview/commit, reports and KPI services exist, with partial source
  coverage explicitly documented.
- S5 persisted case services, decision gates, clearances, penalties, unsigned
  letter generation, public lookup and evidence-backed completion exist.
- New APIs are available through an opt-in integration harness, not proof of
  inclusion in K1's normal application routes.
- Missing trusted sources fail closed. Test-only fake ports are not real adapters.

Do not rebuild these modules from scratch. Inspect and extend the existing code.
The old Django workflow, original tests, private documents and labeled datasets
must remain intact. Do not change expected labels merely to make tests pass.

## 3. Work to complete

### S1 — Model and migration integration

- Review additive migrations with the actual shared model state and Y1's
  instrument-to-obligation relationship. Confirm FK target, migration dependencies,
  nullable legacy behavior and data preservation.
- Resolve the proposed S5 storage choice with the team: code lives in `casework/`
  while its models are currently registered in `obligations`. Do not relocate
  applied tables, renumber shared migrations or create the reserved portal
  migration without the coordination required by AGENTS.md.
- No major replacement model foundation is requested.

Acceptance: fresh-database migration and upgrade from a backed-up prior database
work; migration drift is absent; original rows/files survive; actual Y1 records
can link to the intended obligation without inventing links for legacy data.

### S2 — Real holdings, receipts, policies and shared API conventions

- Connect actual scoped Y1 holdings and complete proof-receipt metadata from
  Y2/Y3 to the existing calculation/check services.
- Implement Saksham's receipt/source adapters against the real contracts.
  Missing integration means unavailable; a complete source reporting no proof
  means known absence. Never substitute arbitrary upload dates or an empty ledger.
- Adopt K1 routing, session/CSRF, error/schema conventions and K4 scope helpers
  through agreed interfaces. Retain version checks, audit and integer paise.
- Resolve draft-policy assumptions using reviewed authoritative requirements and
  human decisions. Until then retain draft labels and block unsupported decisions.

Acceptance: linked real-model synthetic holdings produce labeled required/held/
shortfall, term and proof findings; another institution is denied; invalid input,
stale writes and source/database failures behave correctly. Unknown never becomes
zero or an approved policy. API tests use the merged shared auth and scope stack.

### S3 — Mount and verify institution screens

- Mount existing components through K2's agreed route/menu registration and
  shared client/auth/navigation. Do not create another React/Vite setup.
- Connect list, profile, programmes, obligations, coverage timeline, open actions
  and calculator to actual APIs. Check the specification for any component gaps.
- Complete visual integration with the shared shell, loading/empty/error states,
  session/scope invalidation, mobile behavior and keyboard accessibility.

Acceptance: browser journey from institution list to linked obligation and
calculator works; values match backend labels; 403/409/service failures are clear;
switching identity cannot reveal stale data. Check desktop and 360px layouts,
keyboard navigation and document evidence links where applicable.

### S4 — Complete report sources, import integration and KPI cohorts

- Complete real verification, typed-document, shortfall, SLA and discrepancy
  adapters for the five specified reports. Preserve explicit limitations until
  each source is genuinely integrated.
- Connect existing import/report/KPI screens; verify preview then atomic commit,
  source freshness, scope, replay protection and audit on the shared stack.
- Connect actual Y6 events to documented KPI cohort definitions. Distinguish
  unknown from zero and avoid unsupported improvement claims.

Acceptance: each report agrees with a labeled synthetic database snapshot;
unauthorized records never appear in JSON/XLSX; exports resist formula injection;
failed imports leave no partial rows; actual event cohorts reproduce expected
KPIs, including incomplete history and unavailable source cases.

### S5 — Finish release backend integration

- Implement the **Saksham-owned real release-facts assembler** consuming actual
  scoped Y1/Y2/Y3 metadata, reviewed holds/basis and source completeness. Do not
  assign this responsibility to Yash or configure fixtures as application facts.
- Obtain the canonical reviewed Affidavit-6 questionnaire and template/version
  contract. Do not invent its eleven questions or silently accept missing answers.
- Connect K4 clearance membership/scope, reviewed clearance evidence, Y2 bounded
  PDF parsing and K5 transactional notification enqueueing. Configuration alone
  is not proof of notification delivery.
- Agree storage/migrations, waiver and settlement powers, term/maturity exceptions,
  path-specific prerequisites and public-verification publication contracts.
  Implement only agreed requirements; record policy blockers precisely.
- Preserve independent authority review, source/template freshness, separate
  approval and completion, new completion evidence and rollback/file cleanup.
- Keep generated letters explicitly unsigned/SIMULATED; no real bank/refund or
  legal-signature claims. Public lookup must retain its agreed minimal allowlist.

Acceptance: an authorized synthetic case traverses request, unit clearances,
penalty review, independent approval, letter, separate completion and public
verification using actual integrated adapters. Test rejection, holds, proposed
penalties, stale case/instrument/document/template state, role/scope denial,
legacy bypass attempts, parser/storage/database/outbox failures and revocation.
Approval alone must leave monitoring active. Completion must require valid new
evidence. No private information may leak through public lookup or errors.

### S6 — Finish release screen integration and rehearsal

- Mount wizard, case page, unit queue and public verification through K2.
- Connect the real questionnaire, path-specific typed uploader and protected
  PDF viewer using Y3/Y4 interfaces. Changing path must invalidate old readiness.
- Connect actual server actions, versions, reasons, documents and saved status.
  Do not infer authorization from a client role or evaluator readiness.
- Rehearse the entire journey, including rejection and public revocation. Check
  PDF page references/downloads, browser errors, stale-state reload and session loss.

Acceptance: an institution submits through the wizard; assigned unit members
review evidence; an independent authority decides; letter and completion actions
work with current versions; public verification reveals only approved fields.
An unassigned unit, other institution and stale browser cannot act. Failed writes
reload saved state without automatically replaying consequential mutations.

## 4. Order of execution

1. Establish baseline and dependency/contract status. Separate implemented,
   integrated, verified and blocked work in a short matrix.
2. Resolve required agreements, then integrate the smallest complete slice:
   scoped institution read → obligation → actual linked holding coverage through
   K1/K2. Prove cross-institution denial and unavailable-source behavior.
3. Finish S2/S3 remaining cases, then S4 source adapters and screens.
4. Integrate S5 sources and gates, then S6's complete release journey.
5. Run the full regression suite, shared frontend build and browser scenarios.
6. Coordinate with K3 for packaging/setup/CI integration. Verify a fully offline
   rehearsal before claiming the new features work offline; do not rewrite K3's
   packaging yourself without authorization.

Test after every meaningful slice before advancing. Continue independent owned
work while another item is blocked. Do not add fake production integrations to
avoid a dependency. **S7 and other new features are outside this request.**

## 5. Verification commands and evidence

From the root in PowerShell, inspect the current environment first. The existing
optional dependency lock is `requirements-saksham.txt`; shared dependency
consolidation belongs to the agreed K1/K3 integration.

```powershell
git status --short
git log -5 --oneline
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py showmigrations
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_owned_api obligations.tests.test_casework
.\.venv\Scripts\python.exe manage.py test portal.tests
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe frontend/src/features/saksham/verify.py
```

Use K2/K3's actual frontend install, typecheck, build and browser-test commands
once their setup exists. Do not assume a package.json exists from this handoff.
Run the preserved S2–S6 fixture gates and the plan's Saksham scenarios 3, 7 and 9.
Use isolated test databases and synthetic documents; back up matching private
files and database before any authorized live migration.

Historical checkpoint results were 378 backend tests, 159 separate legacy portal
tests and 11 isolated React tests passing. These overlap and are **not new results**,
merged-stack evidence or browser tests. Rerun and report actual outcomes.

## 6. Required final deliverables

- Working owned integration changes, preserved existing behavior and meaningful
  regression/API/browser tests for completed slices.
- Updated setup/run instructions, architecture/contracts and synthetic demo steps.
- S1–S6 matrix marking complete, partial or blocked, with file/test evidence.
- Exact tests executed, counts/results, failures and manual checks still pending.
- Dependency/decision blockers naming the owner, required interface or decision,
  and acceptance test it prevents. Do not call an unreviewed contract agreed.
- Honest real-versus-simulated status, security concerns and remaining release gaps.
- A concise next action for the human. Do not claim completion, deployment,
  notification delivery or offline operation without verifying it.

Start by inspecting the repository and reporting the baseline and first concrete
integration slice. Then carry out the authorized work; do not stop at an outline.
