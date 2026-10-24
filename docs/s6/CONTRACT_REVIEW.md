# S6 screen contract review

Reviewed locally against checkpoint `07163b2`, the current S1 models, S5 pure
evaluator, `portal/models.py`, `portal/releases.py`, `portal/permissions.py`,
`portal/uploads.py`, `portal/urls.py`, `config/urls.py` and existing release
templates. Planning basis: allocation S6 and F5/F13/F14. This is a gap record and
proposed handoff, not an approved OpenAPI schema or a fresh check of remote main.
No teammate code, shared API, role, migration or frontend contract was changed.

## Screen-to-source mapping

| Screen need | Actual source in this checkout | Missing agreement / responsible work |
|---|---|---|
| Scoped holding and obligation | Existing `Instrument` ownership, S1 `DepositObligation`; S5 receives materialized synthetic linkage | Y1/Y3 + S2/S5 must supply complete scoped relationships; never trust route/body institution IDs |
| Request path/reason | Legacy `request_release(actor, instrument_id, expected_version, reason)` | S5-D01 storage: extend ReleaseRequest versus new ReleaseCase; path/template/declarations absent from legacy model |
| Wizard declarations | S5 aggregate review flags are illustrative, noncanonical metadata | S5-D04: canonical eleven questions, version, required answers and correction behavior; no checkbox form can be built from the flags |
| Wizard evidence | Protected legacy downloads and upload envelope checks; evaluator sees supplied parse/review flags only | Y2/Y3 + S5-D03: typed checklist, ownership, page count, parse status, document version, staging lifetime/cleanup and protected viewer transport |
| Authority readiness | `evaluate_prerequisites()` returns outcome, reasons, findings, assessment context and hypothetical effects | S5 server adapter/service must capture authoritative scoped inputs, completeness and freshness; no S6 fixture or result is a permission grant |
| Saved case state | Legacy ReleaseRequest status plus Instrument version; S5 example case has its own illustrative version | S5 + K1 must agree instrument/case/task/document versions and aggregate invalidation; do not assume the illustrative version equals legacy instrument.version |
| Allowed actions | Legacy checks enforced in services/views; no JSON action contract | S5 + K1/K4 must supply actions, reasons and revalidation semantics; no deriving buttons from actor strings or READY |
| Parallel unit queue | No ClearanceTask model/service; S5 synthetic unit status values only | S5 + K4: real group/assignment scope, task visibility, stale checks, evidence/reason requirements and allowed transitions |
| Penalty review | S2 pure proposals and S5 synthetic disposition/arithmetic checks | S5-D06/D07: authority to confirm/waive, settlement evidence and unknown handling; no waiver button or computed net refund yet |
| Decision | Legacy independent authority approve/reject + reason/version; evaluator checks requester and clearance-decider conflicts | S5 + K4 must persist/check identities, recheck freshness and audit atomically; hiding a button is not enforcement |
| Letter | Only S5 synthetic letter state/kind/ref; no IssuedLetter service, serial, PDF, QR or token | S5-D08: generation/storage failure, issuance/retry idempotency, revocation/reissue, unsigned-demo label and protected download |
| Completion | Legacy approved request + new PDF/notes, atomic release timestamp/audit and known-failure cleanup | S5: mode-specific reference and issued-letter gates after agreement; preserve current service invariants and original evidence/history |
| Public verification | S5 PUBLIC_VERIFY classifies supplied metadata only; no route/lookup/public DTO | S5 + K1: dedicated allowlist, token lifecycle/security, generic malformed/not-found, failure/revocation/caching policy |
| Shell and error behavior | Existing Django templates/session auth; no `frontend/` in this checkout | K2 router/auth/client/layout registration; K1 errors/CSRF; K5 delivery/audit hooks. Do not implement replacements |

## Differences that affect implementation

1. **Assessment versus request:** `wizard-review-request` carries unknown penalty
   review and unfinished unit work intentionally. Those facts alone do not prevent
   a REQUEST, although they prevent authority readiness. It is a presentation-only
   assertion, not a newly measured S5 case. Agree request payload/staging behavior
   before integration; do not use ASSESS to gate initial submission.
   Several other `wizard-*` examples inherit an AUTHORITY actor from an S5 ASSESS
   snapshot. They illustrate a checklist state, not permission for that actor to
   enter an institution wizard. The S5 REQUEST snapshot also contains a fictional
   PENDING case context; it does not establish the future create API's storage or
   pre-submission draft lifecycle. Do not use these snapshots as request payloads.
2. **Projected versus saved:** the 33 linked examples contain only pre-action saved
   status/version/monitoring, not simulated post-action state. In the successful
   COMPLETE example, saved status remains APPROVED and monitoring true. No status,
   history, notification or download may be invented from the evaluator projection.
3. **Version identity:** stale-case and stale-assessment concepts exist in S5;
   real clearances/documents may change independently. Agree an aggregate revision
   or dependency fingerprint before approving based on a cached assessment. On 409
   reload, invalidate preview and require human review; no blind retry.
4. **Partial presentation data:** S6 fixtures do not contain full findings, page
   evidence, money/rates, history, assignees, next-action DTOs or timestamps. A linked
   S5 snapshot can explain a concept, but it is not an API serialization contract.
   Unknown page count in `case-viewer-failed` must not become page 1. Full field
   attribution and accessible rendering need later synthetic component fixtures
   after the actual contracts are agreed.
5. **Illustrative roles and denials:** `CLEARANCE_UNIT` and `scope_unit` describe
   presentation intent, not K4's implemented group/helper names or a trusted auth
   response. Queue fixtures have no real membership evidence. A DENIED assessment
   example suppresses all `view_data` conservatively; this does not establish that
   every action-level 403 must hide an otherwise readable own case. K1/K4 must
   distinguish safe read access, forbidden action, unknown object and foreign scope.
6. **Public allowlist discrepancy:** F5 also lists amount, while publication remains
   unresolved in S5-D08. The proposed S6 examples deliberately omit it. Serial,
   date, institution, kind and status are a conservative proposal, not approval to
   publish them. No internal `assessment_context`, monitoring, actor, document URL,
   UTR or token belongs in that DTO. Public fixtures are not a public route bundle.
7. **Legacy compatibility:** current ReleaseRequest has neither APH path/clearances
   nor issued letter. Mark historical cases as legacy; do not retroactively assert
   these gates were performed, or require invented letter IDs to render old
   completed evidence. New-case requirements and old-case compatibility need S5-D01.
8. **Retry and incomplete transitions:** return-for-correction, external hold
   resolution, waiver, issuance/revocation and task reopening have no agreed mutation
   contract here. Represent the read state without inventing operational buttons.
   A timeout after a write requires reconciliation of saved state; no auto-replay.

## Decisions before components are authorized

| Decision | Safe preparation stance | Owner / dependency |
|---|---|---|
| Routes, envelope and status errors | Proposed screen names only; no HTTP status tests claimed | K1/K2 + S5-D09 |
| Unit visibility and separation of duties | Assigned work only; no broad client preload or cross-unit action | K4 + S5-D06 |
| Exact questionnaire and reviewed exceptions | Missing template/unknown basis blocks progression; no inferred policy | S5-D04/D05 and appropriate human policy review |
| Storage, revision and document lifecycle | Preserve legacy and original bytes; invalidate stale assessment | S5-D01–D03, K1 and Y2/Y3 |
| Letter/public publication and revocation | No generated token or link; unsigned synthetic display only | S5-D08 + K1 |
| Penalties, waiver and settlement | Unknown is unavailable; confirmed is not paid | S5-D06/D07 |
| Next action, timestamps, due dates | Need authoritative source/responsible party; no browser-calculated SLA | S5 + K4/K5 |

These decisions remain unresolved. The validator checks v1 fixture consistency,
required coverage, concrete state boundaries and existing pure S5 comparisons.
It cannot establish legal meaning of natural-language expectations, real user
authorization, PDF authenticity, browser usability or end-to-end integration.
No new product feature or S7 work is part of this review.
