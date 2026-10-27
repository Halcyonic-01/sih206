# Semifinal priorities 2–4: implementation and verification

27 October 2026. Local branch: `s/semifinal-p2-p4`. No commit, push, PR or merge was performed. Local main remains at `a1b990b`; fetching origin for migration inspection did not merge its README update. Earlier local regression and sign-out fixes were preserved.

## Requirement matrix

| Priority | Implementation | Verification / limits |
|---|---|---|
| P2: protected clearance PDFs | New append-only evidence model, additive obligations migration 0008, atomic upload, case/unit linking and hash checks | Real parser and API/service tests; protected PDF viewing in the real browser. |
| P2: reviewer, reason and time | Explicit decision links a selected PDF with actor, timestamp, reason and file reference; audit snapshots include evidence hash | Reload and stored audit assertions; authority sees supporting PDFs before its separate decision. |
| P2: private access and stale writes | Scoped case lookup, assigned-unit writes, officer/authority reads, denied institutions/other units; optimistic version checks | Allowed/denied/invalid/stale, rollback, anonymous access and failure tests. |
| P2: preserve historical work | Existing references/timestamps not invented; pending reference-only decisions require re-attestation; completed cases untouched | Legacy-state test; new real-adapter release scenario uploads evidence. |
| P3: labelled corpus | Twelve synthetic CC0 PDFs, fixed four-case held-out subset, manifest values/pages/hashes and mismatch labels | Manifest/scoring tests and visual page inspection; independent human label review remains. |
| P3: evaluation and fallback | Extended existing evaluator; raw results, per-field metrics, mismatch scoring and timing; AI/OCR remain advisory | Approved live synthetic calls, offline text baseline and unavailable OCR recorded separately. |
| P3: verified defects | Reject unsupported values without pages; separate document-extraction quota from other AI operations | Regression tests; final live run after the quota-collision fix. |
| P4: reproducible build | Disposable settings, setup command, source-only fresh-install verifier using existing launcher | Dependencies installed from pinned files; build, migrations, seeding, login, notification API and audit smoke pass. |
| P4: workflow/offline/browser | Existing record tests plus complete release, three clearance PDFs, letter, completion and sign-out tests | External requests blocked while loopback allowed; manual workflow completes. Physical Wi-Fi disconnect / target laptop remains a human check. |
| P4: recovery and notifications | Private synthetic backup, restored audit verification, in-memory delivery, reminder idempotency | SQLite integrity and foreign keys pass; 9 PDF hashes and 3 completed cases in that checkpoint backup; no secrets copied. |

## Actual checks

- Unchanged baseline outside the sandbox: 41 backend tests, OK, 1 skipped. The sandbox attempt failed on subprocess/temp-file restrictions; it was not used as an application-quality result.
- P2 initial focused run: 27 passed, 1 assertion failure because secure cache headers contained additional directives. Corrected the assertion to require `no-store`; 28/28 then passed.
- Latest focused real-adapter/scoping/AI run: 41 tests, OK, 1 skipped. Includes safe API storage/logging failures and the new PDF-backed release journey.
- Pure scoring rerun after correcting failure credit: 5/5 passed. Unavailable responses no longer receive exact-match credit for unknown labels.
- Frontend: 125/125 passed, 13 files. One earlier existing session-expiry test raced lazy-route mounting; it now delivers its actual shared-client 401 response after the route mounts, preserving the same redirect assertion and timeout. No test disabled.
- TypeScript and production build passed after fixing typed mock arguments in the new UI test.
- Chromium full regression rerun: 6/6 passed in approximately one minute. Includes records/corrections/renewal, reconciliation/mobile records, institution isolation, notifications, full release evidence and account switching.
- Initial six-test browser run: 5 passed, reconciliation timed out because the loading icon changed the commit button's accessible name. The test now waits for preview loading to finish and then commits; focused reconciliation rerun passed before the six-test rerun.
- Additional phone-width clearance run: 2/2 passed at 390 px, with no page-wide horizontal overflow; synthetic screenshot retained in ignored planning/browser-results.
- System checks and migration consistency: pass. Production-profile deploy check passes with explicit HTTPS/security settings and a temporary random secret. The intentionally HTTP/debug rehearsal profile has five expected deploy warnings; it is not an internet deployment.
- Fresh dependency install and smoke: pass. Final source refresh and smoke recheck: pass. Source hashes and installed candidate are private under `data/semifinal-installs/178cd95fe1d0`.
- Audit checkpoint after the first release: 137 sealed events, 0 unsealed, verified. Restored backup checkpoint: 179 sealed events, 0 unsealed, verified.
- Notification checkpoint: 56 deliveries processed through the in-memory backend, 0 failed. This is not real SMTP delivery. Reminder check: 147 before, 153 after first historical run, 153 after the identical second run (0 duplicates).

Final full backend rerun: **683 tests, OK (1 skipped), 500.637 seconds**. The skip is the optional native OCR integration check because Tesseract is unavailable. The preceding full run executed 682 tests with one failure in the older reference-only release test; that test was updated to perform real evidence uploads and passed in both focused and final full runs. The backend regression gate passes; the skip is not counted as a pass.

Additional finalized browser assertion: supporting PDFs must finish rendering (spinner removed), not merely allocate a canvas. The desktop/390-px release and account-switching rerun passed 2/2 in 33.3 seconds. The mobile screenshot was inspected. Final active rehearsal audit chain: 205 sealed events, 0 unsealed, verified; a new unsubmitted synthetic holding was then available for the next manual demo.

## Measured extraction outcomes

See `docs/evaluation/README.md` and the JSON reports for denominators and per-document results.

- Live AI: 10 successful responses; 2 rate-limited. 58/58 non-null predictions correct and on the correct page; 58/63 expected values recovered (92.06% recall). 60/72 exact field slots after counting unavailable responses as failures. Three labelled mismatch flags: TP 3, FP 0, FN 0. Median all-attempt latency 2,414 ms. No broad accuracy claim.
- Offline text baseline: 45/63 expected values recovered; it cannot read the three image-only scans. Deterministic mismatch TP 3, FP 0, FN 0.
- OCR: unavailable on all twelve samples because Tesseract is absent. No OCR accuracy claim.
- All twelve evaluation records remained DRAFT after extraction. Provider outputs did not approve, verify or mutate their deposit workflow state.
- The conflicting-value and unreadable AI samples hit the ten-call limit, so their provider behavior is not yet measured. The initial diagnostic report is retained and explicitly excluded from final claims.

## Security, real versus simulated behavior

Real: local session/CSRF enforcement, role and case/unit scope checks, protected validated PDF bytes, hash checks, transactional case writes, audit events, real browser PDF rendering, and approved external AI requests on synthetic PDFs.

Simulated: institutions, bank names, deposits, declarations, clearance conclusions and APH policy context. PDFs being readable does not establish authenticity. Letters remain unsigned. The app does not release bank funds.

Evidence updates/deletes are blocked at the model/service interface; a database administrator can still alter storage. Hash/audit checks are integrity checks, not a substitute for database security or external legal assurance. Existing app constraints and permission checks were preserved. No real applicant data or normal app database was used for rehearsal. No `.env`, API keys or existing password files were edited or printed.

## Startup, recovery and demo

Use `docs/owned/SEMIFINAL_UPGRADE.md` for complete commands and the updated click sequence. Start the disposable app on `127.0.0.1:8011` with `config.rehearsal_settings`; do not apply the default migration command to an unintended shared database. Synthetic passwords remain in `data/semifinal/data/*-credentials.txt`.

The backup is under `data/semifinal-backups/7dbd75d1f1e7`; it contains only synthetic rehearsal records/media/generated passwords, not `.env` or API/audit secrets. Its database and PDF hashes were validated, and a restored-copy audit check passed using the existing local key configuration. It is a local fallback, not a portable production disaster-recovery certification.

Keep the dependency cache, built frontend and synthetic PDFs installed before disconnecting networking. Use the manual workflow live if AI is unavailable. Saved AI output may be shown only as a clearly labelled recorded result.

## Remaining before presentation / wider use

1. A second teammate independently verifies the synthetic labels.
2. Run the final candidate on the physical semifinal laptop/browser with networking actually disconnected; verify PDF download and display there.
3. Obtain team review of the evidence API/migration and pending legacy-clearance re-attestation policy before sharing/merging.
4. Tesseract installation and legitimate post-quota evaluation of U02/U03 are optional follow-ups; make no unmeasured OCR/ambiguity claims meanwhile.

Shared PostgreSQL deployment, real SMTP, authentic bank integration, official APH policy approval and digitally signed documents remain outside this two-day local upgrade.
