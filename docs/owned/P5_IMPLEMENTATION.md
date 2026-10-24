# P5 — Reports, import and KPI platform integration

Implemented locally on 25 October 2026 for Saksham's S4 work. P1–P4 are
preserved. Release APIs/screens (P6 and later) remain unmounted. No shared or
teammate-owned source was edited, no migration/dependency added and nothing pushed.

## Plan and actual scope

Read `S1_S6_IMPLEMENTATION_PLAN.md` P5 and the private allocation/implementation
PDF text (S4, F6, F7, simulated imports and PS scenario 9). This connects the
existing owned services/components to the already merged K1/K2/K4 and Y1–Y6
sources; it does not create a second authentication, verification or scheduler.

| Requirement | Implementation and acceptance evidence |
|---|---|
| CSV preview and explicit commit | Normal `/api/imports/institutions/preview` multipart POST and `/{id}/commit` JSON POST; officer-only, session/CSRF protected. Existing expiring, actor-bound hash/context checks, transaction, audit and compare-and-swap retained. Tests cover no institution writes on preview, commit once, replay/stale version, another officer, invalid fields, source tampering, expiry and mid-commit rollback. Existing context freshness test also retained. |
| Five scoped reports | `/api/reports/{kind}` JSON uses shared pagination and retains the owned `rows` alias for the current page. `?download=xlsx` exports the complete bounded result. Server-side scope precedes selection; explicit access logging fails closed. Unsupported input returns the shared error envelope. |
| Pending verifications | Visible non-draft, non-released, non-superseded instruments without current-version, non-simulated `BANK_CONFIRMATION/CONFIRMED` evidence and matching persisted level. Officer review and simulated matches do not establish confirmation. |
| Upcoming maturities | Current accepted holdings maturing inclusively from the evaluation date through 90 days later. |
| Missing documents | Actual stored FDR / PAYMENT_PROOF / RPGF_PROOF metadata according to deposit mode. Presence is not authenticity or reviewed receipt timing. Release-path checklists explicitly await later work. |
| Intervention | Actual overdue current renewals, unresolved blocking observations, persisted discrepancies, ageing corrections, submission SLA breaches, and advisory obligation shortfall/term-gap findings. Obligations without any linked holding can still appear, with a null instrument ID and an obligation reference. |
| SLA definitions | Read K6's `load_config`, business-date and working-day helpers. Submission uses strictly greater than its working-day threshold; corrections use greater than or equal to their earliest calendar-day threshold. Missing timestamps and obligation assessments appear as limitations, not invented zeroes. |
| KPI cohorts | Actual scoped audit histories for first submission → acceptance and correction cycles. Creation history must be present. Only actual current-version non-simulated bank evidence can support confirmation; declaration must appear in the creation snapshot. Incomplete histories and simulated-only verification remain unknown. No improved real-world performance is claimed. |
| Renewal KPI | The pure labeled evaluator remains available, but the runtime adapter conservatively marks renewal eligibility unknown until obligation/release policy is agreed. Acceptance alone no longer implies an obligation to renew. Known-subset/exclusion counters remain visible in the API; the UI shows unavailable rather than an invented percentage. |
| Shared frontend | Owned `/reports`, `/kpis`, `/imports/institutions` registration; existing shared transport, auth, session generation and Card layout. Import officer-only; report/KPI roles are institution, officer and authority. Other roles are conservatively denied pending an agreed report policy. |
| Review seed | Idempotent `seed_review_obligations` hook is discovered by K8's existing `seed_review`. It requires an existing unambiguous officer and creates only clearly synthetic owned masters, a draft rule and an obligation through the owned services. No account, instrument, document, verification, clearance or production-policy creation. Existing seed identities are retained; collisions fail closed. |

## Files and responsibilities

- `obligations/api_urls.py`: register only S2 and S4, never the catch-all legacy
  harness that also exposes release work.
- `obligations/api/report_views.py`: input checks, shared API/schema/pagination,
  multipart import boundary and explicit report/KPI access logs.
- `obligations/report_sources.py`: scoped bounded records, typed verification
  interpretation, real timestamps and K6 SLA configuration; read-only.
- `obligations/reports.py`: report membership, safe XLSX and actual-model KPI
  snapshots passed to the preserved pure calculator.
- `obligations/management/commands/seed_review_obligations.py`: synthetic owned
  review fixture, automatically discovered by the existing platform hook.
- `frontend/src/features/saksham/ReportPages.tsx`, `routes.tsx`, `reports.tsx`:
  shared-shell registration, role/session guards, previews, explicit confirmation,
  loading/empty/error states, exact source limitations and cohort selection.
- `obligations/tests/test_report_integration.py`: labeled actual-model snapshots,
  API/security/import rollback/export/KPI/seed acceptance tests.
- `frontend/src/features/saksham/reportRoutes.test.tsx`: shared HTTP/auth/route
  component tests; real browser verification supplements native file submission.

## Correctness fixes verified during P5

1. Replaced the old `SUBMITTED == pending verification` shortcut with current
   evidence and version checks. A stale confirmation or simulated match remains
   pending; ordinary acceptance never establishes authenticity.
2. Replaced FDR-only missing-document membership with the persisted deposit mode.
3. Replaced unavailable-source placeholders with actual obligation/SLA/discrepancy
   adapters, while keeping unresolved sources visibly partial.
4. Renewal eligibility is unknown rather than inferred solely from acceptance and
   current release state. This prevents unsupported cohort percentages.
5. Excel retains only 15 significant numeric digits. Paise are always exported
   as decimal text, including amounts inside JavaScript's safe integer range.
   Text cells, including metadata, are forced to strings. Tests round-trip both
   9007199254740993 and 9007199254740991 exactly, and preserve formula-looking
   references as text. Filter/freeze positions follow the actual metadata length.

JSON report pages use the platform pagination envelope plus `kind`, `as_of`,
`simulation_label`, `limitations`, and `rows` (alias of page `results`). The UI
uses total `count`, not the page length. XLSX contains the complete bounded set.
Reports reject more than 5000 visible instruments, or more than 5000 obligations
for intervention, rather than silently truncate. This is a demo bound, not a
production-scale performance guarantee. Stored histories/files are not revalidated
by a metadata report; retention and historical reconstruction remain separate work.

## Verification

Baseline: **59/59 passed** under normal Windows local test permissions. The first
sandbox attempt failed PDF submission/temp-directory cleanup; no product checks
were weakened to bypass Windows restrictions.

Focused final backend: **97/97 passed**, 12.381 seconds, including preserved
P2/P4 and S4 pure tests. Shared review-seed compatibility plus new P5 acceptance:
**22/22 passed** before final pagination/export changes; final focused run includes
the updated 14 P5 scenarios. CSV labeled corpus **7/7** and KPI corpus **10/10**
passed unchanged. Labels are author-labeled synthetic examples, not independently
adjudicated or measured real applicant data.

Bounded final synthetic export: **200 rows, 11843 bytes, 0.097 seconds**, including
querying actual models and building XLSX in this local test run. This is one local
sample, not a throughput or regulatory accuracy claim.

Portal regression: **200/200 passed**, 182.885 seconds. Initial full backend:
**634 run, 633 passed, one optional native-OCR skip**, 358.160 seconds. The final
backend rerun includes the completed pagination and exact-money export changes;
its result is **634 run, 633 passed, one skipped**, **339.306 seconds**, with no
failures or errors. The optional native OCR check skips without Tesseract/Poppler;
P5 does not claim to verify native OCR. System check passed and migration drift
check reported no changes. Both backend runs used isolated SQLite and local mail.

Frontend final complete suite: **99/99 passed**, 49.44 seconds; final strict
typecheck/build passed (Vite 1.62 seconds). Earlier full runs repeatedly hit the
existing 401 redirect test's scheduling race (98 passed, one failed). The owned
test now explicitly awaits React's asynchronous auth-cache/navigation flush via
`act`; the same redirect assertion and timeout remain. The targeted check and
complete suite passed after that harness correction. Shared auth was not edited.

Final real Microsoft Edge headless rehearsal passed against the built app and
isolated SQLite database: live report membership, actual XLSX download, native
CSV file upload/button-click preview, reason-gated explicit commit, KPI unknown
states, direct reload, 360px horizontal layout, institution-scoped report,
role-denied import and expiry-to-login redirect. Only the last expiry case uses
explicit HTTP 401 fault injection; successful API actions were not stubbed.
Officer context recorded zero page errors and zero external requests. The actual
download reopened with openpyxl: two expected rows and exact text paise values.
The mobile screenshot was inspected; the shared sidebar trigger slightly overlaps
the card's left heading edge at 360px. Inputs remain usable; that small K2 visual
issue is recorded rather than fixed in teammate code. This is not a WCAG audit.

The first component tests expected a role error as an alert, while K2 renders its
existing role-denied Result; the test now asserts that actual component. jsdom
file validity did not trigger native click submission, so component tests exercise
the React submit boundary and assert multipart, CSRF, explicit reason/version and
stale-preview invalidation. Real Edge separately verifies native file upload and
button clicks without mocking HTTP success. Initial unit-test fixture `size` was
corrected to the actual `size_bytes` field; no product expectation changed.

Known upstream OpenAPI serializer/operation-ID diagnostics remain unchanged. No
strict global schema-clean claim or teammate-code repair is included.

## Repeat tests (PowerShell, repository root)

`.env` selects the supplied remote PostgreSQL connection unless overridden.
Always select SQLite for these local checks; do not migrate/seed the shared
database accidentally. No Supabase queries, credentials or applicant files are
needed for this acceptance run.

```powershell
$env:DATABASE_BACKEND = 'sqlite'
$env:EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_report_integration obligations.tests.test_owned_api obligations.tests.test_platform_api obligations.tests.test_sources obligations.tests.test_csv_validation obligations.tests.test_kpis --noinput
.\.venv\Scripts\python.exe -m evaluation.s4.run
.\.venv\Scripts\python.exe -m evaluation.s4.kpis.run
.\.venv\Scripts\python.exe manage.py test portal.tests --noinput
.\.venv\Scripts\python.exe manage.py test --noinput
Set-Location frontend
npm test
npm run build
```

## Demo step and remaining boundaries

On a disposable local synthetic demo database, the existing `seed_review` invokes
the owned seed hook automatically. Sign in using the existing generated officer
credentials, open **Reports**, choose each report and download XLSX. The synthetic
S4 college's draft obligation appears in the intervention report with advisory
shortfall/term-gap reasons. Open **Synthetic institution import**, choose
`evaluation/s4/valid.csv`, preview and inspect candidate identities, enter a reason,
then explicitly confirm once. Reusing that file after commit reports duplicate
identities and does not overwrite data. Open **Process KPIs**, select an aware
cohort through the browser's local date/time inputs, and explain sample counts,
unknown histories and source limitations before discussing any percentage.

Still requires team agreement: renewal eligibility/waivers and policy publication,
reviewed receipt completeness, release-stage document requirements, verification
history/version semantics for corrected legacy records, and preview retention/
cleanup. No automatic cleanup or destructive migration was introduced. No bank
service, OCR, scheduler write, release workflow or P6 screen is implemented here.
Master-audit sealing/visibility integration remains the explicitly planned P6
contract work; imports retain existing owned entity audit records.
