# Bounded MVP evaluation

`cases.json` contains 24 independently labeled synthetic metadata cases and 10 upload-envelope cases. All names, amounts and references are synthetic. Document bytes come from our locally generated fixture PDFs or explicit invalid byte strings; no third-party documents or real applicant data are used. There is no external dataset license dependency.

The labels were manually reviewed by the implementation author against the stated technical contract; they have not been independently adjudicated by a bank, AICTE official or second evaluator. Expected labels are literal entries in the dataset, not outputs copied from the rules. Unicode and whitespace cases exposed four false negatives before the fix. The same set was rerun after the fix, so it is a regression/boundary set, not a held-out generalization benchmark.

`results-before.json` records technical-v1: duplicate TP 9, FP 0, FN 4, TN 11. `results-after.json` records technical-v2: duplicate TP 13, FP 0, FN 0, TN 11. Missing-document TP 5, FP 0, FN 0, TN 19 in both runs. Precision = TP/(TP+FP); recall = TP/(TP+FN). Empty denominators are represented as null. The exact dataset SHA-256 appears in both result files.

The rule evaluation creates an isolated in-memory SQLite database. Document presence is represented by synthetic metadata rows; their dummy file paths are not read. This measures whether the two rules classify their actual inputs correctly. It does not test PDF rendering, text extraction, malware detection, instrument authenticity, regulatory correctness, or the manual reviewer's accuracy. The separate upload cases pass actual bytes to the upload validator; the HTTP suites exercise real file storage and retrieval.

All ten upload cases match the existing envelope policy. One deliberately unreadable body with `%PDF-` and `%%EOF` is accepted by that policy. This is a measured limitation, not evidence of successful PDF readability validation. Empty, plain-text and truncated files are rejected; extension, MIME and size rejection are separately tested.

Reproduce from the project folder:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_release.py --output data\release-evaluation.json
```

The command exits nonzero if any labeled contract case fails. Timing covers only the two metadata checks against small isolated SQLite fixtures, excluding setup, uploads, PDF reading and human review. Do not present it as document processing time or production throughput. Extraction precision/recall are null because extraction is not implemented. No real-world regulatory-validation accuracy, manual-time savings or bank-turnaround improvements have been measured.

`dependencies.json` contains the application dependency advisory result; `dependencies-with-bootstrap.json` also includes the packaged pip bootstrap. Both are point-in-time advisory checks, not a security guarantee. See `docs/release-readiness.md` for their tool version, scope and release implications.
