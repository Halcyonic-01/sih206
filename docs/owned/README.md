# Saksham S1–S6 implementation checkpoint

This is local implementation against **provisional integration interfaces**,
following checkpoint `d36720a`. It preserves the original Django workflow and all
previous labeled datasets. Nothing is pushed or merged. S7/AI work is not started.

Read [shared contracts and pending agreements](CONTRACTS.md), the
[frontend integration guide](../../frontend/src/features/saksham/README.md), then
[actual verification](VERIFICATION.md). Older S2–S6 documents describe their dated
preparation slices; this guide describes the newer service/component implementation.

## What is built

| Task | New implementation | What still needs integration/agreement |
|---|---|---|
| S1/S2 | Additive versions on owned master entities; entity audit; scoped master/approval/obligation services; DRF endpoints; explicit rule calculator; holding and receipt adapter boundaries | K1 routing/auth/error conventions, K4 scope, real Y1 relationship and Y2/Y3 receipt metadata; policy publication/exemptions remain human-policy work |
| S3 | Institution list, profile/programmes, paginated obligations, coverage/holding tables, suggested follow-up and multi-programme calculator components | Mount in K2's shell with its client/auth/session identity; actual data adapters; target-browser layout/accessibility review |
| S4 | Private expiring CSV preview, all-or-nothing commit and audit, replay/conflict/expiry checks; scoped report JSON/XLSX; audit-derived KPI endpoint; report/import/KPI components | Full Y3/Y6 verification/document/intervention adapters; schema/permissions agreement; production export scale/retention; no baseline-improvement claim |
| S5 | ReleaseCase extension of a legacy request, clearance tasks, proposed/confirmed penalties, independent decision gates, frozen unsigned letter/PDF/QR, hashed public token lookup, revocation, separate completion and audit | Real source/questionnaire/parser/membership/evidence adapters, K5 enqueue adapter, storage/migration review and policy decisions; no real bank/refund integration |
| S6 | Wizard, case detail with private documents/history, unit queue and minimal public-record components | Canonical questions, path-specific document capabilities and real server permissions; K2 route registration/client/viewer; browser and end-to-end team tests |

The new release services **do persist transitions** when trusted ports are supplied.
Their existing pure prerequisite evaluator still produces projections only. A
projection is never copied into persisted status. Tests supply fake ports explicitly;
the shipped defaults do not load fixtures or pretend to validate PDFs.

## Setup and run locally

From the repository root in PowerShell, using the existing Python 3.12 environment:

```powershell
# pip, or use uv's --python equivalent if this venv has no pip.
.\.venv\Scripts\python.exe -m pip install -r requirements-saksham.txt
# Equivalent used in this workspace:
# uv pip install --python .venv/Scripts/python.exe -r requirements-saksham.txt

# Back up needed SQLite and private document files together before upgrading.
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test
```

`requirements-saksham.in/.txt` are an isolated optional lock, retaining every
original requirement pin. Shared `requirements.in/.txt` and project settings were
not edited. The new tests need DRF/openpyxl/reportlab from the optional lock.
Kushagra must consolidate dependencies into the shared setup during integration.

Default application startup is unchanged:

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

To inspect the **owned API integration harness** alongside the original routes:

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8011 --settings=obligations.integration_settings
```

This opt-in settings module only selects an isolated URL include. It is not a
K1 replacement, production deployment or a React server. Existing form login is
available at `/accounts/login/`; authenticated API GETs include `/api/institutions`
and `/api/rules`. A session without a recognized role is denied. Use the shared
session/CSRF contract for writes; do not disable CSRF for manual testing.
No new accounts, master records or financial examples are seeded automatically.

The new React components are **not mounted** by this harness. There is no Vite,
package.json, router, AppShell, auth provider or shared client in this feature
delivery. Follow the frontend guide for isolated compilation/tests and K2 handoff.

## Release storage and safety boundaries

`casework/` owns the services/PDF/API code. Its models are registered in the already
installed **obligations** app (`obligations/case_models.py`), so no shared settings
change or reserved `portal.0006` is made. `ReleaseCase.release` is one-to-one with
the original ReleaseRequest. This proposed additive storage choice must be reviewed
with Kushagra/Yash before merge; it differs from both a pure replacement and adding
columns directly to portal's request. Do not move already-applied tables casually.

Creating a new case invokes the original request service in the same transaction.
That preserves one-active-request constraints and release/renewal exclusion.
`portal/releases.py` has an S5-owned guard: old request rows work as before; extended
cases must use casework's gates, so the old form/service cannot bypass clearances.
Authority approval leaves monitoring active. Successful completion still invokes
the original new-upload/evidence/audit service and alone ends monitoring.

All new release operations are SIMULATED/draft-policy demonstrations. Waivers,
rule publication, exemptions, return-for-correction/reopening policy, actual
financial settlement and DSC/PAdES remain unavailable. The canonical eleven
Affidavit-6 questions are not invented. Public lookup shows five allowlisted
fields, never private PDFs, amounts, bank references, declarations or audit history.

Missing source/parse/permission integrations yield unavailable/denied results,
not successful simulated production data. Default release submission cannot
complete until the trusted source/template adapter is implemented and configured.
Those integration adapters still belong to Saksham once teammates' contracts are
available; this is not an instruction for Yash to implement S5 on our behalf.

## Remaining integration work

1. Agree the marked contracts, storage choice, money encoding, auth/error shape
   and version ownership with the relevant owners. No agreement is inferred here.
2. Integrate actual K1/K2/K4/K5 and Y1/Y2/Y3/Y6 interfaces. Replace narrow provisional
   adapters; never replace shared foundations or install fixture providers.
3. Mount owned endpoints in K1 and components through K2 route registration. Supply
   scope/session identity, questionnaire and document-viewer/upload capabilities.
4. Run allowed/denied/invalid/stale tests against the merged stack, including
   concurrency, document substitution and external/dependency failure scenarios.
5. Rehearse the complete journey in the target browser; check PDF viewing, mobile,
   keyboard/screen-reader behavior and offline packaging. Existing source packager
   does not yet include the new casework/frontend/optional dependencies; K3 owner
   must update and verify its bundle before claiming these features work offline.

This checkpoint is substantial independent implementation, not a declaration that
the combined S1–S6 product is finished or deployable.
