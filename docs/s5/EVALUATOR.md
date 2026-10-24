# S5 pure prerequisite evaluator

Later work adds [owned casework services](../owned/README.md) that consume this
unchanged pure evaluator through provisional trusted adapters. The evaluator itself
still applies no action. The descriptions below record its original isolated slice;
new services remain opt-in and are not wired into default browser routes.

Local synthetic implementation following the [specification](RELEASE_PATH_SPEC.md).
Code: [release_prerequisites.py](../../obligations/release_prerequisites.py).
No application workflow is wired to it. Legacy release services and S1–S4 remain
unchanged. All unresolved S5-D01--D09 decisions still apply.

## Run from the repository root

```powershell
.\.venv\Scripts\python.exe -m evaluation.s5.run
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_release_prerequisites
```

Expected: 40 scenarios passed, zero failed; 25 focused tests passed. The runner
reads local fictional JSON, prints hashes/counts and failed comparisons, and
exits 0/1. It writes no file or database row. The core uses existing S2 pure rules
and calculations and standard-library modules; no dependency or Django setup is
required. The project's existing dependencies remain necessary for regression tests.

```python
import json
from evaluation.s5.run import DATASET, context, merge
from obligations.release_prerequisites import evaluate_prerequisites

dataset = json.loads(DATASET.read_text(encoding="utf-8"))
rule, when = context(dataset)
case = next(c for c in dataset["scenarios"] if c["id"] == "S5-17")
snapshot = merge(dataset["defaults"], case["input_patch"])
result = evaluate_prerequisites(
    snapshot, operation=case["operation"], rules=rule,
    as_of=when, simulation_label="SIMULATED",
)
assert result["outcome"] == "BLOCKED"
assert result["reason_codes"] == ["CLEARANCE_OPEN"]
assert result["findings"][0]["field"] == "clearances.GRANTS"
assert result["effects_applied"] is False
```

The runner's merge/context helpers load the demonstration only. The core never
reads fixture files, case IDs, expected labels, models, PDFs or the database.
Calling it directly requires a complete materialized snapshot; missing top-level
context, unexpected fields, lazy/custom objects, floats, invalid dates/booleans
or cyclic/deep structures raise controlled `PrerequisiteInputError`.

## Input and result boundaries

`evaluate_prerequisites(snapshot, *, operation, rules, as_of, simulation_label)`
requires an exact frozen S2 `RuleSnapshot`, explicit business date, SIMULATED label
and a concrete JSON-shaped snapshot following the scenario defaults' vocabulary.
There are no silent defaults or current-date/latest-rule queries. Null facts are
explicitly unavailable. Document, clearance, declaration, actor and completeness
values remain **supplied synthetic facts**, not verified source data.

Results contain outcome, deterministic deduplicated reason codes, per-gate findings
with field paths and selected rule/date provenance, and hypothetical action
projections. DENIED results omit findings and rule context to avoid echoing foreign
case/evidence details. A successful scoped assessment also identifies its rule
fingerprint. Domain gate priority is CONFLICT, INVALID_INPUT, CONTEXT_UNAVAILABLE,
BLOCKED, RETRYABLE_FAILURE; known scope/actor denials short-circuit earlier.

Every result has `projection_only=true`, `effects_applied=false`,
`automatic_approval=false`, `bank_verified=false`, and `software_moves_money=false`.
`case_status_after_action` and `monitoring_after_action` are **predictions for a
future separate successful human/service action**, not current persisted state.
An APPROVE projection remains monitored; COMPLETE can project monitoring off only
after all supplied prerequisites, correct issued-letter kind, explanation and
new evidence pass. No PDF, serial, token, UTR or audit event is created.

REQUEST checks scoped institution/requester identity, current holding, conflicts,
path/basis, submitted evidence/declarations and holds; it does not require tasks
and penalty review to be completed before an application can be considered.
ASSESS and authority-operation checks include clearance/penalty readiness.
The fixture's generic `decision_reason` is reused as the prototype request reason;
it is not a final request serializer or API field agreement.

All required clearance units must be known, including mandatory draft units and
any supplied additional units. A shrunk unit set cannot produce READY. Penalties
are compared to existing S2 arithmetic and require recorded human disposition;
they are never applied. WAIVED remains unavailable until waiver powers are agreed
(S5-D06), even if an actor/reason is supplied. Same-day term completion stays
unavailable (S5-D05); the evaluator does not resolve the inclusive-date policy.

PUBLIC_VERIFY classifies supplied synthetic letter metadata only. It does not
lookup a token or implement a public response/route. **Never expose this internal
result dictionary as a public DTO**: fields such as monitoring projections are
not the future public allowlist. No private document/actor/case payload is returned,
but actual public serialization, revocation permission and source authenticity
still require an agreed and tested service.

## Label preservation and verified fixes

All 40 original expected outcomes/assertions are unchanged; canonical label hash:
`3946a123b0caf345c6c82346b152b1f9de2810be29ab291092c20a9e2ab2927b`.
The first run matched 38/40: S5-29/S5-30 inherited an Authority actor while testing
institution requests. Their input patches now specify institution requester 1001
and scope 101. This corrects the intended setup without weakening requester checks
or rewriting expected results. The raw dataset hash therefore changed.

Beyond the labels, regressions verify unknown instrument state, contradictory
monitoring context, evidence substitution, actor conflicts, stale assessment,
missing/extra clearance units, term boundary, pending/unsupported/waived penalties,
replay, correct penalty-clause evidence, and issued-letter kind. A mutation test
removes the open-clearance block and confirms that evaluation fails. Standalone
tests confirm no Django import/setup; `SimpleTestCase` forbids DB access.

## Not completed

No real auth/scope lookup, source completeness proof, document parsing, canonical
eleven-answer affidavit, file upload, stored clearance/penalty record, migration,
transaction/audit/outbox service, letter generation, payment, public endpoint or UI
is added. Supplied role labels and reviewed/parsed flags cannot authorize a real
decision. Caller context/version assertions are not cryptographic evidence that
all document/child/obligation versions were captured. New-case storage and legacy
compatibility still need agreement. Passing author-labeled synthetic cases is not
regulatory validation, bank authenticity or production readiness.

See [actual test results](EVALUATOR_VERIFICATION.md). The original
[preparation verification](VERIFICATION.md) remains a dated historical record.
