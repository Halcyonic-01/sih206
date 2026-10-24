# P6–P9 release integration and verification record

**Status:** implemented where a published platform contract exists; the release
request remains deliberately blocked until its outstanding authorized inputs are
provided. This is a local working-tree record, dated 25 October 2026.

## What changed

- `casework/api_urls.py` registers release cases, clearance work, protected
  letters and public verification through the normal `/api/` extension loader.
  No route relies on the former obligations-only test harness.
- Release scope uses `portal.permissions.clearance_unit` and
  `require_clearance`. A clearance user can see only cases with a task for its
  assigned unit and cannot decide a different unit's task. Institution scope
  still returns foreign cases as `404`.
- Release case and letter reads are access logged through `access.log_access`.
  Private document links use the normal protected `/api/documents/<id>/download/`
  endpoint; public verification exposes only its existing five-field allowlist.
- Release notifications use K5's transactional outbox and existing catalog
  entries. They create in-app/pending-email records inside the release database
  transaction with stable idempotency keys; this does **not** prove email delivery.
- `casework/facts.py` is the narrow facts contract. It deep-copies a complete,
  explicitly configured trusted source and rejects missing or malformed data.
  It never reads S5/S6 fixtures at runtime and never infers bank, document or
  questionnaire facts.
- The shared frontend route registry now mounts the protected request, case and
  clearance queue screens plus `/verify/:token`. They use the existing session,
  CSRF and error transport. The request screen stays disabled until a valid
  instrument/obligation/version plus an authorized questionnaire and document
  capability are available.

## Verification actually run

All commands below were run locally with `DATABASE_BACKEND=sqlite` and the
locmem email backend; the configured external database was not contacted.

| Command | Result |
|---|---|
| `manage.py check` | passed |
| `manage.py makemigrations --check --dry-run` | passed; no migration drift |
| `manage.py test obligations.tests.test_casework obligations.tests.test_s6_fixtures --noinput` | passed: 36 tests in 17.269 s |
| `frontend/npm.cmd run typecheck` | passed |
| `frontend/npm.cmd run build` | passed; production bundle includes `ReleasePages` |
| `python -m evaluation.s5.run` | 40/40 labelled cases passed; labels are author-labelled, not independently adjudicated |
| `docs/s6/validate_fixtures.py` | passed: 53 scenarios, 33 S5 comparisons, zero database queries |

The release tests cover default-router discovery, allowed/denied/wrong-unit
clearance writes, foreign case scope, stale writes, active-case replay blocking,
separate approval/completion, protected-letter audit logging, public allowlist,
outbox idempotency and rollback of failed letter/completion operations. The S6
fixture validator's 53 labelled scenarios remain covered by the test suite.

The parallel full frontend runner exposed a pre-existing asynchronous
institution-route test race once; that owned test file passes when run directly.
The release-specific typecheck and production build pass. Treat a stable complete
frontend-suite run as a P9 gate still to record, rather than calling it passed.
The project-wide OpenAPI generation also reports existing APIView serializer and
operation-ID warnings, including the new release APIViews; schema validation is
therefore not a release-pass claim.

## Remaining blockers before a release journey can be called complete

1. **Authorized policy input:** the canonical Affidavit-6 version, all eleven
   questions, answer interpretation and contradiction policy have not been
   supplied. The UI and backend therefore do not invent them.
2. **Yash source contract:** Y2/Y3 must expose scoped parsed-document status,
   immutable source revisions, page-linked evidence and path-specific document
   readiness. A release request may not use browser metadata or fixtures instead.
3. **Completion parser contract:** the new completion upload must be checked by
   Yash's bounded parser and return reviewed page/evidence references before
   completion can be enabled.
4. **Browser acceptance:** real end-to-end release request through completion,
   PDF page viewer, mobile/keyboard review and offline cold-start rehearsal need
   the two inputs above. They were not claimed from unit fixtures.
5. **Packaging/CI:** K3 must consolidate optional dependencies and include
   `casework`/frontend assets in the shared offline package. No teammate build
   files were edited here.

## Re-run commands

```powershell
$env:DATABASE_BACKEND = 'sqlite'
$env:EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_casework obligations.tests.test_s6_fixtures --noinput
Set-Location frontend
npm.cmd run typecheck
npm.cmd test -- --run
npm.cmd run build
```

For a final release gate, run the full backend suite, S2/S4/S5/S6 evaluation
commands from `docs/owned/S1_S6_IMPLEMENTATION_PLAN.md`, then record the exact
browser/offline outcomes here. Failed or unavailable dependencies are blockers,
not evidence that a synthetic workflow is ready.
