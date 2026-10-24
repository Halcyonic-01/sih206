# Independent S2 correctness review (local, 24 October 2026)

Scope: `catalogue.py`, `rules.py`, `calculations.py`, `checks.py`, seed behaviour,
the existing tests and explicit snapshot contracts. S1 and the portal workflow
are preserved. No API, ORM adapter, publication workflow, S3, dependency or schema
change was added. All work remains local; no remote issue or push was made.

Baseline: 218 tests passed in 103.969 seconds before review changes.

## Verified defects and fixes

| Defect | Reproduction | Fix and coverage |
|---|---|---|
| Nested schema validated types but not required release semantics | Removing Vigilance/Grants or mandatory documents, or misspelling an FDR document kind, still yielded a valid snapshot | Schema v1 retains its mandatory document/clearance sets, mode mapping, conditional requirements and holds; incomplete/unsupported values fail explicitly |
| Escalation symbols were arbitrary nonempty strings | A recipient named `TYPO` was accepted | Validate known draft symbols, required triggers, unique boundaries/recipients and offset direction; configurable valid thresholds remain supported |
| Proof-deadline arithmetic could escape as OverflowError | Intimation at date.max plus 15 days, in both findings and penalty calls | Shared bounded date addition converts overflow to RuleInputError; the final representable deadline is still accepted |

The labelled 76-case set failed six cases before and passes all cases after the
fixes. Exact before/after outputs, engine hashes, unchanged label hash and the
metrics/limitations are in `evaluation/s2/`. Additional unit regressions cover
missing holds, duplicate escalation boundaries and extremely large day offsets.

The release requirements in schema v1 are intentionally fixed; changing those
semantics requires a deliberate reviewed schema revision. This validation is
not the authority/clearance workflow itself and does not grant any role access.

## Decisions and remaining limits

- Current coverage uses the supplied administrative state, not historical
  reconstruction. `term_gap_days` is remaining term after the first break, not
  the total number of uncovered days. The dataset explicitly labels this choice.
- Null required amount or term is unknown; absence of a finding is not a pass
  decision. Government/university applicability and exemptions are not inferred.
- Leap-day anniversaries, rounding, cross-cycle applicability and current APH
  addenda still need human policy confirmation. No interpretation was silently
  changed during this review. Late cross-year penalty computation stays blocked.
- Published RuleSet immutability/authorization, complete scoped ORM snapshots and
  API security remain deferred to the agreed K1/Y1 integration work. A frozen
  captured snapshot does not make an editable S1 RuleSet row a published policy.
- Typed snapshot calculations do not replace request validation or authorization.
- Synthetic values test technical contracts only. No bank authenticity,
  document-extraction accuracy, real-world improvement or second-reviewer
  adjudication was measured.

## Local checks

Focused model/calculation/seed/review tests: 66 passed, including all 22 S1 tests
unchanged. Original portal regression: 159 passed in 65.955 s. Final full suite:
225 passed in 74.918 s. System, migration drift/applied-state and whitespace
checks passed without changing schema. Original database table fingerprints and
25 document hashes matched after the final checks; SQLite integrity was OK.

Reproduce the review gate:

```powershell
.\.venv\Scripts\python.exe manage.py test obligations.tests --verbosity 1
.\.venv\Scripts\python.exe manage.py test portal.tests --verbosity 0
.\.venv\Scripts\python.exe manage.py test --verbosity 0
.\.venv\Scripts\python.exe -m evaluation.s2.run --output data\s2-scenario-results.json
```
