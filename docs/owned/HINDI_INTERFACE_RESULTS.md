# Hindi interface — implementation verification

27 October 2026. Local changes on `s/semifinal-p2-p4`, after merge commit `ab2e984`. No commit, push or remote merge was performed for this feature. Earlier local work and the teammate's updated visual design were preserved.

## Implemented

- Accessible 🇬🇧 English / 🇮🇳 हिन्दी selector on login, portal/public-page mastheads and deposit dialogs, with persisted browser preference and `html.lang` updates.
- Bundled Hindi interface catalogs, including navigation, form labels, status wording, field/help text, declarations, dialogs, notification controls, error/empty states and parameterized labels. Ant Design uses its bundled Hindi locale; dates retain the original formatter.
- Stable router and React language subscriptions preserve unsaved forms. No DOM mutation, online translation, account preference migration or new dependency.
- Presentation-only translation maps leave API field names, option values, identifiers, dates, monetary strings and record data untouched. Institution/bank names are never looked up in the UI dictionary merely because their text resembles a label.
- Additive notification `translations.hi` response, covering all current system templates. Original stored subject/body and email behavior remain unchanged; unknown/custom or changed historical messages stay original. Only formatted display strings are returned, never raw context.

## Actual tests

| Check | Result |
|---|---|
| Full backend suite | 690 tests, OK, 1 optional native OCR test skipped; 363.857 seconds |
| Focused notification/API/schema tests | 16 passed |
| Complete frontend suite | 132/132 passed, 15 files; final full run 66.39 seconds |
| Post-visual-review language/records component checks | 9/9 passed |
| Full Chromium browser regression | 10/10 passed, 55.9 seconds |
| Translation coverage | 548 explicit UI keys covered; 717 catalog entries |
| TypeScript / Vite build | Passed |
| System check / migration consistency | Passed; no migration needed |
| Strict OpenAPI validation | Passed without warnings |
| Whitespace check | Passed |

The initial browser run passed 9/10; the remaining test clicked the header toggle while the closing modal's toggle was still exposed during animation. Added a wait for the dialog to close; the full rerun passed. No test was disabled or its timeout extended.

New checks prove login-language persistence, form state preservation, references/numeric strings/dates unchanged, a bank named `Dashboard` unchanged, notification originals unchanged, literal interpolation and safe fallback when preference storage is blocked. Existing tests cover scope, uploads, release decisions, protected PDFs, keyboard/mobile navigation and sign-out behavior. Hindi mobile screenshots were inspected; a remaining mobile filter placeholder was localized and the relevant checks/build rerun.

## Boundaries and remaining review

- Hindi wording needs a fluent teammate's linguistic review, especially declarations. It is not an approved legal translation.
- Free-form review notes, evidence/OCR text, AI-generated content, names, technical codes, dates and amounts remain in their original form. Stored/downloaded documents, exports, outbound email and the historical `/legacy/` fallback are not translated by this browser preference.
- Custom or historically modified notifications are intentionally not reconstructed from a different template. Their original text remains visible.
- No real applicant data or external translation service was used. `.env`, normal database, credentials, permissions and workflow decisions were not changed.

Local demo: `http://127.0.0.1:8011/login`, using the isolated rehearsal profile. Setup, behavior and maintenance are documented in `docs/hindi-interface.md`.
