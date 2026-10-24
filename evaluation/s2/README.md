# S2 labelled synthetic correctness set

`cases.json` contains 76 original synthetic scenarios. Inputs and literal expected
results were authored separately from the calculation calls; every label has a
written arithmetic or contract rationale. No application output was copied into
the labels. The same labels were run before and after the fixes without editing.

The labels were reviewed by the implementation author, not a second evaluator,
AICTE official or bank. This is a regression/boundary set used to fix defects,
not a held-out benchmark or evidence of regulatory compliance. All identities and
holdings are fictional. No real records, document bytes or third-party dataset
are included; there is no external dataset licence dependency.

## Coverage

| Category | Cases | What is labelled |
|---|---:|---|
| Required amount | 26 | Every Table 1.4 cell, unsupported cells, leased combinations, duplicate/missing/unknown approvals |
| Term | 2 | Calendar anniversary and the explicitly provisional leap-day convention |
| Holdings coverage | 21 | Exact/partial coverage, top-ups, gaps, date boundaries, lifecycle exclusions, scope/duplicate guards and unknowns |
| Penalty proposal | 10 | Inclusive cutoffs, grace period, rounding, human-review outcome, cross-year and overflow rejection |
| Findings | 11 | Positive/negative combinations, proof documents/deadline, unknowns and controlled overflow |
| Policy validation | 6 | Valid draft and rejection of missing clearances/documents, unknown symbols and duplicate reminders |

18 cases expect a controlled input error. Ten valid finding cases contribute to
precision/recall; the finding overflow case is an error-contract test and is
excluded from those classification denominators. Null metrics would mean an
empty denominator, not perfect performance.

`defaults` supplies explicitly synthetic identities, dates, approvals and holdings.
Each case overrides those fields. A 100-paise obligation is an arithmetic boundary
fixture, not a legally sufficient deposit. All policy applicability remains draft.
The APH source and remaining interpretation questions are in `obligations/S2.md`.

## Recorded results

Both result files identify the dataset SHA-256 and exact engine-file hashes.

| Run | Passed | Failed | Meaning |
|---|---:|---:|---|
| `results-before.json` | 70 | 6 | Four incomplete/unknown policy configurations were accepted; two deadline calculations escaped as raw OverflowError |
| `results-after.json` | 76 | 0 | Same labels after semantic validation and bounded date arithmetic fixes |

| Finding | TP | FP | FN | TN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| AMOUNT_SHORTFALL | 2 | 0 | 0 | 8 | 1.0 | 1.0 |
| TERM_GAP | 3 | 0 | 0 | 7 | 1.0 | 1.0 |
| PROOF_OVERDUE | 3 | 0 | 0 | 7 | 1.0 | 1.0 |

These classification counts are identical before and after: the discovered bugs
were input/configuration error handling, not these ten finding classifications.
Do not use the perfect small-set metrics to hide the six original failures.

Recorded total case-call time was about 0.061 s before and 0.045 s after on this
machine. This includes rule validation and first-use module imports, excluding
Django startup, database access, PDF processing and human review. One run per
version does not establish a speed improvement or production throughput.

## Reproduce locally

From the repository root with its existing Python environment:

```powershell
.\.venv\Scripts\python.exe -m evaluation.s2.run --output data\s2-scenario-results.json
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_correctness_review --verbosity 1
```

Expected: 76 passed, 0 failed; exit code zero. The evaluator reads synthetic JSON
and runs in memory without querying or writing the application database, network
requests or external services. The tests enforce the no-query property. Unexpected
exceptions are reported as failures, not accepted as a generic expected rejection.
The command requires Django to initialise model imports but does not require
seeding, a running server, PDFs, an API key, K1 or Y1.

## How a teammate should review the labels

1. Read the metadata and confirm the draft-policy and review-status limitations.
2. Pick a case ID and combine its `input` with `defaults` in the JSON.
3. Calculate the result from its rationale without reading the recorded actual
   output. For `coverage-short-top-up`, 60 + 40 covers April 20-21; only 60 remains
   April 22-24, so the first gap is April 22 and three term days remain.
4. Check penalty dates against the cited draft interpretation and keep provisional
   rounding/leap-day conventions separate from confirmed statutory rules.
5. Compare your result with `expected`. Record disagreements and rationale before
   considering a label revision; do not copy a failing implementation's answer.
6. Rerun into ignored `data/`, keeping the original before/after reports intact.

Labels are hash-pinned by the regression test. A deliberate correction needs a
documented reason, a new dataset version and refreshed evaluation records; a
second reviewer has not yet signed off this version.

The folder-local `.gitattributes` preserves JSON bytes across checkouts so line
ending conversion cannot change the frozen dataset/report hashes.
