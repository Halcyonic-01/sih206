# AICTE-inspired Pramaan frontend

Research date: 26 October 2026. This is an independent student prototype, not an
official AICTE website or approved visual-identity implementation.

## Sources actually inspected

- https://www.aicte.gov.in/ — the live page displayed “The site is currently down
  for maintenance.” Its normal homepage could not be inspected. The alternate
  https://www.aicte-india.org/ led back to the maintenance page.
- https://internship.aicte-india.org/ — the accessible official National Internship
  Portal. Inspected in a real browser, including its masthead, utility strip,
  navigation, hero, actions and footer, and read its computed styles.

This redesign therefore adapts observed cues from the official internship portal;
it does not claim to reproduce the unavailable main homepage.

## Observations and deliberate adaptations

| Observed on the official internship portal | Pramaan adaptation |
|---|---|
| Cream body background `rgb(255,252,246)` / `#fffcf6` | Same cream page background |
| Body text `rgb(27,17,64)` / `#1b1140` | Same main text tone |
| Navy action-group background `rgba(23,37,84,.95)` | Opaque `#172554` for service band, headings and primary controls |
| Orange action gradient from `#ff7a1a` to `#e85d04` | `#e85d04` decorative rules; darker `#a94400` for readable orange text and sign-in button |
| Green registration action `#8cc63f` | Not reused as a generic approval indicator; existing semantic statuses remain distinct |
| Thin utility strip, white identity masthead, separate navigation/update strip | White prototype masthead and navy horizontal category menus; redundant utility strip removed in the 27 October simplification |
| Rounded action controls, generous white cards and structured footer | Existing Ant Design controls and shared panels restyled consistently |
| Hashed custom body/display font-family names, with system/Segoe UI fallbacks | Existing local system-font stack retained; original font names are not guessed and no third-party font is loaded |
| Header spacing: actions use 10px/24px padding; hero groups use 32px gaps | Comfortable 24–32px desktop rhythm, reduced to 16–20px on phones |

No AICTE logo, national emblem, official portraits or institutional copyright claim
is copied. The user-supplied Pramaan artwork is used. The decorative emblem
placeholder was removed in the 27 October simplification; no official asset is shown.

## Implementation

- Shared Ant Design tokens: `frontend/src/theme.ts`.
- Base component tokens: `frontend/src/styles.css`.
- Masthead identity and disclaimer/footer: `components/PortalChrome.tsx`.
- Horizontal category menus and mobile expandable sections: `layout/AppShell.tsx`.
- Public sign-in and role-based home: `pages/LoginPage.tsx`, `pages/HomePage.tsx`.
- Cross-feature styling and responsive rules: `frontend/src/portal.css`.
- Public letter verification identity: `features/saksham/ReleasePages.tsx`.
- Shared page breadcrumbs: `components/PageHeader.tsx`.

Routes, authentication, CSRF, API transport, action permissions and workflow rules
are preserved. Shared components/theme cover records, viewer, verification,
reconciliation, institutions, reports/KPIs, releases, notifications and audit.
Simulation, draft-policy, unsigned-document and AI-advisory labels remain intact.

Accessibility includes the existing labeled controls, role-filtered navigation and
error/empty/stale states, plus explicit main-content skip links, keyboard focus,
reduced-motion treatment, responsive navigation and a print profile. No full WCAG
conformance claim is made without a complete assistive-technology audit.

## Validation

Frontend unit/component tests: 122 passed in 14 files. TypeScript check and
production build passed. Five browser journeys passed, covering PDF review,
local OCR, submission, correction, acceptance, renewal, reconciliation, mobile
navigation, institution isolation and inbox. Browser-test selectors were aligned
with current labels; assertions still exercise the real authenticated UI/API.

Visual review used only an isolated synthetic SQLite database, with AI/email
delivery disabled. Twenty-four route/viewport combinations at 1440×1000,
768×1024 and 390×844 had no page-level horizontal overflow or JavaScript page
errors. PDF rendering, calculator warnings, public verification's unavailable
state and keyboard skip-link focus were also inspected. Release and clearance
screens included supported empty states. No live bank or delivery workflow was
tested. Selected primary, muted, orange and control-border contrast pairs passed
their 4.5:1 text / 3:1 boundary thresholds.

## Navigation simplification — 27 October 2026

At the user's request, replaced the desktop sidebar with Home and horizontal
category dropdowns (Overview, Deposits, Institutions, Release, Insights,
Administration). Categories and children still come from role-filtered registered
routes. Each category opens on click or keyboard Enter; Escape closes it. On
phones/tablets, Select section opens expandable categories in a drawer. Selecting
a destination closes the drawer. Search, notifications, account and sign-out stay
in the masthead. Removed the emblem placeholder, extra utility/toolbar strips,
duplicated workspace copy and numbered decorative lifecycle/capability strips.
Retained all feature pages and operational warnings. The fifth browser test covers
keyboard dropdowns, mobile section selection and role filtering. Search test
readiness waits for the matching API response to avoid clicking an old list row.

## Supplied Pramaan logo — 27 October 2026

Replaced the original shield/text lockup with the exact user-provided PNG at
`frontend/public/pramaan-logo.png`. Shared Brand/LogoMark usage covers login,
authenticated header, mobile drawer, public letter verification and loading
screens. The footer and favicon also use this asset. The name and tagline are
preserved in the artwork without cropping, recolouring or distorting it.
Wordmark images have accessible alternative text and responsive sizing.
