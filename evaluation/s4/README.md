# Synthetic S4 CSV validation cases

All institutions, contacts and context snapshots are fictional. Source label:
SIMULATED. No CSV was downloaded from AICTE or contains authorized live records.
Email examples use `example.invalid`. The identity token grammar is a local demo
format, not an official regulatory schema.

`cases.json` contains seven author-written literal expected outcomes; labels have
not been independently adjudicated. The evaluator never generates expected
errors from the validator's current output.

| File / scenario | Expected outcome |
|---|---|
| valid.csv, empty synthetic context | Three candidate rows; quoted comma, Unicode and leading zeros preserved |
| invalid-fields.csv | Seven precise row/field failures, one unrelated candidate; overall INVALID |
| duplicates.csv | All three rows rejected; both sides of each ID/code collision flagged |
| valid.csv, supplied existing/legacy snapshots | Two rows conflicted, one candidate; no inferred update |
| malformed.csv | Unclosed quote after a valid prefix; discard every candidate |
| forged-header.csv | Extra approver column rejected |
| missing-header.csv | Missing profile columns rejected, never filled with defaults |

`malformed.csv` is intentionally broken and `invalid-fields.csv` intentionally
contains a formula-like string. They are test inputs, not spreadsheet templates.
Inspect them as text. The validator neither evaluates formulas nor exports rows.

```powershell
.\.venv\Scripts\python.exe -m evaluation.s4.run
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_csv_validation
```

Run from the repository root. Expected: 7/7 labelled scenarios and 23 tests pass.
Unit tests additionally cover BOM/line endings/header permutations, all required
fields, lengths matching S1 models, delimiter/encoding errors, layout/quoting,
formula prefixes, hidden controls, byte/row bounds, explicit snapshot contracts,
detached outputs, and standalone operation without Django configuration/models.
`SimpleTestCase` forbids DB queries. A negative evaluator test verifies that
removing existing-identity checks causes a label mismatch.

These are technical format checks, not regulatory accuracy metrics, performance
claims, real authorization tests or proof that a source is authentic. File hashes
describe the bytes read on that checkout; Git/editor line endings may change
those hashes without changing the semantic labels. S2's frozen evaluation files
and historical reports are untouched. Version and review any future label change.
