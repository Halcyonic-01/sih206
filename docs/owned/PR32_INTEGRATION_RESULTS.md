# PR #32: integration with main

27 October 2026. Branch `s/semifinal-p2-p4`. Integrates main `33abab4` (PRs #24–#30) into the existing Hindi/semifinal branch. This is a feature-branch merge, not a merge of the pull request into main.

## Resolution and preservation

- `frontend/playwright.config.ts`: retains main's CI retries, HTML report, failure artifacts and optional Chromium executable; accepts both `PLAYWRIGHT_BASE_URL` and `PORTAL_URL`, in that order.
- `RecordDetail.tsx`: retains main's per-field provenance, original values and source warning alongside Hindi labels, help and the existing evidence/release controls. Known provenance labels/tooltips translate; unknown source text stays original.
- `records.spec.ts`: adopts main's shared sign-in/search helpers and per-test output paths; preserves the filtered-response wait, reconciliation loading wait and explicit disabled AI/OCR assertions.
- Main's document encryption, checksum verification, holder/lien checks, PostgreSQL append-only triggers, operational runbooks, dependency pins and platform launch scripts are retained. No existing migration is rewritten.
- Added Hindi display for main's new integrity-failure notification, including unchanged record/file placeholders and stored history. Added a regression for toggling provenance labels without changing record data.
- Updated main's release browser scenario to upload, select and view each unit's supporting PDF before its decision; reference-only decisions cannot satisfy the new release gate.
- Integrated the new Hindi/semifinal browser specs into main's browser CI job using explicit synthetic-data paths and AI/OCR-off fallbacks. The existing launcher and other CI jobs remain. The rehearsal seeder accepts `--confirm-disposable` outside its dedicated profile only for DEBUG SQLite; non-DEBUG and PostgreSQL are refused, with tests.

## Verification

Checks use SQLite and synthetic documents, never the private remote database.

- Focused clearance/encrypted-storage/notification/schema/seed-guard integration: 19 passed, 13.039 seconds.
- Complete backend regression: 729 tests, OK, one optional native-OCR skip, 406.258 seconds.
- Complete frontend unit/component regression: 135 passed in 16 files, 127.97 seconds.
- Complete Chromium regression: 15 passed, approximately 1.5 minutes, on a new isolated database. Includes PS institution/release/report/auditor scenarios, records/correction/acceptance/renewal, language persistence and form preservation, mobile/keyboard navigation, notifications, scope and sign-out. The separate semifinal release test blocks non-loopback networking.
- TypeScript/Vite production build: passed.
- Translation coverage: 557 explicit keys, 730 catalog entries; passed.
- Django system check, migration consistency, strict OpenAPI validation and dependency consistency: passed.
- Production-profile deployment check with ephemeral test secrets/encryption key: passed (existing two silenced checks retained).
- Fresh isolated database migrations: applied, including `audit.0002` and `obligations.0008`.

The first focused attempt used the rehearsal profile, whose relocated BASE_DIR is incompatible with the schema test's source-tree subprocess; the standard test settings were used afterward. A sandboxed run encountered Windows temporary-directory cleanup denial and was restarted with normal temporary-file access. The first full run then exposed the missing local cryptography dependency (two errors); installing the existing pinned requirements resolved the environment gap. The added encryption test initially supplied raw form strings directly to a service; it now supplies the service's typed values. An initial browser run passed 14/15; the OCR selector matched both title and description, and was corrected to assert each separately. No tests, validation, permissions or timeouts were disabled to obtain a pass.

Local logs/databases/screenshots and one-off test settings remain private in ignored `data/`, `planning/` and untracked `tmp/`; none are part of the PR. Normal `.env`, credentials and the recorded port-8011 demo database were not modified. The temporary browser server uses port 8013.

## Limits

- Local browser tests use Chromium on Windows and synthetic SQLite data. Hosted CI, Docker, PostgreSQL trigger behavior and physical offline-laptop rehearsal are not claimed by these checks.
- Optional native OCR is unavailable locally. No new live AI evaluation was performed in this integration task.
- Hindi declarations still need fluent human review. Exports, email, source documents and free-form data retain their original language.
- Main's encrypted filesystem storage protects `Document.file` when configured. Clearance-evidence and issued-letter BinaryFields remain database blobs; this integration does not claim application-level encryption for those blobs. Their scope and integrity checks remain enforced.
- Synthetic confirmations are still labelled simulated, letters remain unsigned, and consequential decisions remain human actions.
