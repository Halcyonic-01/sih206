# Two-day semifinal upgrade: priorities 2–4

Status: implementation plan only. No product implementation authorized by this document.

Here P2, P3 and P4 mean priorities 2–4 in the semifinal upgrade list, not the earlier P1–P9 implementation phases.

## Outcome and scope

Deliver one stronger evidence-review journey, an honestly measured synthetic AI demonstration, and a reproducible semifinal build within two days. Preserve the current Django/React architecture, manual review, draft-policy labels, existing records and AI-off operation.

Owners: Saksham owns P2 (clearances); Yash owns P3 (extraction evaluation); Kushagra owns P4 (build and platform verification). Each person changes their own area. Shared contracts need agreement before implementation. No automatic approvals, bank integration, digital signatures, new cloud infrastructure or policy redesign in this scope.

## Inspected starting point

- `casework/services.py::decide_clearance` already enforces assigned-unit access, pending/open state, optimistic version checks, a reason, an evidence reference and an audit event.
- `casework/adapters.py::clearance_evidence` currently validates reference syntax. It does not establish that a protected supporting PDF was inspected.
- Clearance persistence is actually in `obligations/case_models.py`, imported through `obligations.models`; there is no `casework/models.py` in this checkout. Any additive model migration belongs to `obligations`.
- The clearance queue in `frontend/src/features/saksham/releases.tsx` currently has shared reason/reference inputs above the cases. It has no case-specific evidence picker.
- `portal.models.Document` and `portal/uploads.py` already supply document metadata and the shared bounded PDF validator. Reuse their existing interfaces; do not copy the parser or expand another owner's permissions independently.
- `ai/management/commands/evaluate_extraction.py` explicitly evaluates one seeded synthetic scan and reports field checks. It is a smoke check, not a representative extraction benchmark.
- `run.ps1`, `scripts/run_portal.py`, `scripts/review_check.py` and the review-build documentation already provide installation, startup, seeding and smoke checks.
- The local tree contains earlier uncommitted regression fixes and the newly tested explicit-sign-out navigation fix. Preserve and distinguish those changes from this upgrade.

## First checkpoint: agree the small shared contract (30–45 minutes)

All three teammates confirm these items before building adapters:

1. A clearance PDF belongs to one case and one unit. Which roles may read it? Proposed default: its assigned unit, officer and authority; deny institutions and other units unless explicitly agreed otherwise. Confirm the auditor policy separately.
2. Reuse `Document` only if its existing upload/download permissions can express that narrower scope without weakening access. Otherwise Saksham adds a small case-owned evidence model and protected endpoints, reusing Yash's PDF validator unchanged. Choose one storage route, not both.
3. New decisions carry `version`, `status`, `reason`, `evidence_ref` and `evidence_id`. Evidence metadata exposes identity, filename, page count, hash, uploader and upload time. Decision metadata exposes reviewer and decision time.
4. A legacy reference stays visible as “Reference only — no linked PDF.” Do not fabricate evidence for old decisions. Agree whether historical pending cases need re-attestation before a new authorization; existing completed cases must not be rewritten.
5. AI fixtures are synthetic only. Live provider evaluation requires explicit approval to send those PDFs externally; the rest of the benchmark and fallback demonstration stays offline.

Record decisions in a short contract note with owner approval. Unresolved contracts block only the dependent work, not fixture preparation or isolated tests.

## P2 — Evidence-backed clearances (Saksham, approximately 7–9 hours)

### P2.1: smallest end-to-end slice — one PGRC PDF and one decision

1. Add the agreed evidence link/storage model in `obligations/case_models.py` and an additive `obligations/migrations/<next>_...py`. Inspect the latest migration graph before choosing its number. Use protected relationships; retain old references.
2. Add evidence validation and linking in `casework/services.py` / `casework/adapters.py`. Validate case, assigned unit, PDF parse result and decision eligibility server-side. Never trust an evidence ID alone.
3. Extend `casework/api.py` and `casework/api_urls.py` for the agreed upload, listing and protected viewing contract. Keep views thin. Use existing upload limits, errors and access logging.
4. Extend the owned client/types and `frontend/src/features/saksham/releases.tsx` with case-specific PDF upload/selection, filename, page count and protected viewing. Keep controls attached to the selected case so one case's evidence cannot be accidentally submitted for another.
5. Preserve explicit decision submission: selecting or opening a PDF never clears a task. Require the reason, reference and evidence selection before the reviewer records the decision.

Success: an assigned PGRC reviewer uploads a valid synthetic PDF, opens it, records a decision, reloads, and sees the same linked evidence, reviewer, reason and timestamp. An unrelated unit cannot view or use that PDF.

### P2.2: complete the three-unit integration

- Apply the same implementation to PGRC, Vigilance and Grants; no separate workflow copies.
- Add a decision timestamp if absent. Keep the existing sealed audit path and record stable evidence identity/hash in the audit detail using established conventions.
- Show evidence beside clearance decisions on the release case page, only for authorized readers.
- Tighten readiness for newly recorded clearances so a typed reference alone cannot satisfy evidence-backed clearance. Apply the agreed legacy-case policy explicitly; never silently promote legacy references to document evidence.
- Keep document parsing distinct from authenticity: labels say uploaded/readable and reviewed, never bank-verified.
- Coordinate any new notification template or platform permission helper with Kushagra; do not introduce it independently.

### P2 acceptance tests

Add focused cases in Saksham-owned backend tests, owned component tests and a new release-clearance browser spec:

| Test | Exact expected result |
|---|---|
| Valid PDF and assigned unit | Upload accepted; protected view returns a valid PDF; decision and evidence survive reload. |
| Missing evidence/reason, invalid ID or wrong case/unit | Invalid input rejected with the agreed 400/403/404 response; no decision/version/audit mutation from a rejected decision. |
| Institution or unrelated unit access | Cannot upload, read or cite private clearance evidence; foreign-resource lookup follows the agreed non-disclosure convention. |
| Stale version / concurrent decision | One decision succeeds; stale write returns 409; no duplicate decision or evidence reassignment. |
| Invalid, encrypted, oversized or active-content PDF | Rejected by existing validation; no usable evidence row or leaked/orphan file. |
| Storage/database failure | Controlled failure; task remains undecided; rollback/cleanup verified with fault injection. |
| Reference-only legacy task | Clearly labelled; behaves according to the agreed compatibility policy; no invented PDF link or historical edit. |
| Three clearances and authority review | Evidence is inspectable; prerequisite gates still apply; only authority can authorize; completion remains a separate action. |

Upload alone may create an evidence item, but must never count as a decision. Decide whether uploads participate in case-version changes in the contract, then test that behavior.

## P3 — Labelled extraction evaluation (Yash, approximately 5–7 hours)

### P3.1: dataset first

Create 12 small synthetic PDFs with a machine-readable manifest, expected values and expected source pages:

- 4 clean text PDFs with varied layouts, dates and amount formats.
- 3 legible scanned PDFs at varied quality/rotation.
- 2 PDFs with declared values intentionally different from document values.
- 2 PDFs with missing or ambiguous fields; expected extraction must abstain or explicitly flag uncertainty.
- 1 unreadable scan; expected result is a safe unavailable/needs-review response.

Keep malformed/encrypted/active-content files in upload-rejection tests, outside the extraction accuracy denominator. Have a second teammate manually verify labels. Reserve 4 documents as a held-out synthetic subset before prompt tuning; identify tuning and evaluation subsets in the manifest.

Suggested files: `fixtures/ai-evaluation/manifest.json`, generated PDFs with synthetic markings, Yash-owned generation helpers, and `docs/ai-extraction-evaluation.md`. Names are proposed; reuse an existing dataset folder if present.

### P3.2: extend the existing evaluator

Extend `ai/management/commands/evaluate_extraction.py` and its tests instead of creating another extraction engine. Preserve the current smoke-check interface. Add proposed options `--manifest`, `--output` and `--subset`; these options do not exist yet and must not be advertised as runnable until implemented.

Measure separately for OCR and configured AI:

- Normalized exact-match accuracy per field and document, with all denominators.
- Wrong extracted values, omitted expected values and invented values for absent fields.
- Page-reference accuracy; an unsupported page/value is a failure, not partial evidence credit.
- Mismatch-finding precision = TP/(TP+FP), recall = TP/(TP+FN), plus raw TP/FP/FN counts. Define negatives and true mismatches in the manifest. Report N/A for undefined ratios.
- Success/abstention/failure counts and end-to-end latency per document. Separate cold runs, cached responses and live service runs; report sample size and median/range rather than implying production performance.

### P3.3: controlled demonstrations and gates

- Correct extraction → original page visible → human chooses whether to use values.
- Intentional mismatch → advisory finding with supporting value/page → officer reviews it.
- AI disabled, timeout, rate limit or malformed output → safe explanation and manual workflow remains usable.
- A document containing instruction-like text is treated as data; it cannot trigger tools, decisions or permission changes.
- Keep all live calls logged in the existing AI run mechanism and retain model/config identity without secrets.

Acceptance: every manifest entry is validated and processed or explicitly classified; deterministic matching/scoring and fallback tests pass; results and failures are written without selective exclusion. Recommended demo gate: all preselected clean-demo fields and evidence pages are correct on the recorded rehearsal run, all controlled mismatch cases are detected, and no sample bypasses human approval. Report the broader measured results even if weaker; disable the AI demo if its selected case is unreliable. This dataset is synthetic and too small for regulatory or general accuracy claims.

## P4 — Semifinal build and platform verification (Kushagra, approximately 5–7 hours)

### P4.1: establish a safe candidate

- Preserve local work, review diffs and keep secrets, generated credentials, private planning PDFs, local databases and build outputs out of Git.
- Verify the current candidate rather than assuming the earlier 670-test result applies after P2/P3. Record candidate commit IDs and any uncommitted changes.
- Use an isolated synthetic database/media directory and local email catcher/console. Do not seed, migrate or send notifications against the shared database during rehearsal.
- Include the authorized sign-out fix and earlier test fixes in the candidate through reviewed changes; do not silently discard them when updating branches.

### P4.2: automated verification

Run from the repository root with the project virtual environment and a verified isolated configuration:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test portal.tests
.\.venv\Scripts\python.exe manage.py test
Push-Location frontend
npm ci
npm test -- --maxWorkers=2
npm run build
# Only with Playwright pointed at the disposable server and generated test credentials:
npx playwright test
Pop-Location
```

These are planned verification commands, not claims that new changes pass. Run backend suites with SQLite unless a dedicated disposable PostgreSQL test database is explicitly configured. A normal passing SQLite run does not demonstrate PostgreSQL compatibility.

After the candidate is committed, run `python scripts/review_check.py` from the candidate checkout. Its fresh-install step packages committed HEAD; it does not include uncommitted fixes. Review the script's environment inheritance before running it and isolate DATABASE_URL, media paths and email configuration. Use the existing `run.ps1 --smoke` / `scripts/run_portal.py --smoke` flow rather than a new launcher.

### P4.3: browser, notifications and offline rehearsal

1. Confirm `/api/health/`, `/login`, sign-in and protected PDF viewing on the target laptop/browser.
2. Open Deposit records → sign out → sign in as the same account: main page opens. Repeat with a different role; no prior-user data remains. Separately expire a session and verify its permitted return destination.
3. Test institution A/B separation and PGRC/Vigilance/Grants unit boundaries, including direct PDF URLs.
4. Complete the fresh evidence-backed clearance journey, officer review, independent authority decision, unsigned letter and evidence-backed completion. Check audit integrity and protected download access logs.
5. Verify notification enqueue, local delivery capture, failed-delivery retry and duplicate suppression. A console/catcher result is not proof of real SMTP delivery.
6. Restart the application and confirm saved evidence, decisions and account access persist.
7. Disconnect networking only after dependencies and browser assets are installed. Run the built app, PDF viewer, manual review and reports. AI external calls may fail visibly; the manual path must complete. Reconnect and verify recovery. Use labelled saved AI screenshots/results only as a fallback, never as a live response.
8. Check phone-width navigation, keyboard access, loading/empty/error states and double-submit protection in the changed screens.

Acceptance: no critical workflow, permission, migration or data-integrity failures; regression and target-browser checks pass; fresh candidate setup succeeds; offline manual demonstration succeeds. Failures stay in the release report with owner and disposition. Do not weaken tests/security to pass the gate.

## Two-day sequence and merge checkpoints

| Window | Saksham | Yash | Kushagra |
|---|---|---|---|
| Day 1, first 45 min | Agree evidence contract and compatibility policy | Agree manifest/metrics | Confirm access and disposable environment contracts |
| Day 1, next 3 hours | PGRC vertical slice and focused tests | Dataset and independent label check | Candidate baseline and startup/account checks |
| Day 1, next 3 hours | Three-unit UI, scope and readiness integration | Evaluator, scoring and fallback tests | Notification/fresh-install checks; report platform defects |
| Day 2, first 2 hours | Fix P2 verified defects and review migration | Run approved evaluation; report outcomes | Integrate reviewed branches on a candidate; run regressions |
| Day 2, next 2 hours | Joint evidence/release rehearsal | Correct/mismatch/fallback rehearsal | Browser, PDF, offline and restart rehearsal |
| Day 2, final 2 hours | Freeze code; update demo | Freeze dataset/results | Final candidate checks and fallback copy |

Times are estimates with work happening in parallel, not a promise. Use reviewed PRs and the team's current agreed merge process; this plan does not authorize pushes or merges. Freeze feature work at least two hours before the final rehearsal. If behind, cut extra AI samples/layout polish first; never cut evidence scope checks, validation, human decision gates or final verification.

## Deliverables and stop conditions

- P2: one protected case/unit evidence link flow; additive migration; documented compatibility policy; API, component and browser coverage.
- P3: labelled synthetic corpus, repeatable evaluation, raw results and limitations; correct, mismatch and failure demonstrations.
- P4: candidate inventory, reproducible setup, actual test logs, browser/offline checklist, clean fallback dataset and startup procedure.
- Shared final note: real versus simulated behavior, remaining defects and exact demonstration accounts/files (credentials remain private).

Stop release if any private PDF is exposed across roles/units, a stale decision overwrites another, required evidence can be bypassed, the manual workflow depends on AI availability, migrations lose records, or a fresh setup cannot start. Cosmetic defects and broader production hardening may be documented and deferred.

No new feature implementation or test run was performed to create this plan. The most recent pre-plan frontend verification was 123 passing tests and a successful build; the first full run had one session-expiry timing failure that passed unchanged on rerun. Historical backend/browser results are documented separately and must be rerun against the upgraded candidate.
