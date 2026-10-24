# Five-minute SIH demonstration and fallback

Yash workspace demonstration: `/workspace/` supports creation/submission, PDF-page
review, discrepancy/correction/resubmission, acceptance, renewal, dashboard and
synthetic statement preview/commit. See `yash-workspace.md` for setup, browser tests,
optional AI-off fallback and honest pending K/S integrations. The legacy script
below remains available unchanged as a fallback.

Y1 developer note: `portal.0005_record_fields` adds optional deposit/obligation
metadata and document categories/page counts (see `record-fields.md`). The current
screens remain the FDR demo; no verification, PDF parsing or RTGS workflow is
claimed from the new storage fields alone.

Use a **fresh extracted offline package**, not the development database or a previous rehearsal. Setup creates 17 instruments and 18 PDFs. Read local passwords privately from its two data/ credentials files. Four separate browser profiles avoid shared-login interference between roles. All documents and names are synthetic. Keep fixtures/release-evidence.pdf ready.

Start from the extracted folder with `Start-Demo.ps1 -Port 8003`, then open http://127.0.0.1:8003/. If that port is occupied, select another free port and use it consistently. Use the optional dashboard evaluation date 2026-10-23. Do not change the system clock. Run Verify-Demo.ps1 before the presentation; the verification takes longer than the five-minute talk and is not part of it.

| Time | Account and clicks | Explanation |
|---|---|---|
| 0:00–0:20 | institution_a → Records | Centralized FDR lifecycle with documents, reasons and history. All displayed data is synthetic. |
| 0:20–1:05 | Dashboard → date 2026-10-23 → View report → Approaching maturity → Export this view as CSV | Initial A counts: accepted 11, approaching 7, today 1, matured 1. CSV carries the same filters and institution scope; no notifications are sent. |
| 1:05–1:55 | officer → Records → M6-VALID → Accept for tracking → reason → Record decision. Then All visible records → Apply filters → M6-DISCREPANCY → Manual document observations | Human acceptance is recorded. The preseeded discrepancy links page 1 and declared/document amounts. It is a manual finding, not OCR. Its blocking observation is unresolved and corrections were requested. |
| 1:55–2:30 | institution_a → Records → M6-DUPLICATE with Draft status → POSSIBLE_DUPLICATE. Then M6-RENEWAL_OLD → Successor link | Two declared-data checks; a duplicate warning is advisory. Accepted successor supersedes predecessor; original history and PDFs remain. |
| 2:30–4:05 | authority → Release requests → M6-RELEASE_PENDING → Authorize release → decision reason → Record authority decision. Show completion pending. Add completion explanation and fixtures/release-evidence.pdf → Record release completion. Then queue → Rejected → Apply filter → M6-RELEASE_REJECTED | Authorization does not stop monitoring. Separate evidence-backed completion does. No payment executes. Rejection and its reason remain recorded. |
| 4:05–4:35 | institution_b → Records → M6-OTHER_INSTITUTION. Paste A's discrepancy record address | B has one record; the other institution's address returns 404. Documents and CSV share institution scope. |
| 4:35–5:00 | Return to dashboard/history | Close on traceability, controlled decisions, local operation and measured bounded evaluation. State that bank verification, OCR, notifications, payments and regulatory certification are not implemented. |

Suggested acceptance reason: “Reviewed synthetic supporting document for demonstration; accepted for tracking.” Suggested authority reason: “Authorized following human assessment for this synthetic demonstration.” Completion explanation: “Manually reviewed attached synthetic completion evidence.” Do not claim a bank approved the record.

Live actions persist and change counts; do not quote the initial counts again after acceptance/completion. Rerunning setup does **not** reset decisions. Use another fresh extraction for a new rehearsal.

Fallback: if a live mutation fails, stop retrying and reload to inspect state. Show M6-RELEASE_APPROVED for authorized-but-monitored state and M6-RELEASE_COMPLETED for preseeded completion/evidence. Identify these as preseeded outcomes, not actions just performed. Use M6-RENEWAL_OLD and its successor for a read-only lineage demonstration. Keep a second fresh extraction and the ZIP/checksum on local storage; Python 3.12 must already be available. If the UI fails entirely, show the recorded test/evaluation report and due-action output, explicitly saying the live demo failed. No screenshots or video have been generated or verified by this audit.

Before sign-off, manually verify readable text, form errors, scrolling, PDF download/viewing and screen sharing in the target browser; rehearse with the network physically disconnected if offline operation will be claimed. Browser automation could not initialize in the audit environment, so those checks remain open.
