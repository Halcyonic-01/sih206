# S2 calculation invariant and boundary review

Local review on 24 October 2026, starting at `db789f8` (S1, independent S2 and
S3 preparation). Branch: `s/S2-calculation-invariants`. No API, adapter, frontend,
dependency, model or migration was added. The existing portal and S3 preparation
are preserved. This is technical test coverage of draft conventions, not approval
of policy, exemptions, bank authenticity or real-data suitability.

## Coverage inspected and added

Existing tests already exercise every Table 1.4 cell, the leased multiplier,
basic amount/top-up logic, simple renewal continuity, inclusive maturity, excluded
lifecycle states, scope/duplicate checks, rule snapshots and penalty cutoffs.
The unchanged 76-case labelled set covers additional regression contracts.

`tests/test_calculation_invariants.py` adds 24 query-free `SimpleTestCase` tests:

| Area | Additional checks |
|---|---|
| Independent timeline oracle | 400 deterministic synthetic ledgers, seed 26265; enumerate every day rather than reusing the engine's boundary algorithm; cover unknown, covered and gap outcomes |
| Invariants | All 24 permutations of a mixed ledger preserve amounts/dates and eligible ID set; positive top-ups cannot worsen shortfall or remaining-term gap; splitting/merging a holding on the same dates preserves financial assessment |
| Temporal/lifecycle boundaries | Issue/maturity inclusion, a one-day gap followed by recovery, pending versus accepted successor snapshots, release exclusion, future and ended terms, leap/year boundaries and date.min/date.max |
| Precision | Exact integer paise above JavaScript's safe range and at signed-bigint maximum; independent Fraction-based half-up penalty expectations and monotonicity |
| Invalid data | Numeric IDs/amounts, date-only types, actual boolean lifecycle flags, cross-scope/duplicate rows even when excluded, malformed text-code values |
| Read-only behavior | Input snapshots remain unchanged, outputs/evidence detached between calls, iterable inputs remain supported, unknown values distinct from known empty ledger |

The generated ledgers use short horizons spanning leap day or year end,
0--5 holdings, mixed statuses/flags and nonnegative or unknown requirements.
They test the existing pure-function zero-required convention without granting
an exemption or creating an S1 record. These are bounded deterministic tests,
not an exhaustive proof over all possible inputs. No new testing dependency was
installed.

## Verified defect and minimal fix

Before the fix, the new 23-test first revision reported 14 failing subcases:
lists/dictionaries in programme, level, land tenure, building tenure, institution
type, holding status or penalty kind escaped as raw `TypeError` from hashing.
Dataclass annotations do not enforce runtime value types. These invalid values
must receive the domain's controlled `RuleInputError`.

`calculations.py` now checks those text fields before hashing/lookup. Existing
unsupported string codes still fail closed. Valid numeric/date results and
rule fingerprints are unchanged; no policy decision was introduced. All temporal
and numerical invariant tests passed before this fix. The new suite was then
extended to 24 tests with lifecycle-flag boundaries and additional invalid
amount/date cases; all pass after the fix.

These typed calculation helpers are not substitutes for K1/S2 request validation.
Arbitrary untyped container/object shapes are outside this tested input contract.
There is no HTTP status or real authorization result claimed by these tests.

## Reproduce from the repository root

```powershell
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_calculation_invariants
.\.venv\Scripts\python.exe manage.py test obligations.tests
.\.venv\Scripts\python.exe -m evaluation.s2.run --output data\s2-strengthening-evaluation.json
.\.venv\Scripts\python.exe docs/s3/validate_fixtures.py
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test portal.tests
.\.venv\Scripts\python.exe manage.py test
```

Windows upload/packaging tests need normal temporary-directory access. A focused
obligations run under the restricted sandbox hit one existing packaging test's
`PermissionError`; it was rerun with that access. No test or application safeguard
was disabled. Private logs/results remain under ignored `data/`.

The frozen evaluation labels and historical reports under `evaluation/s2/` remain
unchanged. A fresh evaluation report records the new engine hash separately;
the old after-report remains evidence for its earlier checkpoint. Likewise S3's
verification file remains a dated record of its own preparation checkpoint.

## Results

- Pre-change full baseline: 235 passed in 56.662 s.
- New invariant/boundary tests: 24 passed, including all 400 oracle cases.
  Last focused run: 0.032 s, after strengthening the excluded foreign-holding
  cases to require the scope-specific error using unique holding IDs.
- Frozen S2 labelled cases: 76/76 passed; zero failed. No labels were edited.
- S3 validator: 19 scenarios passed, seven calculation cases including one
  expected rejection, zero database queries.
- Django checks: no issues; no migration drift; existing app migrations applied.

- Full regression after the calculation fix and all 24 test methods: 259 passed
  in 59.566 s. The later scope-assertion refinement passed the focused rerun above;
  no application code changed after this full run.
- Focused obligations suite: 100 passed in 1.099 s (S1/S2/S3 preparation tests).
- Original portal suite, run separately: 159 passed in 61.545 s.
- Whitespace check and preservation diff: pass; no S1 model/migration, portal,
  configuration, S3 preparation or frozen evaluation changes.

## Remaining integration limits

K1/K2/Y1-dependent API, database adapter and institution screens remain pending.
The current findings remain advisory. Coverage still describes current supplied
administrative snapshots, not historical bank events. A repaired short gap still
reports remaining term from the first break, not summed uncovered days. Post-term
current shortfall is kept separate from a zero remaining-term gap. Open policy
decisions remain in [POLICY_DECISIONS.md](POLICY_DECISIONS.md).
