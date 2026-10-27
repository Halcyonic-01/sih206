# Final regression fixes (local only)

The user explicitly authorized these limited changes to scenario/browser tests. No product logic, private .env or demo records changed. No commits or pushes made.

## Changes

- `scenarios/tests/test_ps_review_fixes.py`: consume the downloaded PDF, assert its PDF header and always close the streaming response in `finally`. This fixes Windows file-lock cleanup without bypassing cleanup or authorization assertions.
- `frontend/tests/records.spec.ts`: current status wording, tab wording and verification labels; expand the extraction panel; test explicit AI/OCR disabled fallbacks; use standalone dashboard/reconciliation routes; fill the mandatory statement source label; use mobile record navigation; account for the button icon and empty-state punctuation. Remove screenshots targeting a folder outside the repository. Keep the full record/correction/acceptance/renewal, reconciliation, notification and institution-isolation assertions.
- `frontend/playwright.config.ts`: optional `PLAYWRIGHT_BASE_URL`, preserving 8010 as default.

## Verification

- Focused backend regression: 3 tests passed, including cleanup (7.113 seconds).
- Full Chromium browser suite: 4 passed (23.6 seconds).
- TypeScript check: passed.
- Full backend rerun: 670 tests in 482.848 seconds; OK (1 skipped), zero failures/errors.

## Isolation and scope

Browser instance: `http://127.0.0.1:8011`, database/documents/generated credentials under `tmp/browser-disposable/`, settings module `tmp/browser_check_settings.py`.

The module imports standard config, then overrides BASE_DIR for seeds, SQLite database and media path; static frontend/template locations retain the real repository locations. AI and OCR are off; outgoing notification delivery is off; email uses locmem. It seeds fresh accounts and `seed_yash_examples`. No API keys were printed, copied into files or used by browser tests. Playwright Chromium is installed under `tmp/playwright-browsers/`.

Local rerun (with the disposable server already started):

```powershell
Set-Location frontend
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:8011'
$env:PLAYWRIGHT_BROWSERS_PATH='C:\Saksham\Code files\SIH3rd\tmp\playwright-browsers'
$env:DEMO_CREDENTIALS_FILE='C:\Saksham\Code files\SIH3rd\tmp\browser-disposable\data\demo-credentials.txt'
npx playwright test
```

These browser tests validate manual fallbacks, not live AI/OCR extraction accuracy. Existing backend tests cover those services separately. No claim of new release-case browser coverage is made: the four current browser journeys cover records, reconciliation/responsiveness, scope and notifications.

The full backend command uses `DATABASE_BACKEND=sqlite` and `NOTIFY_SEND_ON_COMMIT=true`; the latter is required by the existing on-commit notification test. Tests run in Django's separate test database.

Logs: `data/fixed-backend-tests.log` and `data/fixed-browser-tests.log`. Demo case 1 remained COMPLETED with monitoring false after browser checks.
