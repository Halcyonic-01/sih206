# Synthetic prerequisite evaluation

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m evaluation.s5.run
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_release_prerequisites
```

Expected: 40/40 labels and 25 focused tests pass. Original author-labeled data is
in [docs/s5/scenarios.json](../../docs/s5/scenarios.json); no independent adjudication
is claimed. Its SPECIFICATION_ONLY_NO_EVALUATOR status records the original
preparation artifact, not current implementation health. The runner intentionally
does not rewrite that metadata or generate expected results from actual output.

Inputs recursively merge explicit synthetic patches over independent copies of
defaults. The core never imports this runner or reads labels. The comparator
checks all expected machine fields and unconditional invariants with strict value
types. Human assertion text is retained, pinned and documented, not interpreted as
executable code. Output includes raw-byte and canonical expected-label hashes;
Git/editor line endings may change only the raw-byte hash.

The CLI reads local JSON and prints counts/mismatches, exits nonzero on failure,
and writes nothing. All references/actors/letters are fictional. There are no
file-backed PDFs, signed letters, public tokens, bank requests or database rows.
See the [evaluator guide](../../docs/s5/EVALUATOR.md) for assumptions and limits.
