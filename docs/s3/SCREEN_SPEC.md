# S3 institution screens: preparation specification

Status: PROPOSED PRESENTATION SPECIFICATION, NOT AN IMPLEMENTED FRONTEND.
Prepared 24 October 2026. Scope is S3's institution list, institution detail and
requirement calculator from the private allocation PDF (page 3), F1 (gap-plan
page 17), F13 (page 22) and F14 (page 23). These references identify requirements;
the private PDFs remain outside Git.

This adds no React project, component, route, API, model, migration or seed. It
does not change [S2's proposed API contract](../../obligations/API_ACCEPTANCE.md)
or resolve the [policy decision log](../../obligations/POLICY_DECISIONS.md).

## Ownership and dependencies

- Saksham: the three screens and their presentation logic after implementation
  is authorized. Only specification and synthetic fixtures are prepared now.
- K2/Kushagra: shared React shell, auth provider, routing registration, theme and
  API client. Use their agreed extension points; do not create a competing shell.
- S2/K1: scoped institution/approval/obligation/calculator APIs and agreed HTTP
  contracts. The specification uses presentation fields, not a replacement API.
- Y1/Yash: complete linked holding snapshots for coverage; instrument navigation
  and evidence links need the real registered routes and scoped data.
- K6/Kushagra: delivered notifications and scheduled actions. A visible due-date
  banner is not evidence that a notification was delivered.

Future route slots are provisionally `/institutions`, `/institutions/:id` and
`/institutions/:id/calculator`; register them through K2 only after agreement.
There is no working URL for these screens today. No new edit, exemption,
publication, release, report or import workflow is included in this preparation.

## Shared presentation rules

1. Every fixture and fixture-backed screen must show SIMULATED. Calculations
   additionally show DRAFT_DEMO_NOT_APPROVED and the explicit demo assessment date.
   Never fall back to fixtures when a live API fails, denies access or has no rows.
2. Read institution scope and permitted actions from authenticated server context.
   Fixture actors describe scenarios, not client-side authorization. Clear prior
   institution data when identity/scope changes; prevent late responses from
   populating another institution's page.
3. Separate administrative status, calculated coverage and bank verification.
   Use "Covered in this draft assessment", never "Verified", "Compliant" or an
   automatically applied "Met" decision. Empty findings are not a compliance pass.
4. Null is "Unknown"; a failed/missing adapter is "Assessment unavailable";
   a known empty ledger may legitimately hold INR 0.00. Loading is none of these.
   Do not use JavaScript truthiness to turn zero into unknown or null into zero.
5. Money remains integer paise, displayed with INR and two decimal places; e.g.
   1000000000 paise is `INR 1,00,00,000.00` (100 lakh). Never calculate regulatory
   amounts in the browser or round financial facts for display. Agree safe wire
   range/lossless encoding with K1 before converting larger values to JS Number.
6. Dates are date-only ISO values, displayed unambiguously, e.g. `20 Apr 2026`.
   Do not apply browser UTC shifts. A demo as-of date is visibly distinct from
   server today and from an instrument's issue/maturity dates.
7. All findings show code, compared values, relevant rule/version/clause and
   assessment date. Document/page links appear only if the API supplies an
   authorized reference; financial calculations do not invent PDF page evidence.

## Screen A: institution list

Purpose: find an institution within the user's authorized scope and open it.

| Region | Required content/behaviour |
|---|---|
| Heading | Institutions; scoped result count only when loaded |
| Search | Institution name/code/AICTE ID within the proposed API's supported fields; preserve query on retry |
| Table | Name, synthetic/real identifier as applicable, code, type, region/state, assessment availability, View action |
| Pagination | Follow K1's agreed server format; counts and pages cannot widen scope |
| Institution account | Show only its own authorized institution; do not embed staff data and filter it in the browser |
| Staff account | Show only the staff scope actually returned, not a presumed all-India scope |

Keep administrative status labelled separately from assessment availability.
Do not sum unrelated obligations into a single unexplained institution total.
There are no bulk actions, institution creation forms or exports in this spec.

States: loading skeleton without zero counts; ready scoped rows; empty authorized
scope/query with a clear empty-state message; unavailable response with Retry.
An empty list does not mean no deposit obligation exists in the real world.

## Screen B: institution detail

Purpose: understand one selected obligation, its holdings and next human action.

| Order | Content |
|---|---|
| 1 | Institution name/code, AICTE ID, SIMULATED marker where appropriate, assessment date and back navigation |
| 2 | Next-action banner: action, responsible party, supplied due date or "Deadline not supplied" |
| 3 | Profile: trust, type, region, state and contact; missing profile fields stay unknown |
| 4 | Programme approvals: programme, level, LoA/EoA reference/date, separate land and building tenure |
| 5 | Explicit obligation selector/list if several exist; no silent selection or unlabelled aggregation |
| 6 | Selected obligation: basis, recorded administrative status, rule provenance, term start/end |
| 7 | Cards: required, currently held, shortfall; each with its own availability state |
| 8 | Coverage timeline and equivalent date/amount table |
| 9 | Advisory findings and supplied open actions with evidence/provenance |
| 10 | Requirement calculator entry if the server allows it |

### Cards and timeline

- The selected obligation's IDs must match all supplied holdings and findings.
  Inconsistent data is an unavailable assessment, not a partial success.
- Known requirement plus unavailable holdings: show the requirement, but held
  and shortfall are unavailable. Never silently treat the failed ledger as empty.
- Unknown requirement plus known empty ledger: required/shortfall are unknown;
  held can be INR 0.00. State that applicability still needs review.
- Draw the obligation term as the reference band, with one holding bar per row.
  Label each amount, issue, maturity and eligibility state. Historical/pending
  holdings, if supplied, are visually distinct and do not enter current totals.
- Mark the first uncovered date and supplied action deadline. A top-up that fixes
  today's amount may still leave a term gap. A redundant short holding does not
  shorten otherwise sufficient coverage.
- `term_gap_days` means remaining term after the first break, not summed uncovered
  days. Explain this wording rather than claiming an exact accumulated shortage.
- Unknown dates produce no invented ten-year axis. Use "Term not established".
  Current administrative snapshots do not reconstruct historical coverage.
- Give the timeline an equivalent accessible table: holding/reference, amount,
  issue/maturity, current eligibility and coverage warning. Colour alone never
  carries meaning. Label which obligation and assessment date it represents.

### Findings and actions

Shortfall and term-gap banners ask for human review under the draft interpretation.
They do not order a real payment or renew a deposit automatically. A proof action
requires an actual supplied intimation/deadline; absence of a date is not overdue.
An action may be recorded as simulated/notified only according to its actual data;
these fixtures never claim delivery, task assignment or completion.

Avoid fabricated document links, officer identities and rule approvals. If an
authorized instrument route is not registered yet, render its reference as text
with unavailable navigation rather than a guessed URL.

## Screen C: requirement calculator

Purpose: preview a hypothetical requirement without saving it as an obligation.

Context: scoped institution and server profile type, explicitly selected rule
version, rule/source/draft label and assessment date. Missing required context
disables preview with a specific explanation, never a default PRIVATE type.

Input rows: canonical programme, DIPLOMA/UG/PG level, land tenure and building
tenure. Rows can be added/removed locally. Prevent duplicate programme/level rows,
but the server must validate again. No bank, instrument upload or release fields.

Preview action: use K2's client and the agreed S2 endpoint only when implemented.
Show pending state and prevent duplicate submissions. Response: base breakdown,
multiplier applied once, total in INR, source clause/version/fingerprint and
`exemption_assessed=false`. Explain that exemptions and conversion balances have
not been assessed. No Save/Apply-to-obligation action is specified.

Any input/context change invalidates the prior preview immediately. A late
response for old inputs must not appear as the current result. On validation
failure, retain inputs, show a summary and inline errors, and focus the summary.
On 409 context change, request fresh context and require a deliberate recalculation.
On 503, show failure and Retry; no substitute fixture answer or automatic write.

## Accessibility, responsive and navigation acceptance

- Use K2's Ant Design/theme conventions when actual components are authorized.
- All controls have visible labels, logical keyboard order and visible focus.
- Announce loading/error/result changes appropriately; focus errors, not every
  background data refresh. Headings and table headers form a readable structure.
- At narrow widths, stack cards, preserve readable dates/amounts and expose all
  table content through an accessible overflow/row-detail pattern. No clipped
  actions or colour-only warnings. Avoid mandatory hover interactions.
- Back/list navigation retains the previous list query/page. Do not put sensitive
  contacts, tokens or financial detail into URL parameters or browser storage.
- Not-found and cross-institution responses share a generic page with no leaked
  name, holdings, count or cached previous result. A visible forbidden action may
  show a 403 message. Session recovery belongs to K2's auth flow.

## Planned acceptance mapping

These are future UI tests/manual checks, not claims that a browser screen exists.

| ID | Fixture(s) | Expected observation |
|---|---|---|
| UI-01 | list-staff, list-own | Correct scoped rows/count; no client-only security filtering |
| UI-02 | list-loading, list-empty, list-unavailable | Distinct loading, empty and failure messages; no invented zero totals |
| UI-03 | detail-covered | Required/held 100 lakh, shortfall zero, explicit draft label; no compliance/verification claim |
| UI-04 | detail-shortfall | 60 lakh held against 100; 40 lakh shortfall and advisory review action |
| UI-05 | detail-term-gap | Amount sufficient today; future gap remains visible and labelled |
| UI-06 | detail-unknown | Null requirement/term remain unknown; known empty held amount remains zero |
| UI-07 | detail-adapter-unavailable | Required amount remains visible; unavailable ledger never becomes zero |
| UI-08 | detail-proof-overdue | Both missing receipts, intimation and supplied deadline visible; no delivered-alert claim |
| UI-09 | detail-not-found, detail-forbidden | Generic access states; no protected data or cached page |
| UI-10 | calculator-idle, calculator-preview | Explicit preview action, labelled breakdown and 100 lakh result; no mutation |
| UI-11 | calculator-invalid | Retained invalid row and actionable error; previous result absent |
| UI-12 | calculator-conflict, calculator-unavailable | Fresh-context/retry guidance; no silent automatic substitution |
| UI-13 | All ready detail/calculator cases | Same numbers and finding codes as the attached S2 calculation checks |
| UI-14 | All states | Keyboard, responsive and readable timeline/table behaviour once UI exists |

Before real implementation, agree K2 route/client hooks, final S2 response mapping,
pagination, money encoding, field errors, auth status, action names and available
instrument links. Do not change those shared files merely to fit these fixtures.
