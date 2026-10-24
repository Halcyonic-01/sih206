# Owned S1–S6 verification — 24 October 2026

Baseline: local `d36720a`, clean working tree, existing requirements and planning
files inspected. This is local development, not a remote-main/PR merge check.
Nothing was pushed, deployed publicly, sent to teammates or sent to an AI service.

## Actual results

| Check | Observed result |
|---|---|
| Pre-change full Django baseline | 347 passed, 42.725 seconds |
| Focused new owned API/services + casework tests | 31 passed, 5.207 seconds |
| Final full Django suite | **378 passed, 62.573 seconds** |
| Separate original portal suite | **159 passed, 48.937 seconds** |
| Isolated TypeScript compilation | Passed using TypeScript 7.0.2 and React 19.3 types |
| Isolated React component tests | **11 passed**; no browser execution claimed |
| Django default/integration-harness checks | No issues |
| Migration drift | No changes detected |
| Live additive migrations | obligations 0002–0006 applied; portal migrations unchanged |
| Preserved S2 corpus | 76/76 passed |
| Preserved S3 fixture gate | 19 passed, seven calculations, one expected rejection, zero queries |
| Preserved S4 CSV/KPI corpora | 7/7 and 10/10 passed |
| Preserved S5 corpus | 40/40 passed; prior labels SHA-256 unchanged |
| Preserved S6 fixture gate | 53 passed; 33 S5 comparisons, zero queries |
| PDF generation | Real unsigned synthetic PDF generated, parsed with pypdf (one page and expected text), rendered with Poppler and visually inspected |

The tests overlap; do not add their counts as independent scenarios. The 31 new
backend tests use real owned DRF views/services, temporary files and isolated test
databases. Tests for release source/membership/parser interfaces explicitly inject
fake trusted ports. They are not evidence that Y1/Y2/K4/K5 integrations are present.

Local logs: ignored `data/owned-*.log`. Sample letter and rendered PNG are ignored
`data/owned-letter-preview.*`; its QR points to a fictional demo.invalid URL and
does not identify a real issued record. Poppler emitted a Symbol-font warning;
the rendered page was legible, with no observed clipping. A target-browser PDF
or physical QR scan is not claimed. No legal signature or bank confirmation exists.

## Tests and defects resolved during implementation

- Master create/update/child operations: scope, roles, invalid fields, stale/replay,
  uniqueness, audit rollback, non-coerced boolean/text inputs and CSRF.
- Missing Y1 linkage: unavailable coverage, not a falsely empty ledger/zero shortfall.
- Import: preview/commit, source hash and identity freshness, expiry, owner/role,
  replay and injected failure midway through import; no partial institution/audit rows.
- Reports/KPIs: report kinds/scope, exact string cells for formula-looking input,
  unknown confirmation share, and the earlier pure arithmetic regression corpora.
- Release: default missing adapter leaves no partial request, scope and renewal
  conflicts, independent authority, open-clearance/proposed-penalty blocking,
  explicit penalty confirmation/review, stale versions and rules, approval monitoring,
  PDF/storage/audit rollback, minimal issued/revoked lookup, frozen public institution
  identity, protected downloads, rejection and separate new-evidence completion.
- A complete request → unit clearances → penalty review → authority approval →
  letter → completion journey passed through actual owned API views using synthetic
  test ports. Public response had only the proposed five allowlisted fields.
- Existing legacy decision/completion services cannot bypass gates for extended
  requests; old unextended requests retain their original behavior.
- UI: exact paise/nulls, permission-controlled buttons, missing questionnaire,
  identity response races, failed-service/no-fixture fallback, ignored mutation
  projections, public revocation/errors and no unspecified KPI-cohort fetch.

Initial new-test/implementation failures were fixed and rerun: the test URL harness
needed preserved legacy routes; existing middleware adds more no-cache directives;
Django enum values required plain-string conversion at the strict evaluator boundary;
an invalid test-only rule mutation used the wrong key; current TypeScript requires
Node16 resolution; and a frontend action payload incorrectly sent instrument_version
to actions that accept only case version. No old tests or source labels were skipped,
disabled or changed to manufacture passes.

## Preservation and local database upgrade

Before live migration, SQLite's backup API saved a private snapshot under ignored
`data/backups/before-owned-*.sqlite3`. `data/owned-preservation.json` records original
table columns/row hashes and document hashes. Every original table row/account/
credential value and every original private PDF hash remained unchanged. No live
new release case or import preview was created by verification.

The first comparison incorrectly treated any additional row as a preservation
failure. Inspection found only expected Django metadata additions: six content types
and 24 permissions for the six new models. Every original row was intact. The
corrected check compared original rows by primary key, allowing only those metadata
additions; it passed again after the final migration. New version columns default to
1; no obligation, exemption, policy approval or financial state was inferred.

Do not automatically overwrite a database to roll back. Stop processes and inspect
the saved backup/current state before a separately authorized restore. Keep private
documents with the matching database. The upgrade never modified those files.

## Integration gaps and release decision

This is **implemented and locally tested against provisional interfaces**. It is
not the merged S1–S6 product, production-ready, or a completed browser demo.

Remaining blockers are explicit in [CONTRACTS.md](CONTRACTS.md): K1 routing/auth/error
normalization, K2 client/routes/layout/viewer, K4 real scopes/unit membership,
K5 actual outbox, Y1 holding link and Y2/Y3 parsed typed documents, real source
adapters owned by Saksham, canonical questionnaire and policy decisions. New APIs
are mounted only with the opt-in integration harness. Missing adapters fail closed.

S4 report subsets explicitly state missing independent-verification, typed-document,
SLA, discrepancy and obligation-intervention adapters. KPIs do not fabricate Y6
confirmation events. Return-for-correction/reopening, waiver powers, penalty
settlement, publication/exemption decisions, production signatures and S7 are not
implemented. Notification configuration is not proof of delivery.

Still required: cross-team merged API/contract tests, real concurrent-writer tests,
document-version substitution/freshness checks using actual metadata, target-browser
end-to-end and PDF behavior, mobile/keyboard/screen-reader review, security/dependency
audit, export scale, preview retention/cleanup policy, public-token log/rate-limit
review, new-feature offline packaging/rehearsal and production operational controls.
No performance, extraction accuracy or improvement percentage is claimed here.
