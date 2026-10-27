# Feature 2 — institution deposit-readiness checklist

27 October 2026. **Current implementation: calculation, scoped API, institution checklist and existing-form integration are built locally.** The user subsequently authorized finishing Feature 2 while pausing Feature 1. This feature does not alter the release-document pre-check. See [the current walkthrough](../readiness/README.md); the staged design below records the build rationale.

## Product wording and researched scope

Use **Deposit readiness** with the explanation **Recorded milestones, not regulatory compliance**. Acceptance, file upload, officer receipt and issuer confirmation are different facts. A full progress bar describes completion of the selected tracked steps; it cannot certify statutory compliance, authenticity or eligibility for release.

The AICTE Approval Process Handbook 2024–2027, clause 2.25(f), printed page 31 (PDF page 47), describes submitting deposit proof and Affidavit-3 within 15 days after intimation for the applicable cases. This supports a deadline tied to a recorded intimation event; it does not justify inventing a deadline for every institution. Affidavit-3 is described separately on printed page 189 (PDF page 205). Applicability, exemptions, modes and the current approved policy still require review. The implementation uses the supplied versioned rule's `proof_days`, not a new hardcoded statutory timer. [AICTE handbook, government-hosted copy](https://cdnbbsr.s3waas.gov.in/s35938b4d054136e5d59ada6ec9c295d7a/uploads/2025/03/2025031399.pdf)

The original AICTE URL `https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf` was indexed but returned 404 when opened during research; the government-hosted PDF above was inspected. No alternative website is treated as new policy authority.

For accessibility, the visual completion indicator needs an accessible name and value text. Place the interactive checklist links outside the progress indicator because progressbar descendants are presentational. Prefer native `<progress>` with visible “4 of 6 applicable recorded steps complete (67%)” text, a label and a description of unknown/simulated items. Icons and color must supplement state words. Omit a numerical indicator when no steps apply; do not show a fictional 100%. [W3C WAI-ARIA 1.2 progressbar](https://www.w3.org/TR/wai-aria-1.2/#progressbar)

The source research informs this design; the exact score, denominator and action mapping below are product choices, not requirements declared by those sources.

## Existing source map

| Checklist item | Actual available implementation | Required distinction |
|---|---|---|
| Deposit submitted and accepted | `portal.Instrument`, `obligations.sources.linked_holdings` and existing coverage calculation | Accepted **current** holding only; superseded/released holdings cannot satisfy this current-state milestone. Label FDR only for FDR mode. |
| Payment proof uploaded | Scoped typed documents, `Document.Kind.PAYMENT_PROOF`, `sources.proof_evidence` | Presence is upload metadata, not authenticity. Applicability must be supplied from the mode/policy contract. Do not demand RTGS payment proof for an exempt FDR context. |
| Affidavit-3 uploaded | `Document.Kind.AFFIDAVIT_3`, existing document upload | Upload does not establish its content or officer receipt. |
| Amount meets requirement | Existing rule snapshot and `coverage`, integer paise | Unknown requirement/held totals stay unknown. Do not compare formatted strings or sum historical holdings again. |
| Proof receipt recorded | `ProofReceiptReview`, `record_proof_receipts`, `reviewed_proof_receipts` and the existing institution receipt form | Upload dates are not officer-recorded receipt dates. Reviewed-but-missing is incomplete; no review is unknown. |
| Bank confirmation received | `verification.VerificationEvidence`, `BankConfirmation` and `verification.provenance` | Statement matching/officer acceptance are not issuer confirmation. Simulated, stale or contradictory evidence is not independent confirmation. |

Existing institution and obligation REST endpoints, owned `InstitutionPages.tsx` / `institutions.tsx`, shared auth/client and server action capabilities are available. No replacement role system, new React shell or competing bank-confirmation implementation is needed.

## Checklist and percentage contract

Each obligation returns these stable item IDs: `accepted_deposit`, `payment_proof`, `affidavit_3`, `amount_coverage`, `proof_receipt`, `bank_confirmation`.

- States: `COMPLETE`, `INCOMPLETE`, `UNKNOWN`, `NOT_APPLICABLE`, `SIMULATED`, `BLOCKED`, with a stable reason.
- Applicability must explicitly be true, false or unknown. False produces NOT_APPLICABLE and is excluded from the denominator. Unknown stays in the tracked denominator and never becomes completed.
- Completed count is COMPLETE only. Simulated bank responses are separately identified, do not raise the independent-confirmation count and cannot appear as a real green bank check.
- Percentage uses integer half-up rounding: 4/6 → 67%. Show counts as well as the percentage. Do not hardcode the sample's numbers; the user's six example lines actually have only three checked items.
- No applicable items produces percent null, not 100%. No obligations produces `NO_OBLIGATIONS`. Institution aggregation sums completed/applicable obligation milestones rather than averaging percentages; duplicate obligation IDs, mixed institutions or mixed evaluation dates are rejected.
- An explicit zero requirement is a recorded comparison value, not an inferred exemption. The adapter must establish exemption/applicability from actual policy evidence; absent requirement is null, not zero.
- Deadline is derived only when both a nonfuture recorded `intimation_date` and valid supplied `proof_days` exist. Otherwise show deadline unknown. Include the actual due date and policy provenance. Day zero is due today; negative days are overdue. The calculation uses date-only business-day snapshots and does not itself decide business calendars, penalty bands or sanctions.

### Receipt applicability

The current officer form records receipt of deposit proof and Affidavit-3. A PAYMENT_PROOF **upload** can be inapplicable for FDR while receipt of the FDR deposit proof still applies. Accordingly the pure core requires the deposit-proof receipt date when `accepted_deposit` or `payment_proof` applies; it requires the affidavit receipt date only when `affidavit_3` applies. Explicitly inapplicable affidavits do not create a permanent pending receipt. Unknown applicability makes the receipt state unknown. Marking proof receipt applicable while no proof applies is an invalid snapshot, rather than a fabricated incomplete task.

### Actions and privacy

The first core returns only symbolic action intents already permitted by the caller's server-computed capability list: `OPEN_DEPOSIT_WORKFLOW`, `UPLOAD_PAYMENT_PROOF`, `UPLOAD_AFFIDAVIT_3`, `VIEW_REQUIREMENT`, `RECORD_PROOF_RECEIPTS`, `VIEW_BANK_VERIFICATION`. COMPLETE and NOT_APPLICABLE items have no corrective action. This is **not** a permission check or a URL registry. The future adapter must derive allowed intents from authenticated scope/actions, never trust client-supplied capabilities.

Institutions cannot record officer receipts or request privileged bank confirmation merely because a checklist item is missing. Show “Officer action required” when the user cannot act; provide an authorized evidence/details link when appropriate. Do not create dead buttons, automatic writes or blanket permission grants.

## Incremental implementation

### C1 — pure calculation and labelled scenarios (implemented locally)

Files created:

- `obligations/readiness.py`: strict explicit JSON-like snapshot validation, six milestone states, deadline arithmetic, action intents and institution aggregation. No Django import, query, database write or network call.
- `docs/readiness/scenarios.json`: 18 wholly invented input/expected-result scenarios; not live demo rows.
- `obligations/tests/test_readiness.py`: 14 tests covering all 18 labels, rounding, aggregation, paise, missing/unknown/exempt cases, simulated/stale/discrepant bank facts, receipt applicability, dates, IDs and malformed contracts.

Public functions: `calculate(snapshot, institution_id=...)` and `aggregate(snapshots, institution_id=...)`. A supplied institution ID is only a consistency assertion: these functions do not establish authorization or database ownership. The future adapter must query actual scoped records first.

Run:

```powershell
$env:DATABASE_BACKEND='sqlite'
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_readiness --noinput
```

Actual focused result: **14 tests passed in 0.014 seconds**. No application route, screen, endpoint, migration or existing teammate source was modified. The root agent runs the combined regression suite alongside the other feature streams; this document does not claim that suite has passed yet.

### C2 — scoped source adapter and read-only API

Before implementation, agree exact bank-response freshness/comparison semantics with Yash and action-link targets with the shared frontend owner. Create owned `obligations/readiness_sources.py` and a read-only endpoint in owned obligation API routing/schema modules. Suggested additive route: `GET /api/institutions/{id}/readiness`; do not expose the pure function as a client-submitted assessment API.

- Start from `scoped_institutions` / `scoped_obligations`, then existing scoped holdings/documents/receipt providers. All source rows must belong to the same institution and obligation. Incomplete providers produce UNKNOWN; unavailable sources must not become false zeroes.
- Reuse existing required-amount/coverage calculations; do not invent a second APH rule engine. Use each obligation's actual rule and policy-source label. Keep draft rules visible as draft.
- Current bank confirmation needs an issuer response agreeing with current instrument facts, not merely `verification_level=CONFIRMED` or a bank-request row marked sent. The newest relevant discrepancy must take precedence over an older match; simulated responses stay simulated. Agree reuse of Yash's provenance helpers rather than copying their normalization.
- Return `as_of`, source IDs/version fingerprint, uncertainty counts, per-obligation rows and aggregate counts. Bound queries, handle pagination/completeness explicitly and avoid one query per item per record.
- Add server-resolved safe action targets/capabilities. If multiple holding candidates exist, an upload link must explicitly select the correct record; never silently upload to the first one. If no record exists, direct only an authorized institution user to deposit creation.
- Keep GET free of workflow writes, preserve scope/error conventions, and use access logging for protected evidence/staff searches. Browser state never supplies policy applicability, count facts or allowed actions.

Acceptance: allowed own institution/staff access, foreign/anonymous/unsupported-role denial, no data leakage, actual typed documents and receipt dates, source failures and unavailable data, stale bank responses and simulation, accurate multi-obligation totals, query bounds and unchanged workflow state. No write/stale-write API is introduced by this read-only feature; existing linked forms retain their own version/409 checks.

### C3 — accessible institution checklist and exact actions

Create an owned `DepositReadiness.tsx` and component tests, mounted in the existing institution detail page. Retain teammate visual design and i18n conventions. No shared shell change is needed.

- Show the institution aggregate, expandable per-obligation six-item lists, visible state words and due information. Show evidence/unknown/simulation explanations beside each item, not only a green tick.
- Progress percentage/counts come from the server; do not re-evaluate business facts in React. Preserve institution names, amounts/dates and source identifiers when toggling Hindi.
- Use links/buttons for concrete actions outside the read-only progress indicator. Reuse the actual record upload/submit, requirement and officer receipt panels. Add a targeted query parameter/deep-link handler only after its receiving form agrees the contract; do not guess `#` anchors that do nothing.
- Reflect role restrictions: an institution sees an upload when allowed; an officer sees receipt-review entry when allowed; authority read-only steps remain explanatory. Source errors, loading, empty obligations, unknown deadlines and permission denial each need distinct states.

Acceptance: keyboard focus/labels, 360px layout, Hindi labels, 4/6 counts, all-NA/no-obligation views, live refresh after the actual upload/review, disabled unauthorized corrections, working exact form targets and no automatic changes to deposit/verification/release state.

### C4 — integrated acceptance and demo

Use fresh synthetic records. Rehearse 4/6 → upload Affidavit-3 (5/6) → officer records required receipts (6/6 only if bank confirmation is genuine/current in the source context). A simulated bank case must remain explicitly simulated rather than magically reaching independent verification. Rehearse unknown intimation, one-paisa shortfall, alternate mode/applicability, overdue proof, source outage, cross-institution denial and later bank discrepancy.

Run focused API/services and UI tests, complete backend regression, TypeScript/build, translation validation and browser suite. Verify the full download/page scope and action targets. Record actual results; screenshots alone do not prove authorization or policy accuracy.

## Deferred contracts and limits

Full statutory coverage, APH updates/official exemptions, canonical documents, authenticity, uploaded-content correctness, obligation fulfillment/release eligibility and penalty decisions remain outside this six-step readiness indicator. Do not label a filled progress bar “fully compliant.” No data migrations, background jobs, new dependencies, emails or scheduler changes are needed for C1.

Work remains local. No commit, push or PR change is authorized by this feature's initial implementation.

## C2 implementation checkpoint

The user subsequently authorized end-to-end Feature 2 work. C2 now adds `obligations/readiness_sources.py`, `obligations/api/readiness_views.py`, `obligations/tests/test_readiness_api.py` and the additive GET route in `obligations/api_urls.py`. No model, migration, workflow service or shared Yash/Kushagra implementation was modified.

The endpoint is `GET /api/institutions/{id}/readiness`, with existing session authentication, institution scope, role restrictions and no-store responses. Query date/count overrides are rejected; POST is not implemented. Officer/authority reads are logged as scoped institution SEARCH access; logging or database failure returns safe 503. Bounded sources require at most 100 obligations, 1,000 visible linked holdings and 10,000 document/evidence rows; oversized/inconsistent source context fails instead of producing a truncated percentage.

Response retains aggregate counts plus `as_of`, `source_fingerprint`, uncertainty/simulation counts and per-obligation results. Obligation rows add version, `mode_known`, exact paise, holding choices and source IDs. Each item supplies permission-derived `targets` with short translatable labels, concrete agreed readiness-query URLs and separate untouched `record_reference` values. Only own editable records expose proof-upload shortcuts. Accepted FDRs do not receive an invented Affidavit-3 upload permission. Institution/authority bank targets only open their existing scoped verification tab; the receiving API still enforces who may request a confirmation.

Payment-proof upload is applicable to homogeneous RTGS holdings; it is NOT_APPLICABLE for homogeneous FDR/RPGF and UNKNOWN for absent/mixed mode context. FDR/RPGF still need their mode-specific deposit-proof receipt when that milestone applies. Affidavit-3 applicability/deadline uses a valid selected rule; missing rule context stays unknown. A sourced exemption requires the model's zero amount, approver, code, clause and reason—not only a status label. All-NA or no-obligation results remain null percentage.

Issuer confirmation uses the newest issuer response only, its authenticity assertion and Yash's current-value provenance comparison for reference, amount, IFSC, holders, issue/maturity dates and lien. Workflow-only version increments do not invalidate unchanged bank facts. Statement matches never become issuer confirmation. A new partial/invalid response cannot borrow old matching fields; malformed responses and changed facts stay unknown, simulated responses stay simulated, and a latest discrepancy blocks the milestone. Original source implementation remains unchanged.

Actual focused backend result: **27 tests passed in 10.761 seconds** (13 API/integration tests plus 14 core tests). Scenarios cover real typed uploads and receipt reviews, role/foreign/anonymous denial, action permissions, one-paisa shortfall, missing rules, workflow-only version updates, changed bank facts, simulated/statement/discrepant/malformed responses, safe source/logging failure, fingerprints, no workflow writes, bounds and query count. Root owns the UI integration and final combined regression/visual checks; this checkpoint does not claim those have completed.
