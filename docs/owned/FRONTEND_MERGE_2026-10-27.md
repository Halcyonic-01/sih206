# Updated frontend integrated with local semifinal work

27 October 2026. Local branch: `s/semifinal-p2-p4`.

## Sources and preservation

- Latest fetched main: `9c16f59`, PR #23, including the updated frontend and API schema documentation; also includes PR #22's README rewrite.
- Local semifinal source was saved first in checkpoint commit `d2433b4`. Private planning files, `.env`, databases, credentials, generated builds, `output/` and `tmp/` were excluded.
- Integration is local. No GitHub push, PR merge, force-push or remote branch change was performed. The local main pointer was not changed; the working feature branch incorporates the remote main history.

## Visual design preserved

The following match `origin/main` exactly in Git's content comparison: horizontal shell, masthead/footer, logo/image, theme, both stylesheets, home page, shared page headings, frontend entry HTML and public release-page layout. The updated login markup is also preserved; its only difference from upstream is a comment explaining intentional sign-out behavior.

Our retained behavior includes the session sign-out destination fix, case-specific protected clearance PDFs, per-unit access, evidence review and timestamps, advisory extraction fixes/evaluation, and isolated rehearsal setup. The shared PDF viewer retains a backward-compatible optional download path for clearance evidence; ordinary deposit PDF links keep their existing default.

## Conflicts and integration gaps resolved

1. `casework/api.py`: kept the upstream schema annotations alongside our evidence endpoints, scoping and safe storage-error responses.
2. `scenarios/tests/test_ps_review_fixes.py`: kept both the upgraded release scenario's real supporting-PDF uploads and the PDF download header assertion with guaranteed immediate response closure.
3. `frontend/tests/records.spec.ts`: retained upstream navigation, search-response waiting and precise page-header assertions; preserved our AI/OCR-off fallback checks and commit-button loading wait. Screenshots now stay in the workspace's ignored planning/browser-results directory.
4. The new schema now documents evidence metadata, multipart upload, protected PDF download, and required `evidence_id` on clearance decisions. Evidence operations have explicit unique IDs. A contract test checks the required field, binary upload and authenticated download.
5. README and API documentation describe the integrated evidence flow rather than reference-only decisions. The teammate's visual design was not rewritten.

## Verification

- Frontend tests: **127/127 passed**, 14 files.
- TypeScript and production Vite build: **passed**.
- Strict OpenAPI generation (`spectacular --validate --fail-on-warn`): **passed with no warnings/errors** after fixing the evidence list/download operation-ID collision.
- Schema contract tests: **4/4 passed**.
- Chromium browser suite: **7/7 passed**, 50.4 seconds. Includes new horizontal categories, keyboard/phone navigation, role filtering, records/corrections/renewal, reconciliation, institution separation, notifications, the full PDF-backed release journey with external traffic blocked, and sign-out to the next account's main page.
- Desktop dashboard and mobile clearance screenshots: visually inspected.
- System check, migration consistency and whitespace check: **passed**. Existing obligations migration 0008 is already applied in the isolated rehearsal database; no new migration was needed for this merge.
- Full backend regression: **687 tests, OK (1 skipped), 377.137 seconds**. The optional native OCR integration test is skipped because Tesseract is unavailable. Log: `data/merged-final-backend.log`.

The initial strict-schema attempt caught an operation-ID collision and was corrected before the passing schema tests. No existing test was skipped or disabled to obtain a pass.

## Local application and remaining limits

The merged frontend is built and served on `http://127.0.0.1:8011/login` using `config.rehearsal_settings`. This is the separate synthetic database, not the normal app's database. Standard setup/evaluation details remain in `docs/owned/SEMIFINAL_UPGRADE.md`.

No private environment file, normal database or existing password file was changed. The previous synthetic AI evaluation was preserved, not rerun during this frontend integration. Its missing-Tesseract and rate-limit limitations still apply. Physical-laptop disconnected-network checks, independent label review and teammate review before publication remain as documented.
