# Merged-code local verification — 25 October 2026

Repository commit: `e789c30` on local `main`. Scope: install dependencies, apply
existing migrations safely, run checks/tests, and identify Saksham's remaining
S1–S6 work. No application source, shared configuration, migration or test was
edited. No push, remote merge, deployment or teammate message was performed.

## Environment setup performed

- Python 3.12.14 in the existing `.venv`; Node 22.22.2; npm 10.9.7.
- Installed both current pinned Python dependency files together:
  `uv pip install --python .venv/Scripts/python.exe -r requirements.txt -r requirements-saksham.txt`.
- `uv pip check --python .venv/Scripts/python.exe`: all installed packages compatible.
- Installed frontend dependencies using `npm.cmd ci --no-audit --no-fund` in
  `frontend/`: 216 packages. npm reported a deprecated `whatwg-encoding` package.
  This was an installation, not a dependency vulnerability audit.
- Backed up the existing SQLite database to ignored
  `data/backups/before-merged-setup-20261025-015511.sqlite3`; saved private document
  hashes before applying migrations.
- Applied existing access, audit, axes and notification migrations. Afterwards,
  Django's migration graph had no pending migrations. All 25 original private
  document hashes matched. No live demo users or financial scenarios were seeded.

## Actual results

| Check | Result |
|---|---|
| `manage.py check` | Passed, no issues |
| `manage.py makemigrations --check --dry-run` | Passed, no changes detected |
| Production-profile `check --deploy --fail-level WARNING` | Passed, with the project's two configured checks silenced; not a full security certification |
| `manage.py spectacular --validate --fail-on-warn --file data/merged-schema.yml` | Passed; generated schema is 22,097 bytes, but does not include unregistered S endpoints |
| `manage.py test --noinput` | **530 run: 529 passed, 1 failure**, 197.477 seconds |
| `manage.py test portal.tests --noinput` | **159 passed**, 49.168 seconds; subset of full suite |
| Frontend `npm run typecheck` | Failed: owned `client.ts:28`, possibly undefined `whole` passed to `BigInt` |
| Frontend `npm test` | **23 passed, 4 failed**, 27 total; four audit-screen tests exceeded 5 seconds |
| Unchanged frontend suite rerun after backend completion | Same **23 passed / 4 failed**, 38.06 seconds |
| Frontend `npm run build` | Failed at the same TypeScript error; production bundle not generated successfully |
| Existing isolated `features/saksham/verify.py` | Failed to compile after nesting within the new frontend ESM package; its Node16 setup now requires ESM import extensions and produces cascading type errors |
| S2 evaluation | **76/76 passed** |
| S3 fixture validator | **19 passed**, seven calculations, one expected rejection, zero queries |
| S4 CSV / KPI evaluation | **7/7 and 10/10 passed** |
| S5 evaluator | **40/40 passed**, expected-label semantic hash unchanged |
| S6 fixture validator | **53 passed**, including 33 S5 comparisons; zero queries |
| Existing local audit chain | **INCOMPLETE**: 82 pre-existing events unsealed, zero sealed; no seals added in this pass |

Counts overlap. Pure synthetic fixtures are not browser or real-bank validation.
Historical 378/159/11 passing results predate the combined stack and do not
override these current results. No browser, Docker or complete fresh-install/
offline-rehearsal success is claimed.

### Failures requiring attention

1. **Saksham:** `frontend/src/features/saksham/client.ts:28`. Shared TypeScript
   enables `noUncheckedIndexedAccess`; explicitly narrow the parsed whole-number
   string while retaining exact integer paise, then add boundary regression tests.
   Do not weaken shared compiler settings.
2. **Saksham:** migrate or adapt the old isolated component test harness to the
   actual shared ESM/Vitest setup. The previous checker stops before running its
   11 assertions; those assertions were not verified successfully on this stack.
3. **Kushagra:** `access.tests.test_accesslog.SeedStaffTests.test_creates_accounts_units_and_private_credentials_once`
   fails on `st_mode & 0o077 == 0` with actual value 54 on Windows. This is a
   POSIX-mode assertion on Windows; real credential ACL privacy still needs
   verification. Do not infer that files are secure or insecure from this assertion
   alone. Owner implementation/tests were left unchanged.
4. **Kushagra:** four `frontend/src/features/audit/audit.test.tsx` cases timeout:
   event detail, filters, broken chain, intact chain. Reproduced without concurrent
   backend tests. No timeout thresholds or assertions were relaxed.
5. **Local setup:** the documented runner calls `seal_audit_chain` for historical
   records. A deliberate backfill is still needed if using this existing database;
   it establishes integrity from backfill time, not retrospective authenticity.

## What remains in S1–S6

| Task | Present | Remaining owned work and dependency |
|---|---|---|
| S1 | Models and additive migrations are merged and applied | Review storage/model contracts; integration test the actual Y1 FK when available. `portal` currently ends at migration 0004 and `Instrument` has no `obligation` field. Do not implement Y1. |
| S2 | Pure rules/calculations/checks, versioned master services and provisional APIs | Add the owned `obligations/api_urls.py` extension; align authentication, error envelope, pagination and schema with K1; use actual permitted role/scope semantics; connect real holdings and complete proof metadata once Y1–Y3 exist. Reconcile escalation configuration with K6's `escalation-matrix` contract; retain draft-policy labels until reviewed. |
| S3 | Institution/calculator feature components and fixtures | Fix strict compilation and test harness; add feature `routes.tsx` and page wrappers, shared-client/auth identity adapter and visual integration through K2's existing hooks; complete coverage/open-action presentation and browser/accessibility verification. No second React setup is needed. |
| S4 | Atomic CSV preview/commit, partial report sources, KPI calculations and components | Mount APIs/screens, apply shared pagination/errors/access logging, complete verification/typed-document/shortfall/SLA/discrepancy sources and actual KPI cohorts; add idempotent owned `seed_review_<area>` hooks and integrated scenario 9 tests. Y3/Y6 data remains unavailable. |
| S5 | Persisted release services, guards, clearances, penalties, unsigned letter/public lookup and completion | Register `casework/api_urls.py`; implement real Saksham-owned facts/proof adapters when Y metadata exists; obtain canonical Affidavit-6 template; connect K4 unit helpers, Y2 parser/evidence and K5 recipient/template/outbox contracts; log protected reads; agree storage, source revision, waiver/settlement and publication policies. Coordinate scheduler clearance adapter: K6 imports `casework.models.ClearanceTask` and expects `release.instrument`; actual model is in obligations with `task.case.release.instrument`. No silent competing model or K6 edit. |
| S6 | Wizard, case page, clearance queue and public verification components | Mount routes/pages and shared transport/auth; connect canonical questionnaire and Y upload/viewer; verify saved-state/actions/version handling and the full request → clearances → independent decision → unsigned letter → separate completion → public issued/revoked browser flow. |

### Confirmed integration facts

- K1/K2/K4/K5 foundations are now present locally. They should no longer be
  described as entirely missing; the remaining task is consuming their actual
  published contracts from Saksham-owned files.
- The normal `/api/institutions`, `/api/releases` and `/api/kpis` paths currently
  resolve to K1's `NotFoundView`. Our existing routes remain only in the opt-in
  harness because the auto-loader looks for different owned module names.
- Only audit and notification feature `routes.tsx` files currently exist. Our
  components are not mounted in the shared React router.
- All six callable `SAKSHAM_*` source/permission/parser/notification ports remain
  unconfigured. Keeping unavailable/denied behavior is intentional until real
  adapters are supplied; fixtures must not become runtime source providers.
- Owned master/case events use `MasterAudit`; their relationship to the new
  platform audit explorer/hash chain needs an explicit entity-audit contract.
- CI and the one-command runner currently install only `requirements.txt`, which
  does not include owned openpyxl/reportlab/qrcode dependencies. Local checks used
  both locks. Consolidation belongs to the shared K1/K3 owner; no CI fix made here.
- Canonical questionnaire, approved regulatory interpretations and full Y1–Y6
  document/verification integration remain blockers. A merged branch is not
  evidence those capabilities are available.

## Recommended next slice

First fix only the owned strict-TypeScript defect and component-test integration,
then register the owned APIs and institution screens through the existing hooks.
Use shared authentication/error/pagination/access-log behavior and test an actual
institution read in the browser. Keep linked coverage explicitly unavailable until
Y1 exists. Follow with S4/S5/S6 integration in small verified slices; do not start S7.

The current baseline is red. Report the two teammate-owned failures to the human
before any fix to those areas, as required by AGENTS.md. No source fixes were
attempted as part of this setup/verification request.

Logs, evaluation outputs, schema and database backup remain private under ignored
`data/merged-*` and `data/backups/`. No secrets or credentials are included here.
