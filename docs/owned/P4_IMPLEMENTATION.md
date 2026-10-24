# P4 — available holdings and document sources

Local implementation, 25 October 2026, branch `s/P4-source-integration`.
Status: actual holdings and stored typed-document evidence connected; **reviewed
proof-receipt timing and unresolved regulatory interpretations remain blocked**.
P5 is not started.

## Dependency check and preservation

Remote main advanced from `e789c30` to `2c3f922`, merging Yash's records and
Supabase work. Y1's nullable obligation FK/mode fields, Y2's bounded PDF parser,
Y3's typed document APIs and later verification modules are now present.

Local P1–P3 was first saved in checkpoint `5747130`. Upstream dependencies were
merged locally in `223ee32`. The two conflicts were in owned client.ts and
obligations/api_urls.py: P1's explicit narrowing and P2's core-only registrations
were retained. Upstream changes elsewhere were accepted without authoring edits
to teammate code. In particular, the upstream catch-all obligations include was
not allowed to mount S4/S5 prematurely. Original merged source remains available
in Git; no files were deleted to replace the checkout.

The merged shared lock pins charset-normalizer differently from our older optional
lock. Only requirements-saksham.txt was recompiled against its existing input and
the current shared requirements. Shared requirements and frontend lock/config
remain unchanged. No unapproved new product dependencies or migrations were added.

## Environment configuration

- The supplied settings were saved in ignored, untracked `.env`; no values are
  reproduced here. Password punctuation in the database URI was percent-encoded.
- Merged settings load `.env`; existing process variables take precedence.
- The configured PostgreSQL URI was parsed without connecting; required TLS,
  session-pooler port and private schema configuration were recognized.
- **Supabase connectivity, schema existence/permissions and migration status are
  unverified. No shared database query, migration, seed or upload was performed.**
- Tests explicitly use local SQLite and capture mail locally. The existing local
  application database was not migrated or used as a test fixture.
- Owner-only permission verification failed through the platform helper; automatic
  approval review rejected a subsequent native ACL change. The human chose to
  leave permissions unchanged. `.env` is ignored, but restrictive ACLs are not
  verified. No bypass or further permission change was attempted.
- Keys/password pasted into the conversation should be rotated before shared use.
  Do not rotate an audit-chain key on already sealed data without a reviewed
  migration/key-rotation plan: it can invalidate verification of existing seals.

For local SQLite work in PowerShell, explicitly set this in that terminal:

```powershell
$env:DATABASE_BACKEND = 'sqlite'
```

Without that override, the supplied .env selects the configured remote database
for normal runtime commands. Do not assume local SQLite migrations validate the
remote database or run normal migrate/seed commands against it inadvertently.

## Source implementation

`obligations/sources.py` is Saksham's read-only adapter over the actual Y models:

1. Re-resolve the obligation through owned scope and use K4's scoped instrument/
   document querysets. No guessed institution/code/reference matching occurs.
2. Verify the actual FK target; assemble typed holdings with amount, dates,
   persisted review status, supersession/release flags and explicit obligation ID.
3. Reuse existing pure coverage/findings. Nonaccepted, superseded, released,
   expired, future-issued and unlinked records do not contribute to held money.
   An accepted successor retains the existing obligation term.
4. A complete scoped empty query is **known zero**. A missing/inconsistent source
   remains **unavailable**. A visible corrupt cross-institution link fails closed.
5. Return scoped FDR/PAYMENT_PROOF/RPGF_PROOF/AFFIDAVIT_3 metadata under
   assessment.proof_evidence, including real document/instrument IDs, stored hash,
   page count, protected Y3 download path and first-page reference when known.
6. Label evidence `STORED_METADATA_ONLY`; uploaded_at remains an upload timestamp.
   received_on is null. Stored parser metadata is not current-file availability,
   document sufficiency, bank verification or reviewed receipt timing.

`services.obligation_detail` now separates valid holding assessment from proof
timing. Without a reviewed receipt-date contract it returns coverage/findings
and real evidence while proof_assessment remains UNAVAILABLE with a reason.
It does not invent PROOF_OVERDUE from arbitrary upload timestamps. A malformed or
future-dated explicitly configured receipt provider cannot erase valid coverage;
database failures still use safe shared 503 responses.

The existing trusted receipt-provider boundary is retained for a later agreed
integration. Tests that inject complete missing receipts are clearly test-only;
no default fixture provider or fake runtime receipt source was configured.

## Remaining P4 boundaries

- Y2/Y3 expose created_at, page_count and typed evidence, but no reviewed receipt
  date/completeness contract. A policy owner and Yash must define that interface;
  Saksham then implements the adapter. Merely renaming uploaded_at is insufficient.
- Existing P-01–P-13 decisions remain open, including applicability, exemptions,
  conversion offsets, term/leap-day rules and penalty/receipt semantics. No draft
  rule was published, exemption inferred or penalty imposed.
- K6 consumes its published escalation-matrix configuration. Our existing draft
  catalogue's nested reminder/escalation representation still needs an agreed
  mapping/publication step; no scheduler edits or automatic obligation-status
  writes were introduced. A read assessment does not silently set MET.
- Adapters represent current persisted lifecycle state, not a reconstruction of
  what the database contained on an arbitrary historical date.
- Yash's separate obligations/coverage.py adapter is retained unchanged. Aligning
  its reviewed-policy presentation with the draft assessment needs a team contract;
  P4 does not silently replace teammate dashboard behavior.

## Verification

Focused source/default-route/legacy casework tests: **55 passed**, 19.940 seconds.
Actual Y1/coverage/PDF dependency checks: **14 passed**, 6.520 seconds.
S2 labeled evaluation: **76/76 passed**, original labels unchanged.
Django system check passed; migration drift: no changes detected.

The first frontend suite run had one existing owned sign-in timing failure while
other checks ran (89/90); the unchanged rerun passed **90/90**, 34.48 seconds.
The frontend strict typecheck/build passed (Vite 883ms). No auth assertion or
timeout was changed. The initial dependency-test command named a nonexistent
test_uploads module; it was corrected to the existing test_pdf_validation module
and all 14 tests passed. These initial failures are not hidden as successful runs.

The first 47-test merged baseline also exposed the old unavailable-ledger test's
assumption that Y1 was absent (46 passed, one failed). It now explicitly injects
an unavailable source, preserving its assertions. Separate actual-model tests
verify that a genuinely empty linked query is known zero. Source labels and
regulatory expectations were not changed to manufacture success.

Merged schema generation reports missing serializer annotations/operation naming
in upstream Y endpoints. Those diagnostics remain owner work; no claim is made
that strict whole-project OpenAPI validation passes after this upstream merge.

Portal regression: **200 passed**, 176.706 seconds. Full backend: **620 tests run,
619 passed, one skipped**, 340.808 seconds; no failures or errors. The upstream
native OCR integration check in ai/tests/test_ocr.py skips when optional
Tesseract/Poppler tools are unavailable. Native OCR is therefore not verified by
this run. Logs and
evaluation outputs stay private under ignored data/p4-*; source tests use isolated
synthetic records/PDFs, not the supplied remote database or real applicant data.

### Repeat locally (PowerShell, repository root)

```powershell
$env:DATABASE_BACKEND = 'sqlite'
$env:EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_sources obligations.tests.test_platform_api obligations.tests.test_owned_api obligations.tests.test_casework --noinput
.\.venv\Scripts\python.exe manage.py test portal.tests --noinput
.\.venv\Scripts\python.exe manage.py test --noinput
Set-Location frontend
npm test -- --run
npm run build
```

These test commands create isolated test databases. They do not verify remote
Supabase configuration or authorize migrating/seeding the shared database.
