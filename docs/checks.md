# Milestone 2 scrutiny checks

This document covers the Milestone 2 scrutiny checks, preserved in Milestones 3–5. Maturity reporting is in `maturity.md`, renewals in `renewals.md`, and release handling in `releases.md`. No OCR, bank integration or notification delivery is included. Completion evidence does not satisfy FDR document-presence checks.

## Deterministic technical checks

`portal/validation.py` contains named functions, not a configurable regulatory rule engine. `run_checks()` returns current findings with a stable code, severity, explanation and relevant declared values. It does not parse document content.

| Code | Severity | Inputs and behavior |
|---|---|---|
| `FDR_DOCUMENT_REQUIRED` | Blocking | No attached document record. Drafts can be saved; submission is blocked. |
| `POSSIBLE_DUPLICATE` | Warning | Same institution, bank and reference, excluding the current instrument; compares both sides after Unicode casefold and trimming surrounding whitespace. Advisory only. |

| `HOLDER_NOT_AICTE` | Warning | FDR mode only. Holder names are recorded but do not mention AICTE (the Member Secretary, AICTE, or the full council name). A blank value is "not recorded" and gives no finding. Draft rule: APH 1.12(iv)-(v). |
| `LIEN_NOT_MARKED` | Warning, or Blocking when `FDR_LIEN_CHECK_BLOCKING=true` | FDR mode only. The record explicitly says no lien is marked. Unknown (`null`) is not treated as "no lien". When blocking, acceptance is refused until the record is corrected. Draft rule: APH 1.12 (exact wording to be confirmed). |

The two AICTE checks are **advisory draft rules**: they read what the institution declared, they do not read the document, and their clause references live in `portal/validation.py` (`AICTE_CHECK_RULES`) because the obligations `RuleSet` payload schema v1 cannot carry new rules. They add `checks_version` `technical-v3`.

Duplicate search is scoped to the current institution BEFORE matching, including that institution's drafts. It returns neither identifiers nor metadata of matching records. A matching record in another institution produces no finding. This is a limited duplicate heuristic, not a global identity check or a fraud decision. The release audit fixed SQLite's ASCII-only normalization mismatch by streaming scoped bank/reference values and comparing them consistently in Python. This is linear in an institution's record count, suitable for the small demo; no fuzzy matching or transliteration is performed.

Positive amount, required fields and date ordering remain Milestone 1 form/database validation. They are not duplicated as a second validation subsystem. There are no regulatory amount/tenure/eligibility rules.

Current findings are recalculated on detail views. GET requests do not write findings or audit records. Submission and officer decisions save the current checks version and finding values into the audit event's `after` snapshot. New snapshots use `technical-v3` (v2 added the Unicode-casefold duplicate match, v3 the two AICTE holder and lien checks); historical `technical-v1` and `technical-v2` snapshots are not rewritten. Existing Milestone 1 audit entries are retained without fabricated retrospective results.

## Per-field provenance

The record detail (`GET /api/instruments/{id}/`) carries `field_provenance`: for amount, reference, IFSC, bank, holder names,
issue date, maturity date, UTR and lien, one of

| Status | Meaning |
|---|---|
| `DECLARED` | Entered by the institution; nothing else has looked at it |
| `DOCUMENT_REVIEWED` | An officer accepted the record for tracking (officer review evidence); not bank authenticity |
| `CONFIRMED` | A bank statement line or bank response saw the **same value the record holds now** (both are SIMULATED in this prototype; `simulated: true`) |
| `MISMATCH` | That source saw a different value, or the bank denied authenticity. Mismatch wins over every other status |

It is derived on read from the append-only `VerificationEvidence` rows and the officer-correction audit events (`verification/provenance.py`); nothing new is stored. The latest evidence that looked at a field decides it, and a field an
officer corrected after the review goes back to `DECLARED`. The Details tab shows the status next to each value.
This refines the record-level verification level; it does not replace it. A filter on the records list is not part of this change.

## Manual observations

An officer inspects an uploaded document and records:

- A document belonging to the instrument (required).
- Page number (optional, positive, counted from 1).
- Warning or blocking severity.
- A description, including the compared values when relevant.
- Reviewer and timestamp (set by the server).

Page numbers are human references. There is no page-count extraction, page-bound check, OCR, automatic amount comparison or confidence score. The sample `fixtures/scrutiny-fdr.pdf` visibly states INR 600000.00 so a declaration of INR 500000.00 provides an actual manual mismatch scenario.

Observation creation and resolution are available only while the instrument is `SUBMITTED`. Institutions can read their own observations and make corrections through the existing correction workflow; they cannot create or resolve officer observations. Officers cannot scrutinize their own submissions after changing roles.

Unresolved **blocking** observations prevent acceptance on the server. Warnings do not block acceptance. Requesting corrections remains possible with unresolved observations. Editing or uploading replacement PDFs never resolves observations automatically, and references remain linked to the original document.

After resubmission, an officer resolves an observation with a required explanation. Its original comment, reviewer, timestamp, document and page remain unchanged. Resolver identity and time are server-set. Resolution cannot be overwritten through the portal. Accepted records are locked against new observations/resolutions; an unresolved warning can therefore remain in an accepted record's preserved history.

Every observation addition/resolution increments the parent instrument version, invalidating stale review forms. The observation change, version increment and audit event commit in one database transaction. Audit snapshots include original/resolved observation values and the relevant document IDs. There are no edit/delete observation endpoints.

## Verification provenance

Every detail page says **Not independently bank-verified**, including accepted records. No request parameter or review decision changes that label. The prototype has no bank confirmation field, integration, or simulation capable of claiming real confirmation.

## Acceptance checklist

- [x] Same-institution duplicate produces an explainable warning.
- [x] Different-institution match produces no warning or metadata leak.
- [x] Officer records a page-1 amount mismatch against the correct uploaded PDF.
- [x] Institution can see and correct the discrepancy.
- [x] Unresolved blocking observation prevents acceptance, including after correction/resubmission.
- [x] Officer explicitly resolves the observation; original evidence and comments remain visible.
- [x] Acceptance succeeds after all blocking observations are resolved.
- [x] Acceptance leaves bank verification unconfirmed.
- [x] Unauthorized, stale, invalid-document and repeat-resolution actions fail safely.
- [x] All Milestone 1 tests remain green.

Automated coverage: `portal/tests/test_validation.py` and `portal/tests/test_observations.py`, together with the original regression suite. Live HTTP scenario: `scripts/smoke_scrutiny.py`; restart verification: the same command with `--verify`.

At Milestone 2 completion, 49 tests and both live/restart checks passed. The current Milestone 5 suite passes all 134 tests, including those original 49. Existing Milestone 1 rows were unchanged by the additive Milestone 2 migration. Visual browser QA remains manual; the live HTTP checks are not visual verification.
