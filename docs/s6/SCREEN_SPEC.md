# S6 release UI specification — preparation only

Prepared 24 October 2026 against local checkpoint `227a59c`. This is a proposed
screen contract, not implemented React, an agreed API, or evidence of UI testing.
All examples are SYNTHETIC / SIMULATED and use DRAFT_DEMO_NOT_APPROVED rules.

## Requirements and existing behavior

S6 covers four surfaces: release wizard (path → declarations → documents →
review), release case (clearances, penalties, decision, letter, completion),
clearance-unit queue, and public `/verify/:token`. It depends on S5 persistence
and services and K2's shared shell; K1, K4, Y2/Y3 and K5 supply supporting contracts.
Private planning sources: allocation S6 and feature designs F5, F13 and F14.

Today the Django release queue and instrument release panel work as documented
in [releases.md](../releases.md). They support request, separate authority decision
and evidence-backed completion. They do not implement the planned wizard, units,
penalties, issued letters or public verification. Preserve those templates,
routes, histories, original PDFs, access checks and services. Do not present legacy
requests as if an APH checklist or parallel clearance had been performed.

The [S5 evaluator](../s5/EVALUATOR.md) only evaluates supplied synthetic facts.
Its outputs are not database state, authorization or public response objects.
The fixture file is a reading/testing aid, never a production API fallback or seed.
The [contract review](CONTRACT_REVIEW.md) maps each screen to actual source and
unresolved dependencies. The [offline validator](validate_fixtures.py) checks
preparation consistency, not a running UI; usage is in [README.md](README.md).

## Shared presentation and action rules

- An authenticated screen identifies the institution, case/holding, saved version,
  persisted status and data freshness only after server scope succeeds. Route IDs
  and fixture roles grant no access. Clear previous data on logout, role, scope or
  case change; discard late responses belonging to an old identity or version.
- Show a next-action/responsible-party banner on every authenticated case. Keep
  readiness, actual decision, letter issuance and completion in separate regions.
  `READY_FOR_AUTHORITY_REVIEW` means human review can proceed, not release approved.
- Live actions come from the future server's scoped actions contract and current
  persisted state. Never derive enabled actions from role names alone, readiness,
  an internal evaluator result or `case_status_after_action`. S6 fixtures describe
  intended controls only; they contain no authoritative action grants.
- Show `Not independently bank-verified`. Approval means `Release authorized;
  completion pending`; monitoring remains active. Only a successful, refreshed,
  persisted completion ends monitoring. A projected completion must never update
  the status badge, monitoring badge or history locally.
- All examples show SIMULATED and draft-rule labels. A future production response
  must identify its actual approved source; do not silently remove draft labels.
  Unknown facts display `Unavailable — human review required`, not zero/false,
  cleared, waived, settled, or complete. Money uses integer paise, formatted as INR
  with two decimals; date-only values remain business dates, timestamps show IST.
- Findings show outcome, plain-language reason, field, supporting scoped document
  and page when supplied, and rule clause/version/assessment date when supplied.
  Missing evidence links say unavailable; never fabricate a PDF URL or page.
  A fingerprint is provenance, not a signature or independent verification.
- GET must have no side effects. No automatic request, upload, clearance, penalty
  confirmation, letter issuance or completion on navigation or readiness change.
  Proposed mutations need explicit human confirmation, current version, CSRF and
  backend revalidation/audit. Disable duplicate clicks while pending. On uncertain
  network failure, refresh committed state before retrying; no blind auto-replay.

## 1. Release wizard

Proposed route: authenticated release creation under the agreed K2 route registry;
the exact URL and APIs remain unagreed. Start from a scoped accepted current holding.
Show existing active request or renewal conflict rather than creating another case.
No new browser/localStorage draft persistence is proposed. Warn before discarding
unsent edits, without blocking logout. Upload staging/cleanup must be agreed first.

| Step | Fields and behavior | Advancement gate |
|---|---|---|
| Path | Holding/obligation summary, mode, one of TERM_COMPLETE, PROGRESSIVE_CLOSURE, MERGER, CONVERSION_TO_UNIVERSITY, CLOSURE_BY_AICTE; reason; applicable term basis | Supported mode/path and scoped context; no invented maturity or exemption |
| Declarations | Versioned canonical Affidavit-6 questions, explicit answers and signed affidavit evidence | Approved template and required answers available; null never means no |
| Documents | Server-generated path/mode checklist; type, ownership, parse/review status, optional page count; upload progress/errors; protected view/download | Required usable evidence and human-reviewed exceptions; server revalidates |
| Review | Entered path/reason, declarations, evidence, draft assessment and provenance, unresolved facts, next responsible party | Explicit submit; server request gate, current version; no automatic authority decision |

The approved eleven questions have not been supplied (S5-D04). Do not invent eleven
checkboxes or treat aggregate fixture flags as the legal form. Show a blocking
`Declaration template unavailable` state until that contract exists. Read-only
synthetic review examples assume a supplied template and are not a shipped form.

Changing path, mode, declarations, evidence or assessment version invalidates the
previous preview. Retain editable values where safe, refresh checklist, explicitly
identify now-inapplicable documents, and require renewed review. Do not silently
delete stored evidence or carry an exception across paths.

Path-specific acceptance:

- Term complete: obligation basis required; FDR maturity alone cannot prove term.
  Same-day term boundary stays unresolved pending S5-D05.
- Progressive closure: require no-students certificate unless an explicitly reviewed
  applicable maturity exception is supplied; unknown exception blocks advancement.
- Merger: show each scoped child and its required certificate separately; one
  child's evidence cannot satisfy another. Do not leak out-of-scope child data.
- Conversion: unknown complaints or pending proceedings remain visible gates.
- AICTE closure: proposed penalty arithmetic is not confirmation or payment.
- FDR/RPGF propose NOC; RTGS proposes sanction order. These are not issued letters.
  Unsupported guarantees produce a controlled unsupported-mode state.

REQUEST need not wait for completed clearances or penalty review. Those block
authority readiness, not initial submission by themselves. Do not use the stricter
ASSESS operation to invent a request restriction. Holds and request evidence still
apply as defined in S5. Success navigates only to the server-returned saved case.

## 2. Release case

Proposed route: authenticated case detail via K2 registration. Sections:

| Section | Display and intended controls |
|---|---|
| Header | Scoped identity, persisted status/version, monitoring, next action/party; legacy-case marker where relevant |
| Application and evidence | Path, reason, canonical answers/template version, checklist, protected documents; human review/provenance distinct from parser success |
| Clearances | All applicable units including PGRC, VIGILANCE, GRANTS and supplied additional units; status, due date, responsible group, reason/evidence where permitted; null set is unavailable |
| Penalties | Clause, base/rate, calculated integer amount, proposed/confirmed/waived status, actor/reason; unknown list is unavailable; no calculated net refund or automatic deduction |
| Readiness | Separate outcome, reasons, evidence and rule/date provenance; refresh when version changes; never a decision badge |
| Decision | Authority action and required reason only when server permits; requester and any clearance decision-maker cannot decide; officer/institution read-only |
| Letter | Not issued / generation pending / issued / failed / revoked; kind, serial, issue date and protected PDF only after persisted success; unsigned-demo label; no token/QR on failed issuance |
| Completion | Separate authorized operation: new PDF upload and notes, plus recorded refund reference for RTGS; original financial PDF or letter cannot substitute; approval and letter alone leave monitoring active |
| History | Read-only server audit/decision/evidence chronology; rejection retained; new request after rejection is a separate case, not rewritten history |

Open/objection/hold clearance and proposed penalty cannot yield authority readiness.
Unknown additional units cannot be displayed as all cleared. WAIVED remains an
unavailable policy state until waiver powers are agreed; do not add an operational
waiver button. A confirmed amount is not evidence of settlement. External NOC only
resolves its specific hold. Completion still requires independently allowed action
and current evidence. No software money transfer, bank confirmation, DSC/PAdES or
AI decision is implied. S7 summary and later-stage actions are outside this scope.

Evidence viewing: request through the protected scoped document contract, preserve
authentication and validate a known positive page within page_count. A page link
uses the future viewer's supported page navigation. Unknown page count supplies
no invented anchor. On viewer failure show accessible retry/download if authorized;
on denied/missing document show generic unavailable and no old PDF. Signed-document
content and its original version remain accessible after completion to allowed users.

## 3. Clearance-unit queue

Proposed route: scoped queue through K2 registration, not a new role implementation.
Server determines assigned groups/units and case visibility using K4. Show unit,
case/institution, status, due date (IST date), next action and responsible group.
Filter/pagination remain server scoped; no client-side all-institution preload.
Empty means no assigned work, not that every case is cleared.

An authorized unit member may open a task and propose cleared/objection/hold with
required reason/evidence under the agreed service contract. A cross-unit forged
task or stale version must fail without changing rows. Do not offer unit assignment,
role administration, reopening, bulk clearance or SLAs recalculated by the client.
S5-D06 must settle permitted transitions and visibility of other units' evidence.
Recordable clearance and authority decision are separate actions; displaying both
role labels must not permit the same actor to approve their own clearance case.

## 4. Public verification

Planned `/verify/:token` reads a separate minimal public API; no authentication or
private case fetch. This screen must never serialize the internal S5 evaluation
dictionary or reuse authenticated case DTOs. No tokens are minted by fixtures.

Proposed conservative allowlist: serial, issue date, institution display name,
letter kind, status. The plan also lists amount; publication is unresolved in
S5-D08, so exclude it until agreed. Issued means `Issued demo record found`, not
bank-verified, currently payable, legally authenticated or a valid digital signature.
Revoked must prominently say `Revoked — do not rely on this letter`, retaining only
approved minimal fields. Not found/malformed uses the same generic unavailable
message with no token reflection or private identifiers. Service failure has a
separate retryable unavailable state, never a false not-found or revoked result.
No private PDF download, bank/UTR, actor, declaration, clearance, case history,
monitoring, rule fingerprint or assessment is exposed. Public DTO/security/token
entropy, revocation, caching, logging and rate-limiting contracts require S5/K1
agreement before implementation. Do not put raw tokens in analytics or UI logs.

## Failure, accessibility and acceptance contract

Every fixture has a concrete input condition and visible expectations. These are
future acceptance tests, not browser results. `checks` are literal assertions;
`prohibited_controls` identifies controls that must not be usable in that state.
When actions are described, they are proposals conditional on server authorization.

| Input/action | Required result |
|---|---|
| Load any authenticated screen | Loading state; no previous case/actions; then scoped data or explicit empty/error |
| Invalid fields/PDF/parser rejection | Summary plus inline errors, focus first invalid field, preserve safe edits; no accepted upload claim |
| 401/session expiry | Clear protected data and pending actions; use shared login flow; no automatic write replay |
| 403 / out-of-scope 404 | Generic unavailable; no names, history, evidence, old cached case or private links |
| Stale write/readiness (409) | No optimistic success; refresh/reassess and ask human to review changed values |
| Database/storage/service failure (503), timeout | Honest unavailable/unknown; no zero penalties/empty clearances or fixture fallback; reconcile uncertain writes |
| Path/edit or out-of-order response | Invalidate preview; ignore old response by identity/case/version/request key |
| Duplicate click/reload after action | No automatic repeat; show only confirmed saved outcome/history |
| Keyboard/mobile/viewer failure | Visible focus, step headings, associated labels, text status, accessible error/live messages and readable table fallback |

At implementation time test at 360px and desktop width, keyboard-only wizard and
dialogs, focus on step/error transitions, screen-reader names, non-colour status,
and download fallback in the target browser. Ant Design reuse belongs inside K2's
existing app. No new shell, router/auth/client or npm setup is authorized here.

## Contracts to settle before implementation

S5-D01--D09 remain open: legacy/new-case storage, migration ordering, Y2/Y3 document
metadata/staging/cleanup, canonical questionnaire, term/exception/child scope,
K4 unit/authority/waiver powers, penalty settlement, letter/public publication,
versions/error/audit/notifications. See [S5 spec](../s5/RELEASE_PATH_SPEC.md).
Specifically agree saved-case/readiness versions, scoped `actions`, mutation
payloads, unit transitions, protected viewer transport, and public DTO before S6
components consume them. Route names here are intentions, not existing endpoints.
Do not integrate S5 pure projections directly as mutation success responses.
Legacy release services take the instrument version; S5's illustrative case and
assessment versions are not an agreed replacement. Also agree how clearance or
document changes invalidate readiness across separate task/document revisions.
A DENIED fixture suppresses its entire presentation payload conservatively;
the real contract must distinguish a forbidden action on a readable case from
foreign-scope or missing-object disclosure, without exposing unauthorized data.

Completion of this preparation means reviewable docs/fixtures and preserved
regressions. Full S6 completion still requires actual S5 services/APIs and K2 shell,
allowed/denied/stale/invalid API integration tests, component and browser tests,
and a synthetic end-to-end scenario. None is claimed by this document.
