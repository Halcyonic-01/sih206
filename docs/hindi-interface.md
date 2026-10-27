# English / Hindi interface

The current React portal has a local English/Hindi selector: **🇬🇧 English / 🇮🇳 हिन्दी**. It appears in the masthead on login, signed-in pages and public letter verification. Deposit dialogs include the same selector so an unsaved form does not have to be closed to change language.

## Behavior

- English is the default. The selected language persists in this browser under `localStorage['pramaan.language']`; only `en` and `hi` are accepted. This is a display preference, not an authentication token or account setting. Storage-denied browsers can still switch in memory.
- Navigation, headings, buttons, field labels, declarations, status descriptions, tooltips/help text, empty/error states and Ant Design controls use bundled Hindi strings. There is no remote translation request and no new dependency.
- React components subscribe to the language preference. The router is constructed once, so switching does not recreate routes, discard an unsaved form, submit an action, or reload the application.
- Institution/bank/holder names, user-entered notes, references, filenames, original document/OCR text, AI-generated case content, amounts and dates remain as recorded. Dates retain the existing formatting; no global Day.js locale is changed. Brand names and technical acronyms remain unchanged.
- API routes, field names, IDs, status codes, option values, permissions and stored records stay language-independent. Only their display wording changes.

The primary React interface is localized. The historical `/legacy/` fallback, stored/downloaded documents, workbook/CSV export content, outbound email and free-form historical messages retain their existing language. These are not translated by a browser display preference. Hindi policy/declaration wording is a prototype translation and still needs a fluent teammate's review; it is not a certified legal translation.

## Notifications

The notification API adds an optional display object:

```json
{"translations":{"hi":{"subject":"...","body":"..."}}}
```

All current system templates have Hindi equivalents with the same placeholders. References, dates, counts and institution names are inserted unchanged. The serializer never exposes the raw context dictionary. Stored subject/body, read status, email delivery and historical audit data are not rewritten.

If an unknown/custom notification or a historical message no longer matches its template, it remains in its original language. That avoids inventing a translation that changes the recorded meaning. Locale switching alone makes no notification write request.

## Maintenance

- `frontend/src/i18n/index.ts`: preference store, React subscription, interpolation and display-only label maps.
- `hi.json`: common labels; `hi-help.json`: explanatory text; `hi-domain.json`: workflow labels, declarations and messages; `hi-dynamic.json`: parameterized display text.
- `LanguageToggle.tsx`: accessible buttons with `aria-pressed` and explicit language labels.
- `notifications/i18n.py`: known system-message translations. Tests enforce identical placeholder sets and preserve historical messages.
- `source-keys.json` / `dynamic-keys.json`: audited source inventories; the unit test checks their Hindi coverage.

Add new UI wording through `tr(...)` / `t(...)`, never by translating arbitrary record values or mutating the DOM. Supply dynamic values separately, for example `tr('Welcome, {name}', {name})`. Keep technical API values and React list keys unchanged. Do not call translation APIs on applicant records.

```powershell
Push-Location frontend
npm run test:translations
npm test -- --maxWorkers=2
npm run build
Pop-Location
.\.venv\Scripts\python.exe manage.py test notifications.tests.test_i18n notifications.tests.test_api portal.tests.test_schema_contract
```

`test:translations` uses the existing TypeScript compiler to check every explicit literal translation call. It catches missing catalog entries; it cannot certify linguistic quality or discover every future unmarked string automatically.

## Browser acceptance

Use the disposable app from `docs/owned/SEMIFINAL_UPGRADE.md`. New checks are in `frontend/tests/language.spec.ts` and require `SEMIFINAL_DISPOSABLE=1`.

1. On login, type a username, switch to Hindi, and verify the text remains while labels change. Reload and confirm Hindi persists; switch back to English.
2. As institution A, open New deposit. Enter a reference, a bank named `Dashboard`, amount `500000.25` and date `2026-10-27`. Switch using the dialog's toggle. Verify all values remain exactly unchanged and field/help text changes. Switch back, cancel and confirm the header toggle works after the dialog closes.
3. As officer, open Notifications and switch to Hindi. Confirm the system message changes while a second API read returns unchanged stored English subject/body/date.
4. At 390 px verify readable Hindi labels and no horizontal page overflow. Rehearse the existing workflow in English to detect regression of navigation, uploads, clearance evidence or sign-out.

Test results and limitations for this implementation are recorded in `docs/owned/HINDI_INTERFACE_RESULTS.md`.
