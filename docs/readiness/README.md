# Deposit readiness checklist

Open **Institutions**, choose an institution, and look for **Deposit readiness**. Institution accounts see their own institution. Officers and authorities see their permitted scope. The panel is read-only; its links open existing permission-checked forms.

The six milestones are acceptance for tracking, payment proof, Affidavit-3, recorded amount coverage, officer receipt review, and current issuer confirmation. Steps that do not apply are excluded from the denominator. Unknown and simulated steps do not count as completed. An empty institution or an entirely exempt obligation has no percentage. A completed bar is not a regulatory compliance certificate.

## Try it with synthetic data

1. Sign in as an institution and open its institution page.
2. Expand an obligation. Read the count, deadline and individual state words.
3. For an editable deposit, choose **Upload Affidavit-3**. The correct record's upload dialog opens with that category selected. Upload an appropriate synthetic PDF through the normal form.
4. Return to the institution and choose **Refresh readiness**. The uploaded-document milestone should update. Uploading does not establish authenticity.
5. Sign in as an officer and choose **Record receipt review**. The matching obligation and receipt form open. Record actual synthetic receipt dates and a reason using the existing version-protected action.
6. After saving, the checklist reloads. An institution account cannot perform that officer action.
7. Open **Review bank confirmation** to inspect the existing verification tab. A simulated bank response remains **Simulated**, and a discrepancy remains **Needs attention**.
8. Toggle Hindi: labels change; names, references, amounts and dates retain their existing values and formatting.

## Important permission boundary

An accepted deposit currently cannot receive an Affidavit-3 or payment-proof upload through the existing record workflow. The checklist explains the missing action instead of granting an extra permission. Upload those categories while the deposit is editable. Changing this accepted-record policy requires a separate agreed workflow change.

## Implementation

- `obligations/readiness.py`: pure milestone and aggregate calculations.
- `obligations/readiness_sources.py`: bounded, scoped records/documents/receipts/current bank-evidence adapter.
- `obligations/api/readiness_views.py`: authenticated `GET /api/institutions/{id}/readiness`; query overrides are rejected, source failures return safe 503, staff reads are logged.
- `frontend/src/features/saksham/DepositReadiness.tsx`: accessible progress and per-obligation checklist.
- Existing institution and record screens receive only targeted links to their established actions.
- `scenarios.json`: 18 invented labelled cases; these are author-labelled tests, not an independent compliance evaluation.

No new migration, dependency, AI request, bank integration, status mutation or background job is introduced by this feature.

## Verification commands

From the repository root, using the existing project environment:

```powershell
$env:DATABASE_BACKEND='sqlite'
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_readiness obligations.tests.test_readiness_api --noinput
cd frontend
npm test -- --maxWorkers=2
npm run build
npm run test:translations
```

Windows PDF tests need normal access to their temporary files and subprocesses. A sandbox failure during draft creation or temporary-directory cleanup is not a passing application test; rerun with the required local permissions.
