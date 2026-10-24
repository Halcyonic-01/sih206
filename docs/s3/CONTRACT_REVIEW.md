# S3 contract review

Reviewed 24 October 2026 against the local S1/S2 checkpoint `3888ec4`,
`obligations/models.py`, `calculations.py`, `checks.py`, `portal/models.py`,
`config/urls.py`, and [S2's API proposal](../../obligations/API_ACCEPTANCE.md).
This is a gap record, not an approved API schema or a live-main inspection.
No shared contract or teammate implementation was changed.

## Screen-to-source mapping

| S3 need | Actual source today | Missing contract / implementation | Owner / next action |
|---|---|---|---|
| Identity and profile | `portal.Institution` name/code; S1 `InstitutionProfile` fields, nullable through absent relationship | Scoped list/detail serializers, search fields, pagination and profile-null response | S2 + K1: agree read shapes and scope before UI |
| Programme rows | S1 `ProgrammeApproval`, including date, reference and both tenures | IDs, pagination/completeness, canonical programme mapping, applicable approval selection | S2: never combine every historical approval silently |
| Obligation selection and metadata | S1 `DepositObligation` supports basis/reference, rule FK, amount, dates, status and exemption evidence | Scoped obligation collection/detail response, default selection rules | S2: explicit selection; never aggregate unrelated obligations |
| Required/held/shortfall and timeline | Pure S2 `coverage()` accepts typed obligation and holding snapshots | Complete scoped instrument linkage/adapter, issue/maturity/reference metadata, eligibility explanation | Y1 + S2: reject mismatched/duplicate snapshots; no empty fallback |
| Rule provenance | S1 source/version fields; S2 frozen snapshot fingerprint and draft label | Rule context discovery/selection response; published-version and approved-policy guarantees absent | S2 + K1/K4: explicit rule context; draft only until agreed |
| Findings | `obligation_findings()` returns `Finding(code, severity, explanation, values)` | Detail assembly and final field names; fixtures carry only codes | S2: expose complete scoped values/provenance, not only codes |
| Proof review | S1 intimation date; S2 accepts explicit receipt dates | Real mapping of payment proof/Affidavit-3 receipts and page/evidence references | Y1/Y2 + S2: define document semantics; do not infer receipt from any upload |
| Actions | Fixture `presentation_actions`, next-action text/responsible party | Server-computed permission `actions` and open-action DTO; due date source and delivery state | S2 + K1; K6 only for real scheduler/delivery state |
| Calculator | Pure S2 `required_amount()` with explicit rule/profile context | POST route, CSRF, allowed input schema, rule picker/context, field errors and freshness identity | S2 + K1: POST is read-only but still CSRF-protected |
| Screen integration | Existing templates and session auth work | K2 shell, route registration/client/auth hooks absent in this checkout | K2: reuse supplied shell; no separate React project |
| Document/history navigation | Existing instrument-specific documents/audit | Institution-wide scoped history/doc aggregation and registered frontend routes | Y3/Y4 + S2: integration gap, not permission to add workflows now |

## Important presentation differences

- `rule_ref` and `institution_ref` are local fixture references. They are not API
  field names. Fixture IDs are fictional and must never be queried from live data.
- Fixture calculator `base_paise` is a list; actual S2 returns `breakdown` rows
  with programme/level/base amount. A future agreed adapter must preserve that
  attribution. The validator checks these amounts against S2.
- Fixtures omit obligation `basis`/`basis_reference`, approval IDs, instrument
  display references, full finding `values`, and document/history rows. These
  screens are not ready for implementation simply because 19 fixtures pass.
  Add synthetic examples for these fields only after the response mapping is
  agreed; use an explicit unavailable label when legitimate source data is absent.
- `recorded_administrative_status` is presentation naming for S1 `status`.
  Calculator results and empty findings must never set it to MET or EXEMPT.
- S1 has no `publication_status` field; fixture UNAPPROVED is a synthetic label,
  not an implemented publication lifecycle. Fingerprints freeze calculation
  context, not the underlying editable database rule row.
- `coverage()` returns `holding_ids` for eligible holdings today, not all timeline
  rows or a historical audit. Timeline dates must come from complete scoped
  snapshots; `term_gap_days` counts remaining term from the first break.
- An unavailable adapter retains known required amount but leaves ledger-derived
  values null. Unknown requirement plus known empty ledger can show held zero.
  Those two states must have different presentation.

## Decisions still required before integration

| Decision | Current safe position | Agreement needed |
|---|---|---|
| Envelope, slash convention, search and pagination | Existing API proposal only | K1 + S2; freeze exact response and field-error schema |
| Auth / object disclosure | Cross-tenant and missing object generic 404; forbidden visible action 403 | K1 auth status and scope helpers; fixture statuses are hints only |
| Integer money | Python integer paise; fixtures fit JS safe range | K1 + S2: safe wire range or lossless encoding for larger S1 values |
| Date overrides | Visible fixed synthetic date in fixtures | Server business date normally; agree DEBUG-only demo override |
| Calculator freshness | Discard preview when any input/context changes | Define rule/profile context identity and conflict behavior; do not invent a wire version |
| Missing assessment context | S2 proposes 409 with unavailable reason | Agree whole-response versus partial assessment envelope and retry rules |
| Actions and navigation | Text-only placeholders, no guessed instrument links | K2 registered paths and server action names |
| Master writes | No S3 edit/create screens in current spec | S2 version fields/entity audit prerequisites remain separate work |
| Policy | DRAFT_DEMO_NOT_APPROVED only | Decisions remain open in [policy log](../../obligations/POLICY_DECISIONS.md) |

F14 in the private plan also mentions documents and history. They require the
scoped integrations above; public NOC verification belongs to S5/S6, not this S3
preparation. No API, authorization, browser, accessibility or end-to-end pass is
claimed here. Fixture validation proves internal consistency only.

## Smallest next implementation after agreement

1. Confirm K1/K2/Y1 availability and agree the response mapping above.
2. Complete and test S2's real scoped reads/calculator/holding adapter.
3. In K2's existing shell, implement only institution list -> one selected detail
   obligation; check loading/empty/error and cross-tenant denial through real HTTP.
4. Add timeline and calculator using that tested contract; execute UI-01--UI-14.

This sequence is a proposal, not authorization to implement these steps now.
