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
The runtime URL, permissions and business logic are unchanged.

The Windows PDF regression is covered by
`scenarios.tests.test_ps_review_fixes.ConfirmationAndCoverage`. Its download response
is registered for cleanup so the temporary document handle is closed before the
class removes its test directory.
