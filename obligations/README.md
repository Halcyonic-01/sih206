# S1: institution and obligation storage

S1 adds four models and one initial schema migration. It does not add a policy
calculator, findings, seeded APH rules, publication workflow, API or frontend.
Those are later tasks. No additional Python dependencies are required.

## Models and handoff

| Model | Contract |
|---|---|
| `InstitutionProfile` | One-to-one extension of `portal.Institution`; unique `aicte_id`, trust, institution type, region/state, contact email and active/inactive status. The existing institution remains the identity used by accounts and instruments. |
| `ProgrammeApproval` | Existing institution FK, programme, diploma/UG/PG level, approval date, LoA/EoA reference, separate land and building tenure. Institution/programme/level/reference is unique. |
| `RuleSet` | Unique `(code, version)`, effective interval (end inclusive), JSON object payload, source clause/document and optional approver. These are storage records, not published or verified policy. |
| `DepositObligation` | Existing institution FK, basis/reference, nullable `rule_version` FK to `RuleSet`, integer `required_paise`, nullable term pair/intimation date, status and exemption metadata. |

Yash's Y1 can reference `obligations.DepositObligation` from `Instrument` and
depend on `('obligations', '0001_initial')`. That migration depends on the existing
`portal.0004_release_workflow`; it does not change portal tables or migration files.
Use the existing `portal.Institution` for both sides of the future relationship.

Reverse names: `institution.deposit_profile`, `institution.programme_approvals`,
`institution.deposit_obligations`, and `ruleset.obligations`.

No existing institution is assigned a fictional AICTE ID or profile. No existing
instrument is automatically assigned a requirement, exemption or coverage status.
The F1 legacy wrapping/backfill needs Y1's instrument FK and must be coordinated
with Yash then; S1 does not create a competing instrument relationship.

Unknown requirements use `required_paise=None`, `status=UNKNOWN`; unknown terms
use two null dates. `basis=MIGRATED` is available for the later reviewed backfill.
Zero amount is permitted only for `EXEMPT`, with a code, clause, reason and
approver. A quantified amount may be recorded without claiming the obligation
is met. No ten-year date or exemption is inferred automatically.

## Validation boundaries

Call `full_clean()` before saving supplied values, following the existing model
convention. It validates choices, required strings, email, JSON object shape,
exemption metadata and dates. `save()` and bulk writes do not call it automatically.
DB constraints additionally enforce profile/approval/rule uniqueness, positive
rule versions, rule date order, paired/ordered term dates, amount/null consistency
and required exemption evidence. JSON policy schemas, publication permissions,
immutable published rules, policy dates, coverage calculations and status
transitions are not implemented in S1. No new route or admin interface exposes
these records; model validation alone is not authorization.

## Apply and verify

Back up any needed local database and documents together before an upgrade.
From the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test obligations.tests --verbosity 1
.\.venv\Scripts\python.exe manage.py test portal.tests --verbosity 0
.\.venv\Scripts\python.exe manage.py test --verbosity 0
```

The first command creates only the four new tables and normal Django permissions.
Tests use isolated databases and synthetic fixtures. Migration tests exercise
upgrade/reverse/reapply and retain existing portal records. Packaging coverage
checks that the offline source allowlist includes this registered app and its
migration while excluding local planning and runtime data.

The existing startup command remains `manage.py runserver 127.0.0.1:8010`.
S1 has no new screen: the original submission-to-release browser journey remains
the visual demonstration. The schema can be inspected through Django's shell.
