# S5 release preparation only

The later authorized [pure prerequisite evaluator](EVALUATOR.md) now executes
the labels without applying any action. Its [verification](EVALUATOR_VERIFICATION.md)
records actual results. The sections below describe the original documentation-
only checkpoint `7e05644`; its no-evaluator statements are historical.

- [Release-path specification](RELEASE_PATH_SPEC.md): scope, path/mode matrix,
  human gates, legacy compatibility, evidence, independence, letter/completion
  boundaries and unresolved team/policy decisions.
- [40 labeled synthetic scenarios](scenarios.json): literal future expectations,
  not a database seed, mock HTTP API, evaluator or real eligibility determination.
- [Verification record](VERIFICATION.md): actual checks and their limits.

No existing application/model/test file is changed. No migration, application
database write, evaluator, API, frontend, PDF or public token was added. This
preparation preserves S1–S4, including the original release workflow, S2 rules,
S3 specification and S4 CSV/KPI calculations. All work stays local.

## How to read the scenarios

1. Read `unconditional_expectations`: every example is SIMULATED, no software
   movement of money, no bank-verification claim or automatic approval, and human
   decisions remain required. Draft rule context is never published policy.
2. Read `defaults`: a fictional FDR case, three reviewed synthetic clearances,
   complete no-penalty review, no unresolved holds and a reviewed term basis.
   The signed-affidavit aggregate flags are **not** the missing canonical eleven
   questions; their exact approved template remains an implementation blocker.
3. For one scenario only, deep-copy defaults and recursively apply `input_patch`.
   Objects merge; arrays and scalar/null values replace. Start fresh for the
   next case. These alternatives are not one chronology or combined database.
4. Read `operation` as a proposed human/service action, not an existing endpoint.
   `expected` records the author's readiness/error or post-action expectation.
   There is no function here that computes it. Reason codes are proposed semantic
   labels, not K1's implemented exceptions or HTTP response codes.
5. For example, S5-17 replaces Grants' clearance with OPEN. The expected block
   does not mean the app currently checks Grants; that implementation is pending.
6. Compare S5-31 and S5-34. Human approval alone keeps monitoring active. Only
   the future separate successful evidence-backed completion ends monitoring.
   These are fictional post-action assertions; no such action runs from this file.

Every `SYNTH-...` document, order, clearance and letter reference is fictional
metadata without a corresponding PDF, signature, token or uploaded file. No real
AICTE IDs, applicants, bank records, credentials, contacts or current user roles
are embedded. Actor IDs and role labels illustrate conflicts and cannot authorize
anything. Child certificate references assume human review for that scenario;
actual child scope, ownership and document validation must be supplied later.

## Read and verify locally

From the repository root, using the existing Python environment:

```powershell
# JSON syntax/readability only; this is not release eligibility execution.
.\.venv\Scripts\python.exe -m json.tool docs/s5/scenarios.json

# Preserved application regression checks.
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test portal.tests
.\.venv\Scripts\python.exe manage.py test
```

No new dependency or setup command is required. The upload/packaging tests need
normal Windows temporary-file access. There is deliberately no `migrate`, seed,
server, API invocation or S5 evaluator command in this preparation's instructions.

The existing S2 snapshot was captured in memory for provenance using unchanged
draft payload, explicit synthetic effective dates and assessment date. Its SHA-256
is a reproducible context fingerprint, not a signature or bank authentication.
Two penalty examples were compared with existing S2 arithmetic only: 10% and 50%
of 10,000,000 paise are 1,000,000 and 5,000,000 paise. Applicability, payment and
net-refund decisions are deliberately not inferred from those numbers.

## Next work only after explicit authorization

1. Agree S5-D01--D09, especially storage/legacy compatibility, questionnaire,
   maturity exception and clearance/waiver powers. Resolve source/policy questions
   with the appropriate human; no document here supplies that approval.
2. If authorized, implement a pure prerequisite evaluator and execute these
   acceptance labels, retaining unknown versus false and human-only decisions.
3. Integrate persistence only after Y1/Y2/K4/K5 and K1 contracts are available;
   announce/coordinate the migration after refreshing main at the planned sync.
4. Add service/API transaction, scope, stale-write, failure/replay tests before
   proceeding to S6's UI. Do not rewrite legacy history or start S7 AI work.

Public verification, unsigned-demo letter generation, refund-reference formats
and revocation also require the listed agreements. DSC/PAdES, forfeiture and term
extension remain later-stage work; their mention in the plan does not authorize
implementing them now.
