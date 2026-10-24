# Minimum interfaces for parallel implementation — AGREEMENT REQUIRED

Status: **PROPOSED AND LOCALLY IMPLEMENTED, NOT TEAM-APPROVED**. No shared teammate
file, helper or API schema was changed. This document describes actual owned code
and the integration points to review; it does not claim K1/Y1 are merged.

## Decisions to confirm first

| ID | Proposed boundary | Must agree |
|---|---|---|
| C01 | K1 includes `obligations.api.urls` under `/api/`; owned paths have no trailing slash | Kushagra + Saksham: paths, slash convention, auth, errors, schema registration |
| C02 | Existing `portal.Institution` is the shared identity; `Instrument.obligation` targets `obligations.DepositObligation` nullable FK | Yash + Saksham: relationship/migration ordering, accepted mode codes and complete scoped holding snapshots |
| C03 | Profile version protects institution name/code/profile aggregate; approval and obligation each own a version | Kushagra + Saksham: entity audit/version contract and permitted master writers |
| C04 | ReleaseCase extends a legacy ReleaseRequest; new tables currently registered in obligations, code in casework | All three: review this storage choice before integration; no portal migration allocated |
| C05 | Separate case `version` and legacy `instrument_version`; any clearance/penalty/letter action advances case revision | Kushagra + Yash + Saksham: cross-entity freshness and correction rules; instrument changes rechecked at decision/completion/issuance |
| C06 | Existing roles/scope are reused conservatively; clearance membership/evidence helpers are injected and deny/unavailable by default | Kushagra + Saksham: real K4 helpers, unit assignments, region/bureau scope and independence |
| C07 | Integer paise on write, bounded to JS-safe range; legacy values beyond safe range encoded as decimal strings on reads | All three: wire encoding. Frontend `money()` supports both losslessly; never float rupees |
| C08 | Canonical questionnaire/template reference and path-specific document readiness come from server data | Saksham + Yash: exact document metadata/validation contract; appropriate human supplies canonical questions and policy interpretations |
| C09 | Public DTO is only serial, issue_date, institution_name, kind, status | Kushagra + Saksham: publication approval, token/revocation lifecycle, caching/log redaction/rate limiting; amount excluded pending agreement |
| C10 | K2 injects client and route navigation; owned components export functions, not an app shell | Kushagra + Saksham: client adapter, identity invalidation, route registry, Ant Design integration and viewer/upload callbacks |
| C11 | K5 adapter enqueues minimal notification intent in the same DB transaction, never sends inline | Kushagra + Saksham: recipient type, template names and idempotency key; absent hook is not delivered |

These are integration proposals, not approval of draft regulatory interpretations.
S5-D04–D08 and S2's policy log remain open. No automatic exemptions, penalties,
waivers or financial decisions follow from a successful calculation.

## Backend surface that exists in the opt-in harness

| Method | Relative to `/api/` | Owner |
|---|---|---|
| GET, POST | `institutions` | S2; POST needs Officer and reason |
| GET, PATCH | `institutions/{id}` | S2; PATCH needs version, reason, permitted fields |
| GET, POST | `institutions/{id}/programme-approvals`, `institutions/{id}/obligations` | S2 |
| GET, PATCH | `programme-approvals/{id}`, `obligations/{id}` | S2 |
| GET | `rules` | S2 draft metadata; no publication/write API |
| POST | `calculator` | S2 read-only preview, still session/CSRF-protected |
| POST | `imports/institutions/preview`, `imports/institutions/{id}/commit` | S4; same officer, current preview version and reason |
| GET | `reports/{kind}` with optional `download=xlsx` | S4; partial source limitations explicit |
| GET | `kpis?window_start=...&window_end=...` | S4; aware ISO instants, no future window |
| GET, POST | `releases` | S5; POST requires real source/template adapter |
| GET | `releases/{id}` | S5/S6 case data and scoped actions |
| POST | `releases/{id}/clearances/{unit}` | S5; version/status/reason/evidence_ref |
| POST | `releases/{id}/penalties` | S5; version/reason, optional kind+base_paise or confirm_id; neither marks complete review |
| POST | `releases/{id}/approve`, `.../reject` | S5; version/instrument_version/reason |
| POST | `releases/{id}/issue`, `.../revoke` | S5; version/reason; unsigned simulation only |
| POST | `releases/{id}/complete` | S5; multipart versions, notes, NEW document, RTGS refund_reference |
| GET | `releases/{id}/letter`, `clearance-tasks` | Protected download / scoped unit queue |
| GET | `public/verify/{token}` | Minimal unauthenticated public record only |

Collection shape is `{count,page,page_size,results}` with default page_size 25,
maximum 100. No GET creates rows. Single resources are plain JSON. Write versions
are integers ≥1; creation has no existing resource version (except the source
instrument when opening a release). Missing or malformed required versions return
400; stale versions 409. Unexpected/protected fields are rejected.

The isolated base uses DRF SessionAuthentication, so an unauthenticated request
returns **403**, and writes require CSRF. This is provisional until K1 supplies the
single shared convention. Other handled errors use `{error:{code,fields}}`:
400 invalid input, 403 forbidden visible action, 404 missing/foreign object,
409 stale/workflow/identity conflict, 503 storage/database/missing integration.
DRF-native parser/auth errors retain DRF shapes until K1 normalization. Do not write
a consumer assuming all errors already share one envelope. No error echoes SQL,
private file paths or arbitrary dependency exception text. All responses no-store.

## Model and source adapters

- `services.holding_snapshot(actor, obligation)` consumes only Y1's actual FK.
  No FK means unavailable, not `holdings=[]`. Yash must preserve issue/maturity,
  amount, status, superseded_at and released_at semantics or agree an adapter.
- `SAKSHAM_PROOF_RECEIPTS(actor, obligation)` returns exactly
  `{payment_proof_on: date|None, affidavit_on: date|None}` from complete scoped
  evidence. Missing hook means unavailable. None means known absence only when the
  hook supplied a complete source context. No arbitrary upload date is substituted.
- `SAKSHAM_RELEASE_FACTS(*, actor, instrument, obligation, path, declarations)`:
  trusted, read-only **Saksham adapter** assembling the exact S5 snapshot shape
  (`obligations.release_prerequisites.TOP/SECTIONS`). It consumes Y1/Y2/Y3 facts and
  human-reviewed basis/holds/affidavit context. It must verify canonical answers,
  source completeness, mode, scope, reviewed exceptions and document metadata.
  Server-owned identities, persisted statuses, clearances, penalties, letter and
  monitoring overwrite source values. Missing/invalid shape fails unavailable.
  **Never configure this to return docs/s5 fixtures in a real/demo application.**
- New release body includes `instrument_id, obligation_id, instrument_version,
  path, declarations, reason, template_ref`. The template reference is captured;
  mismatch against current source blocks creation/assessment. No invented eleven
  questions or blank template fallback exists. Case facts need reviewed real or
  authorized synthetic document metadata, not client assertions of validity.
- `SAKSHAM_CLEARANCE_PERMISSION(actor, task)` must return exact True for a scoped
  assigned unit member. Missing hook denies actions; queue is unavailable rather
  than falsely empty. `SAKSHAM_CLEARANCE_EVIDENCE(actor, task, evidence_ref)` verifies
  scoped reviewed evidence. Neither helper may trust body-supplied ownership.
- `SAKSHAM_COMPLETION_VALIDATOR(upload)` must call Y2's bounded PDF parser and return
  exact True only after validation, restoring/allowing rewind. Default missing means
  completion unavailable. Legacy envelope validation still runs afterward.
- `SAKSHAM_NOTIFY(recipients, template, context, key)` adapter receives requester
  user IDs, action label, `{case_id,version}` and stable `S5:case:version:action` key.
  It must call K5's local transactional outbox; no inline external messages. Its
  absence is returned as INTEGRATION_PENDING, never simulated delivery success.
- `SAKSHAM_PUBLIC_BASE_URL` must be explicitly configured before issuance, with no
  credentials/query/fragment. QR rendering uses reportlab. The token is random,
  hashed for lookup, and appears in the private PDF; no public PDF endpoint exists.

These callable names are local ports, not claims about teammates' existing function
names. Agree adapters rather than forcing them to rename their shared foundation.

## Saved state, actions and uncertainty

Case responses keep saved status/monitoring separate from nested `readiness`.
Evaluator `projection_only/effects_applied` flags are retained. APPROVED does not
mean COMPLETED, issued letter does not mean refund, and confirmed penalty does
not mean paid. No money is moved and no bank verification is asserted.

Decisions/completion use both case and instrument revisions. Letter issuance also
claims the current instrument revision and audits it to reject concurrent changes.
Task or penalty changes advance case revision. Source documents/holds and template
facts are reread at consequential operations; policy must define their immutable
review revisions before production use. Do not assume a stale browser preview is
authority to act. A timeout/503 on write requires reading saved state, not retry.

`actions` contains provisional booleans (`can_approve`, `can_reject`, `can_issue`,
`can_complete`, `can_revoke`, `can_review_penalties`); controls still need reason,
current versions and evidence. Backend checks run independently. Clearance tasks
have their own `can_decide`. Do not infer an action from a role string or READY.

## Smallest team integration test

First connect own institution read → linked obligation coverage using one actual
Y1 instrument and the K1/K2 session/client. Compare its result with a known S2
synthetic label. Deny the second institution and prove no false zero when the
source adapter fails. Only then connect request → parallel clearances/penalties →
independent authority → issued unsigned letter → separate completion → minimal
public issued/revoked view. Tests must cover allowed, denied, invalid, stale,
rollback/file cleanup and unknown facts against the merged stack. Local tests with
fake trusted ports are evidence for our implementation, not that merged test.
