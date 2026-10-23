# What we have completed so far

Snapshot: six implemented FDR lifecycle milestones, subsequent release-readiness fixes, and a synthetic live demonstration. This folder records the work; it does not claim all official problem-statement capabilities or production readiness.

## Documents in this folder

- [Requirements and scope](requirements-and-scope.md): original needs, approved subset, acceptance gates and exclusions.
- [Build history](build-history.md): what was built first, why, dependencies, files and how each slice was verified.
- [Code map](code-map.md): file responsibilities, schema, routes, configuration and safe extension workflow.
- [Original user-supplied problem statement](original-problem-statement.txt): preserved supplied text, not a separately authenticated policy document.
- [README before handover](README-before-handover.txt): verbatim prior milestone diary. Its relative links/machine paths reflect its original location; use the current root README for navigation and setup.

## Implemented capabilities

| Area | Actual behavior |
|---|---|
| Submission | Institution-owned draft, positive INR amount, ordered dates, PDF attachment and submission |
| Review | Separate officer queue, correction request, resubmission, acceptance with reasons |
| Technical checks | Missing FDR-kind document metadata; possible same-institution duplicate bank/reference |
| Evidence | Manual observation tied to a document, optional positive page number, severity and compared values in the comment |
| Blocking review | Unresolved blocking observations stop acceptance until explicitly resolved by an officer |
| Maturity | Six scoped categories, demo date, configurable thresholds, read-only CLI due-action report |
| Renewal | Linked successor, preserved predecessor, atomic supersession at acceptance |
| Release | Institution request; independent Authority authorization/rejection; new-PDF-backed completion |
| Export | Current authorized register view as CSV, exact INR formatting, spreadsheet-text protection |
| Reliability | Transactions, optimistic versions, constraints, known-failure cleanup, generic operational 503 and no-store headers |
| Handover/demo | Offline wheel installation, idempotent synthetic scenarios, HTTP scripts, evaluation, source ZIP builder |

## Evidence that exists

The dated [release report](../../release-readiness.md) and [machine-readable recorded checks](../../../evaluation/release-checks.json) record:

- 159 tests passed after the release audit; all 143 earlier tests retained.
- Five live HTTP journeys passed; original-data and restored-data restart checks passed.
- Initial synthetic scope: 17 instruments, 18 PDFs; A sees 16, B sees 1, staff see 16 without the private draft.
- Frozen two-rule evaluation: 24 metadata cases and 10 upload-policy cases. Duplicate recall rose from 69.23% to 100% on that same boundary set after four normalization false negatives were fixed.
- Missing-document TP 5, FP 0, FN 0; duplicate TP 13, FP 0, FN 0 after correction. This is not extraction or regulatory accuracy.
- Recovery of an isolated integration dataset: 33 instruments and 37 PDFs, SQLite integrity and document hashes verified.
- Point-in-time pip-audit result: no known advisories for pinned application packages plus pip bootstrap at audit time. It is not a permanent security guarantee.

An additional live demonstration used a separate synthetic copy and executed correction/blocked acceptance/resolution, new successor acceptance and evidence-backed release. It produced an optional local read-only replay; neither replay server nor its mutated data is part of a fresh Git clone. The teammate can reproduce the underlying flows from the tests and manual guide.

## Not implemented / not signed off

No OCR/LLM, PDF field extraction, automatic document-value comparison, general application entity, regulatory policy engine, bank/AICTE connector, notification delivery, payment execution, encryption-at-rest scheme or production hosting. PDF envelopes do not guarantee readable/safe/authentic files. Page numbers are not machine-verified. Audit history is protected through supported views, not against a privileged database editor.

Browser visual/PDF presentation and physically disconnected target rehearsal remain **unverified manual gates** in the recorded audit. A successful HTTP replay is not visual sign-off. Public/real-data use remains NO-GO.

## Preservation

During implementation, schema changes were additive; existing records were not assigned invented renewal/release histories. The release audit compared all seven original portal tables row-for-row with a pre-audit backup and preserved them. New synthetic demonstrations were isolated. This handover changes documentation and packaging contents only; it does not add product behavior or erase existing work.
