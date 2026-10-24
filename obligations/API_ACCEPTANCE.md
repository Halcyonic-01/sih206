# S2 API acceptance specification

Status: PROPOSED, NOT IMPLEMENTED OR AGREED AS A SHARED CONTRACT.
Prepared 24 October 2026 for S2 integration. This file does not create endpoints,
change K1, connect Y1, publish rules or begin S3. Existing local calculations and
their limits are documented in [S2.md](S2.md). Outstanding policy decisions are in
[POLICY_DECISIONS.md](POLICY_DECISIONS.md).

## Integration prerequisites

| Dependency | Required agreement/evidence before implementation |
|---|---|
| K1 / Kushagra | DRF/session/CSRF foundation, canonical auth/error/pagination formats, scoped role helpers, OpenAPI registration |
| Y1 / Yash | Nullable instrument-to-obligation FK, migration ordering and a complete scoped holding adapter; no invented legacy requirements |
| S2 / Saksham | Additive optimistic-version fields and entity-appropriate audit storage for master/obligation writes; validated services and transaction tests |
| Team | Proposed endpoint names, allowed writers, calculator input semantics and wire-money range approved before becoming a shared contract |
| Policy owner | Decisions in the policy log, or explicitly limited synthetic demo use with draft labels |

S1 models do not currently have optimistic version fields on the new entities.
The existing `portal.AuditEvent` requires an instrument. Do not fabricate an
instrument to audit institution/profile/rule changes. Agree an entity audit
contract and new additive migrations before enabling those writes. Keep S1's
initial migration and Yash's portal migrations unchanged.

## Proposed endpoint surface

Paths below use no trailing slash; follow K1's final convention consistently.
Do not publish both spellings as separate contracts or rely on POST redirects.

| Method and path | Inputs/responsibility | Success |
|---|---|---|
| GET `/api/institutions` | Scoped, paginated list; validated `q`, `page`, `page_size` | 200 scoped summaries |
| POST `/api/institutions` | Officer-only proposal: create existing Institution identity plus its profile atomically; reason required | 201 resource with version |
| GET `/api/institutions/{id}` | Scoped identity/profile; absent profile stays explicitly unknown | 200 detail, version and actions |
| PATCH `/api/institutions/{id}` | Proposed authorized officer fields only, expected version and reason | 200 updated detail |
| GET `/api/institutions/{id}/programme-approvals` | Scoped approvals; explicit current/selected approval identity | 200 paginated list |
| POST `/api/institutions/{id}/programme-approvals` | Programme, level, approved_on, loa_ref, land/building tenure; reason | 201 created approval |
| PATCH `/api/programme-approvals/{id}` | Permitted corrections, expected version and reason; no institution reassignment | 200 updated approval |
| GET `/api/institutions/{id}/obligations` | Scoped obligations, unknown values preserved | 200 paginated list |
| POST `/api/institutions/{id}/obligations` | Reviewed basis/reference, explicit rule identity and known requirement/term or explicit unknown state; reason | 201 created obligation |
| GET `/api/obligations/{id}` | Scoped detail with rule provenance, coverage assessment, findings, actions and assessment date | 200 detail |
| PATCH `/api/obligations/{id}` | Authorized corrections with expected version/reason; no lifecycle decisions or institution reassignment | 200 detail |
| POST `/api/calculator` | Scoped institution, explicit rule_set_id, hypothetical approval inputs; read-only preview | 200 labelled calculation |

The institution/profile update is one aggregate: its future version must protect
both name/code and profile edits. Exact permitted fields need agreement before
implementation. No DELETE endpoint is proposed: referenced identities and rule
history remain protected. No upload, release, notification or S3 UI is added here.
Publication routes are not specified until maker/checker authorization is agreed.

## Proposed access rules

This is a proposal for S2's new endpoints, not a modification of current portal
permissions. K1 must supply the shared enforcement and response conventions.

| Operation | Institution user | Officer | Authority |
|---|---|---|---|
| Read institution/approval/obligation | Own institution only | Authorized staff scope | Authorized read scope |
| Create/correct master and obligation data | Denied in this proposal | Allowed only through audited services | Denied in this proposal |
| Calculator preview | Own institution | Authorized staff scope | Authorized read scope |
| Publish rules or approve exemptions | No implicit permission | Pending explicit maker/checker agreement | Pending explicit maker/checker agreement |

Auditor/Clearance roles are not invented here; extend the matrix only after K4's
helpers and scope contracts exist. Missing/ambiguous roles fail closed. Superuser
or frontend button visibility alone must not grant a business permission.

Acceptance:

- Authenticate and scope first. An institution's other-tenant object and a missing
  object both return 404 without names, counts, rule history or holding identifiers.
- Filtered list counts, pagination and related collections use the same scope.
- On allowed writes, derive institution ownership from the scoped path/context;
  never trust `institution_id`, actor, approver or computed state in the body.
- A visible object's forbidden action returns 403. A body ownership change is
  rejected with 400, even by an otherwise permitted writer.
- Same-origin sessions, HttpOnly cookies and CSRF on all POST/PATCH requests,
  including the read-only calculator POST. No token-in-local-storage workaround.
- Unauthenticated requests must receive K1's documented JSON status (401 or
  SessionAuthentication's 403), never a successful HTML login page. Freeze the
  exact status in tests once agreed; it is unresolved, not two acceptable statuses
  in a shipped acceptance test.

## Input and output conventions

Proposed JSON dates are exact `YYYY-MM-DD` calendar dates evaluated in the business
timezone. Reject invalid dates, fractional/boolean money, unsupported programme
codes or levels, unknown tenure, duplicate approval identities and unexpected
fields. Canonical programme codes are listed in `catalogue.py`; free-text legacy
programme names require a reviewed mapping, not fuzzy inference.

Proposed wire money is integer paise within the agreed JSON/JavaScript-safe range;
never floating-point rupees. S1's DB range is larger than JavaScript's safe-integer
range. Agree wire limits or lossless string encoding with K1 before accepting or
serializing larger values; do not truncate a valid stored amount. This proposal
does not change the existing integer-paise Python/model contract.

Model fields such as actor, approver, actions, version increments, coverage,
finding severity and derived amounts are server-controlled. Mutating approvals
does not silently rewrite an earlier obligation's rule snapshot or requirement.
Rules are selected by explicit identity/version and valid evaluation interval;
never silently substitute the newest rule for a historical one.

Illustrative calculator input (the IDs are synthetic placeholders):

```json
{
  "institution_id": 12,
  "rule_set_id": 3,
  "approvals": [
    {"programme": "ENGINEERING_TECHNOLOGY", "level": "UG", "land_tenure": "LEASED", "building_tenure": "OWNED"},
    {"programme": "MANAGEMENT", "level": "PG", "land_tenure": "LEASED", "building_tenure": "OWNED"}
  ]
}
```

The server obtains institution type from the scoped profile. Body approvals are
hypothetical preview inputs, not saved approvals or evidence. The expected draft
preview amount is 1000000000 paise, with multiplier 2, breakdown, rule code/version/
SHA-256, source clause/document, `DRAFT_DEMO_NOT_APPROVED` and `exemption_assessed=false`.
No obligation, approval, finding, audit action or financial decision is persisted.
Missing profile/type is a named unavailable-context conflict, not default PRIVATE.

Normal endpoints use server business date. An explicit demo `as_of` needs K1's
agreed DEBUG-only convention and visible labelling; reject an unauthorized date
override. Current administrative coverage is not a historical reconstruction.

Obligation detail must preserve null requirement/term and distinguish `UNKNOWN`
from an explicitly assessed empty ledger. If Y1's adapter is unavailable, return
an explicit unavailable assessment; never pass `holdings=[]` as a fallback.
The complete scoped holding snapshot must reject other-institution/obligation
rows and duplicate IDs before producing an assessment. An authorized client's
coverage/finding requests never accept a body-supplied ledger as stored evidence.

Every detail response includes server-computed actions and assessment provenance.
Findings include their code, compared values, clause, explicit date, checks version
and rule fingerprint. Empty findings do not mean bank-confirmed or compliant.

## Errors, stale writes and atomicity

K1 owns the shared JSON envelope. The following are proposed semantic codes, not
an implemented competing exception handler:

| Condition | Status | Proposed semantic code |
|---|---:|---|
| Invalid field/date/amount, unsupported calculator input, controlled date overflow | 400 | VALIDATION_ERROR |
| Authenticated but forbidden action or missing CSRF | 403 | PERMISSION_DENIED / CSRF_FAILED |
| Missing or out-of-scope object | 404 | NOT_FOUND |
| Stale expected version | 409 | STALE_VERSION |
| Existing unique identity or workflow conflict | 409 | IDENTITY_CONFLICT / WORKFLOW_CONFLICT |
| Visible record lacks required assessment context | 409 | ASSESSMENT_UNAVAILABLE |
| Database/storage operational failure | 503 | SERVICE_UNAVAILABLE |

Errors must be generic where disclosure is unsafe: no SQL, private paths, stack
traces, other-tenant IDs, document contents or credentials. A 503 must not be
automatically retried as a write. The client reloads to determine committed state.

Proposed update body: permitted fields plus `version` and nonblank `reason`.
Missing/malformed version returns 400. A stale version returns 409 before mutation.
An allowed update atomically changes the record, increments the version once and
creates its entity audit event. Replaying the old body cannot increment or audit
again. Concurrent writers using the same version cannot both succeed.

Creation has no existing record version; propose returning initial version 1 and
using uniqueness/conflict tests rather than inventing a stale collection version.
Confirm this exception to the team's general write-version rule before coding it.
No version fields or new migrations are implemented by this document.

## API acceptance cases to implement after dependencies arrive

| ID | Test | Exact semantic success condition |
|---|---|---|
| API-01 | Allowed read per route and role | 200, correctly scoped data, no incidental writes |
| API-02 | Institution B reads A's object/collection | 404 for object/path; lists/counts contain only B's scope |
| API-03 | Forbidden authenticated write per route | 403 and unchanged domain rows, files and audit history |
| API-04 | Missing session / ambiguous role / inactive user | K1's single agreed auth status; ambiguous/inactive role denied; no successful HTML response |
| API-05 | CSRF absent/invalid on POST/PATCH | 403, no mutation, including calculator POST |
| API-06 | Valid creation and authorized correction | 201/200; validated fields, correct ownership, version and exactly one audit event |
| API-07 | Invalid and unexpected fields | 400 with useful scoped field errors and zero partial rows |
| API-08 | Stale/replayed PATCH | 409; original newer values/version/history unchanged |
| API-09 | Two competing PATCH requests | Exactly one wins; other conflicts; no lost update |
| API-10 | Duplicate identity / protected reassignment | 409 for duplicate; 400 for reassignment; no extra rows |
| API-11 | Injected failure between save and audit | Whole write transaction rolls back; generic agreed failure response |
| API-12 | Calculator draft example | 200, 1000000000 paise and provenance; no persisted side effects |
| API-13 | Wrong rule interval, unsupported cell, invalid money or overflow | 400; no fallback amount or fabricated successful assessment |
| API-14 | Unknown obligation and unavailable Y1 ledger | Unknowns stay null; unavailable context explicit; never a false zero shortfall |
| API-15 | Top-up and term gap via real adapter | Match frozen labelled cases; no mismatched or double-counted holdings |
| API-16 | Proof deadline at -1/0/+1 day | Overdue only after inclusive deadline; both receipts needed; values and clause linked |
| API-17 | Later rule version | Earlier obligation/evidence snapshot unchanged; no silent recalculation of stored decisions |
| API-18 | Pagination/search and forged scope filters | Valid bounded pages; query/body filters cannot widen caller scope |
| API-19 | Notification/AI dependency unavailable | Pure S2 assessments still run; no simulated delivery, bank confirmation or approval |
| API-20 | Full regression gate | Original portal, S1, S2 and labelled corpus all pass alongside new HTTP tests |

Use separate clients/users and frozen dates. Assert DB state and audit counts, not
only response codes. Check both direct IDs and nested paths. Empty, loading and
error screens belong to S3 and are outside this acceptance document's implementation.
No HTTP case above is claimed to pass today: the routes do not exist yet.
