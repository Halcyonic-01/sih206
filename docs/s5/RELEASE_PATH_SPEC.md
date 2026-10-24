# S5 release-path specification — preparation only

Status: PROPOSED SYNTHETIC CONTRACT, NOT IMPLEMENTED OR APPROVED POLICY.
Prepared 24 October 2026 against local checkpoint `5be7631`, the private allocation
PDF page 4, plan F5 page 20 and its draft policy summaries pages 10–11. Private
planning PDFs remain outside Git. No external legal verification was performed
for this preparation. [S2 policy decisions](../../obligations/POLICY_DECISIONS.md)
P-01/P-05/P-06/P-08/P-10/P-12 remain open.

This specifies a future S5 release case, clearances, penalty disposition, letter
and completion. It implements no evaluator, model, migration, service, API, UI,
PDF generator, public route, notification or payment. The existing
[legacy release workflow](../releases.md) remains unchanged and usable.

## Existing behavior versus proposed additions

| Capability | Actual implementation today | S5 proposal / dependency |
|---|---|---|
| Request / authority approve or reject | `portal/releases.py`, reason/version/current-instrument checks | Add explicit path, declarations and captured rule context after contract agreement |
| Completion | Approved request, separate new evidence PDF, explanation; atomic monitoring cutoff and audit | Retain these invariants; add mode-specific handover/refund metadata |
| Independence | Requester cannot decide or complete own request | Also prohibit deciding authority from being a clearance decision-maker on that case; K4 role/scope agreement |
| Release eligibility | Competent human's responsibility | Draft path checklist and evidence-linked unmet prerequisites; never automatic approval |
| Clearances | Not implemented | PGRC, Vigilance, Grants, plus explicitly applicable other units; K4/K5 |
| Penalties | S2 pure human-review proposals only | Proposed -> confirmed/waived with reason and actor; no automatic debit or deduction |
| Letters | Not implemented | FDR/RPGF NOC; RTGS sanction order; immutable issued record and QR token |
| Public verification | Not implemented | Minimal allowlisted issued-record view; unknown/revoked handling; publication contract required |
| Typed PDF validation | Current upload envelope checks only | Y2 parse/page/active-content checks before new evidence counts |

S1–S4 source, schemas, tests, datasets and existing release decisions are not
modified by this specification. Readiness labels in the scenarios are author
expectations, not execution results or permission grants.

## Distinct stages and persistent invariants

1. **Request:** derive ownership from scoped server context; accepted current
   holding, no active release, no conflicting successor proposal, explicit path,
   reason, version and declarations. Never infer a path from maturity alone.
2. **Evidence / clearance review:** bind documents, declarations, relevant
   obligation and rule snapshot. Obtain all required unit decisions in parallel.
   Return missing evidence for correction; unresolved/unknown facts remain open.
3. **Ready for authority review:** no open/held/objection clearance, unresolved
   applicable penalty or known release hold. This means reviewable, not approved.
4. **Human authority decision:** require fresh versions, recheck prerequisites,
   independent authorized actor and reason. Approval authorizes only; rejection
   leaves monitoring active. No automated approval from a checklist or AI output.
5. **Letter issuance:** only after approval and a successful generation/storage
   transaction. Correct mode determines letter kind. Failure must not create an
   issued serial/token/public success or mark the holding released.
6. **Separate completion:** approved case, valid issued letter, explicit human
   action and a new protected evidence PDF. FDR/RPGF require handover/discharge
   explanation; RTGS also requires a supplied refund reference/UTR under an agreed
   format. Store evidence of an action, never execute a bank transaction.

Only step 6's future successful transaction changes monitoring eligibility.
Submission, maturity, cleared tasks, a confirmed penalty, approval or an NOC alone
must not set `released_at`. Keep originals, lineage, decisions, earlier letters
and audit history. A rejected case remains readable; a new request is a separate
history, not a rewritten rejection. Completion replay cannot replace evidence.

Legacy requests must not receive fabricated paths, declarations or clearances.
They continue on their existing workflow unless an explicit reviewed migration
and compatibility strategy is agreed. New-case gates must not silently alter
historic completed or approved records.

## Path and mode matrix

All draft paths require REQUEST_LETTER, AFFIDAVIT_6, LATEST_LOA_EOA, the mode's
financial-document kind, reviewed declaration consistency, required clearances,
penalty review and resolution of applicable holds. Document presence by itself
does not establish authentic content, correct ownership or regulatory eligibility.

| Path token (from S2 catalogue) | Additional proposed facts / evidence | Unknown handling |
|---|---|---|
| TERM_COMPLETE | Reviewed obligation term basis and term-end eligibility | Unknown or unelapsed obligation term cannot be replaced by FDR maturity |
| PROGRESSIVE_CLOSURE | Reviewed closure basis; no-students certificate, unless a competent reviewer explicitly establishes the draft matured-deposit exception | Missing maturity/exception interpretation cannot waive the certificate |
| MERGER | Reviewed merger order and complete scoped child-institution list; no-students certificate for every relevant child | A parent certificate or one child's certificate cannot cover the others; incomplete child scope stays unavailable |
| CONVERSION_TO_UNIVERSITY | Reviewed conversion basis and explicit absence of pending complaints/disciplinary proceedings | Unknown is not false; pending proceedings block progression |
| CLOSURE_BY_AICTE | Reviewed closure order; explicit applicable penalty review using supplied case facts | Do not infer lapsed application, six-year absence, penalty base or rate merely from path/name |

| Mode token | Financial document kind | Proposed issued output | Completion addition |
|---|---|---|---|
| FDR | FDR | NOC | New evidence PDF and handover/discharge explanation |
| RPGF | RPGF_PROOF | NOC | New evidence PDF and reviewed handover/refund disposition |
| RTGS | PAYMENT_PROOF | SANCTION_ORDER | New evidence PDF plus supplied refund reference/UTR |

Unsupported modes, including reserved guarantees, fail explicitly. No mode is
silently converted. The five paths and three modes mirror the **unapproved draft**
in `obligations/catalogue.py`, not a confirmed current legal checklist.

## Declarations, documents, clearances and holds

- The plan mentions eleven Affidavit-6 declarations but does not supply their
  full canonical wording/schema. Do not invent eleven checkboxes. The fixture's
  aggregate review flags are illustrative, not the final questionnaire.
- Bind the future signed PDF to its questionnaire/template version. Missing
  answers, contradictory signed evidence or an unavailable review cannot be
  treated as a clean declaration. Answers/declarations never override evidence.
- Required evidence must belong to the scoped institution, holding and case;
  document kind, parse status, ownership and human review are separate facts.
  Encrypted/unreadable/active-content/invalid-page evidence cannot satisfy a gate.
  File parsing is not bank verification. No synthetic reference below is a file.
- The clearance set itself must be known complete. Each applicable unit needs a
  scoped decision, authorized actor, reason and evidence reference. OPEN, HOLD,
  OBJECTION, missing or unknown unit decisions block authority readiness.
- A cleared internal task does not remove a trustee-dispute hold or replace an
  applicable external body's NOC. Financial-embezzlement cases remain on hold
  until the required external NOC is supplied and reviewed. Unknown hold facts
  remain unavailable; false must be established, not defaulted.
- Penalty context must explicitly say whether review is complete. Null/unavailable
  assessments are different from a complete no-penalty review. A proposal alone
  blocks readiness; confirmation/waiver requires actor and reason. Waiver powers,
  second-person checks, settlement evidence and net refund treatment remain open.
  Confirmed amount never proves payment, settlement or permission to deduct it.

## Independence, freshness, audit and failures

The eventual server scopes every lookup first; fixture roles/IDs are not a working
authorization mechanism. An institution's foreign object and absent object should
share the agreed generic unavailable response. A user with a visible case but a
forbidden action is denied. Requester/self-decision remains forbidden after role
changes. A clearance decision-maker cannot also be that case's deciding authority.
The existing independent authority may later complete a case; a second completion
authority is not invented here.

Every future write must use optimistic versions, transaction/audit and recheck
current gates. Changing declarations, documents, path or relevant policy/holding
context must invalidate prior readiness; affected clearances need an agreed
re-review policy. A previous READY label is never an authorization token.
Stale/replayed actions, active competing cases and renewal races must fail without
partial state, duplicate clearance tasks, letter serials or evidence replacement.
K1 owns the final HTTP envelopes/status codes; these fixtures make no HTTP claims.

Known generation/file/database failures must leave no partial issued/completed
state and preserve monitoring. Reuse the existing bounded transaction/file-cleanup
patterns; crash/orphan recovery needs explicit verification. Notification failure
must never be described as delivered. K5 outbox/audit agreement remains required.

## Letter and public-verification boundaries

S5 proposes a QR-linked issued PDF, **not** a digitally signed DSC/PAdES document.
No uninstalled PDF dependency is added now. A QR or stored SHA-256 verifies only
the portal record relationship, not bank authenticity or legal signature.

Future public output must be explicitly allowlisted and agreed: serial, date,
institution identifier/display name, kind and issued/revoked status; the plan also
lists amount, whose publication needs agreement. Never expose private PDF URLs,
bank/reference/UTR, declarations, clearance detail, actor contacts or full case
history. Unknown tokens disclose no case data; revoked records clearly say revoked
and cannot be presented as valid issued letters. No working token/URL exists now.
Revocation after a recorded completion must not silently undo a bank action or
erase history; correction/reissue handling needs a separate agreed service.

## Unresolved design decisions before implementation

| ID | Decision / dependency |
|---|---|
| S5-D01 | Allocation extends ReleaseRequest; F5 proposes ReleaseCase linked to obligation. Agree storage and legacy compatibility; neither design is implemented here |
| S5-D02 | Portal migration ownership/order: S5's planned 0006 only after fresh main at the instructed sync, Y1 ordering confirmed and announcement. Do not allocate a migration number now |
| S5-D03 | Y1/Y2/Y3 document type mapping, validated PDF metadata, scoped evidence adapter and complete holding/obligation context |
| S5-D04 | Exact Affidavit-6 template/version, eleven answers and how contradictions/incomplete answers return for correction |
| S5-D05 | Term completion and progressive-closure matured-deposit exception: which date/basis, inclusivity, extensions and competent reviewer; merger child scope/certificate semantics |
| S5-D06 | K4 clearance unit scope, additional applicable units, requester/clearance/authority independence and waiver powers |
| S5-D07 | Penalty applicability/base/rounding/stacking, waiver audit and settlement/net refund evidence; no automatic deduction |
| S5-D08 | Letter serial/token lifecycle, reissue/revocation permissions, public field allowlist and unsigned-demo label |
| S5-D09 | K1 versions/error contract and audited services; K5 outbox/idempotency hooks; no competing platform implementation |

## Future acceptance mapping

The JSON scenarios are literal expected outcomes for future implementation, not
executed S5 tests. For every future endpoint, add allowed/denied/invalid/stale tests
and assert unchanged records/files/audit on failures. Test atomic rollback, parallel
clearance changes, document substitution after review, duplicate decisions and
issuance, wrong/cross-case evidence, failed PDF generation and replayed completion.
Recheck all existing release/renewal/monitoring tests. Positive demo readiness never
removes the need for independent human decision and separate evidence-backed
completion. Real use remains blocked by the unresolved policy/source decisions.
