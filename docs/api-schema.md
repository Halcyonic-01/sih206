# API documentation checks

The integrated API documentation is available at `/api/docs/` and the machine-readable
contract at `/api/schema/`. On a shared host these retain the existing authentication
requirements. Feature annotations describe existing behavior; they do not authorize
requests or replace service validation.

Validate every registered endpoint, including records, verification, OCR/AI, release
cases and proof receipts, with:

```powershell
.\.venv\Scripts\python.exe manage.py spectacular --validate --fail-on-warn --file planning/openapi.yml
.\.venv\Scripts\python.exe manage.py test portal.tests.test_schema_contract
```

The contract regression checks run strict generation in a separate process, check
endpoint coverage and unique operation IDs, and verify multipart uploads, binary PDF
responses and the body-free OCR operation. Structured JSON fields such as audit
snapshots, rule-dependent assessments and OCR page evidence remain extensible.

`RecordActionSchema` selects the documented request body for the existing shared
action view: renewal uses deposit fields, document upload uses a binary file and
category, and review/observation actions use their existing versioned action inputs.
These annotations do not replace runtime permissions or business logic.

The integrated clearance contract also describes the protected evidence list,
multipart PDF upload (201), and PDF download endpoints under
`/api/releases/{id}/clearances/{unit}/evidence`. Decisions require `evidence_id`
alongside their existing reason, reference and version. Case and queue responses
describe evidence metadata, reviewer and decision timestamp without exposing PDF
bytes. List, upload and download operations have explicit unique operation IDs;
the schema regression verifies required evidence and authenticated PDF downloads.

The Windows PDF regression is covered by
`scenarios.tests.test_ps_review_fixes.ConfirmationAndCoverage`. Its download response
is consumed and closed in a `finally` block so the temporary document handle is
closed before the class removes its test directory.
