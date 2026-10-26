# Review build (K8)

How to produce and verify the build shown at the 25 Oct 2026 review, and what to run before tagging it.

## One-command verification

```bash
python scripts/review_check.py          # everything below, on a clean copy of HEAD
```

It runs: `check`, `makemigrations --check`, the production-profile `check --deploy`, all Django tests, the React type-check,
tests and build, then **a fresh install of the committed files into an empty temporary folder** (virtualenv, `npm ci`, build,
migrate, seed v2, start in production mode, sign in as officer and auditor, verify the audit chain). It prints the tag command
but never creates the tag or pushes anything.

## What seed v2 contains

`run.sh` / `run.ps1` / Docker run these on the first start (all synthetic, idempotent):

| Command | Creates |
|---|---|
| `seed_demo --generate-password` and `--authority-only` | institution A and B users, officer, authority |
| `seed_staff --generate-password` | `clearance_pgrc`, `clearance_vigilance`, `clearance_grants`, `auditor` |
| `seed_scenarios` | 17 records: submitted, discrepancy, duplicate, maturity bands, renewal, 4 release states |
| `seed_review` | example-domain e-mail addresses, institution profiles, real download/export activity, and `run_due_rules --as-of 2026-10-23` (the PS scenario 4 reminders, pending e-mail) |
| `seed_review_<area>` | **owner hooks**: any management command with this prefix is run by `seed_review` in alphabetical order |

`seed_review_ps_data` (K8) adds the PS 3/7/9 data: obligations for DEMO-A and DEMO-B with the scenario records
linked to them, the release-ready record `PS7-RELEASE-READY` with its APH 6.46 documents, and dated KPI history.

Yash and Saksham ship their scenario data as `seed_review_records` / `seed_review_verification` /
`seed_review_obligations` / `seed_review_release` commands (synthetic, idempotent, through the services). `seed_review` reports
a failing hook at the end without hiding the others.

## Walkthrough for the K scenarios (PS 4, 8, 10)

Demo evaluation date **2026-10-23**. After the first start:

1. **4, alerts.** Sign in as `institution_a`: the bell shows the maturity reminders; `M6-THIRTY` has the T-30 message.
   `python manage.py send_notifications` sends the pending e-mails (console output unless SMTP is set).
   `python manage.py run_due_rules --as-of 2026-10-23` again adds nothing. `M6-MATURED` shows "renewal overdue".
2. **8, access control.** As `institution_b` open a record of A: not found. Five wrong passwords lock the account (HTTP 429).
   An officer or clearance account cannot decide a release.
3. **10, audit.** Sign in as `auditor`: Audit and access shows full history and the access log (downloads, exports,
   sign-ins). Integrity tab: *Verify chain* is OK. Then tamper and verify again:
   ```bash
   python manage.py shell -c "from portal.models import AuditEvent; AuditEvent.objects.filter(action='ACCEPTED').update(reason='edited')"
   ```
   *Verify chain* now names the broken event (`python manage.py verify_audit_chain` exits non-zero).
   Re-seal is not possible: restore the row, or start a fresh database.

The same checks run as automated tests in `scenarios/tests/test_ps_scenarios.py`.

## Fresh-install test on Windows

CI (`fresh-install` job, `windows-latest`) runs `python scripts/run_portal.py --smoke` on a clean checkout. By hand:

```powershell
git clone <repo> fdr-portal; cd fdr-portal
.\run.ps1 --smoke      # installs, builds, seeds, probes, stops
.\run.ps1              # then open http://127.0.0.1:8010/
```

## Tagging

When every owner's pull request is merged, CI is green and `review_check.py` passes:

```bash
git tag -a review-1 -m "Review build 25 Oct 2026"
git push origin review-1
```

Hotfixes after the review get `review-1.1`, `review-1.2`, and the final submission build is tagged `submission-1`.

## Browser scenarios (Playwright)

`frontend/tests/` holds the problem-statement flows as browser specs: `records.spec.ts` (scenarios 1, 2, 5, 6) and
`ps-scenarios.spec.ts` (3, 7 end to end from request to completed release, and 9). CI runs them in the
`browser-scenarios` job: it starts the seeded portal with `run_portal.py`, adds the synthetic RTGS and OCR examples, runs
`npx playwright test`, and uploads traces and the HTML report when a spec fails.

To run them locally against a **fresh** database (the release spec completes `PS7-RELEASE-READY`, so a second run on the
same data fails by design):

```bash
python scripts/run_portal.py --skip-build --no-scheduler   # first run seeds the demo data
python manage.py seed_yash_examples && python manage.py seed_ocr_example
cd frontend && npx playwright install chromium && npx playwright test
```

Passwords are read from `data/*-credentials.txt`; override with `DEMO_CREDENTIALS_FILE`, `STAFF_CREDENTIALS_FILE`,
`AUTHORITY_CREDENTIALS_FILE`, `PORTAL_URL`, `PLAYWRIGHT_CHROMIUM_PATH` (use an installed Chromium) and
`PLAYWRIGHT_OUTPUT_DIR`.
