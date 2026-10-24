# P3 — institution screens connected to the shared frontend

Implemented locally on 25 October 2026. Branch: `s/P3-institution-screens`.
P1–P2 working changes preserved; no push, shared/teammate source changes or P4.

## Delivered

- `frontend/src/features/saksham/routes.tsx` registers `/institutions`,
  `/institutions/:id` and `/institutions/:id/calculator` using K2's feature registry.
  The Institutions menu is available to institution, officer and authority roles,
  matching P2's conservative master-read policy. No release/report routes added.
- `InstitutionPages.tsx` wraps the existing screens in the shared Ant Design Card,
  uses K2 auth/route hooks, validates route IDs and gates the calculator on a
  successful scoped parent read. A foreign parent cannot fetch rules or calculate.
- Identity keys include actual React Query auth `dataUpdateCount`, user/role,
  institution and unit. The update counter advances even when same-user login
  returns structurally identical data. No replacement auth state, localStorage
  token or invented session-generation provider was introduced.
- `platformTransport.ts` adapts K2's get/post/upload/download helpers and preserves
  shared session cookies, CSRF, aborts, ApiError and 401 invalidation. It rejects
  non-API, foreign-origin, traversal-outside-API, backslash and fragment paths.
  Legacy document paths are deliberately unsupported here; document UI is later work.
- Existing institution components now show full available profile fields and clear
  empty programme/rule states. Scoped CSS adds keyboard focus and responsive
  controls/tables within the owned feature without modifying the theme or shell.
- Real P2 responses supply programmes, obligations and calculator results. The
  required amount remains visible while held/shortfall/timeline/follow-up remain
  explicitly unavailable when Y1/Y2 source integration is missing. Nothing is
  inferred or replaced with a fixture provider.

## Actual verification

| Check | Result |
|---|---|
| Shared focused owned Vitest suite | **63 passed**, four files; final run 11.80 seconds |
| Shared frontend build (includes strict typecheck) | Passed; final Vite build 1.20 seconds |
| Complete shared frontend suite | **88 passed, 2 failed**, 90 total, 35.60 seconds |
| Django system / migration-drift checks | Passed / no changes detected |
| Original portal tests | **159 passed**, 38.360 seconds |
| Complete backend suite | **545 passed, 1 failed**, 546 total, 144.759 seconds |
| P1/P2 backend file hashes captured at P3 start | All unchanged |
| Protected shared/teammate source comparison | Unchanged |

The two frontend failures remain five-second audit-test timeouts (event detail and
filters). The backend failure remains the Windows POSIX-mode assertion in
SeedStaffTests. No timeouts/assertions/settings were relaxed and those files were
not changed. The project-wide baseline therefore remains red.

The new Vitest tests exercise feature routes with actual shared AuthProvider,
RequireRole, QueryClient and client HTTP implementation, with clearly fake fetch
responses. They cover navigation, calculator payload/preview invalidation,
400/401/403/404/409/503, alert focus, empty lists, malformed route IDs, foreign
calculator gating and same-user login races. Adapter tests cover CSRF, multipart,
abort, unsafe paths, conflict without replay and shared unauthorized notification.
These unit tests are separate from the live browser evidence below.

## Live browser evidence

The in-app browser tool could not initialize (kernel asset path error). The
fallback used the already-bundled Playwright runtime and local Microsoft Edge in
headless mode, with the actual built React app and Django on localhost:8031.
No new project dependency was installed.

An isolated SQLite database and private credentials were created under ignored
data/. Synthetic institution/approval/obligation records were written through the
existing owned services. The ordinary local database and private documents were
not used or modified. No holding source, fake source adapter or bank integration
was installed. No notification was sent externally.

Passed against actual APIs:

1. Sign in as synthetic institution A; list includes A and hides B.
2. Keyboard focus from search to institution button; Enter opens detail.
3. Profile/programme/obligation reads show genuine stored synthetic values;
   missing holding/proof context stays unavailable.
4. Navigate to calculator; explicitly select the synthetic draft rule and leased
   building. Management PG 15 lakh INR × 2 gives **INR 30,00,000.00**.
5. Changing the input clears the old preview; a direct calculator URL reload works.
6. A foreign institution's calculator shows generic unavailable and no form.
7. A deliberately injected HTTP 503 shows the error with focus and no old/fake list.
8. Desktop and 360px screenshots were visually inspected. After the shared sidebar
   transition settled, viewport/page widths were both 360px, feature width 344px;
   no page overflow. Wide tables scroll inside the feature.

Browser run recorded zero page errors and zero external requests. This is a
bounded Edge/keyboard/responsive check, not a full WCAG audit, screen-reader test,
all-browser certification, PDF-viewer test or complete offline-package rehearsal.
Actual holdings, receipts and source-policy integration remain P4 and are unstarted.

Private evidence: `data/p3-browser-results.json`, `data/p3-desktop.png`,
`data/p3-mobile.png` and `data/p3-*.log`. Test DB/settings/seed/check scripts and
private generated credentials remain ignored under data/. They are test harnesses,
not production settings, product seed commands or real applicant data.

## Running and checking locally

With the existing merged dependencies installed, from the repository root:

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8010
```

The built frontend is served at `/`. Use an existing permitted account and visit
`/institutions`; normal profile absence is shown honestly if your existing records
have no S1 profile. Select a visible institution, inspect its programme/obligation
states, follow Requirement calculator and explicitly choose a rule. The preview
does not save an obligation. Do not expect unimplemented Yash sources to appear.

For development, K2's unchanged `npm run dev` in frontend/ proxies API traffic to
8010. For verification in frontend/ run `npm test -- src/features/saksham/`,
`npm run typecheck` and `npm run build`. On Windows use npm.cmd if required by
PowerShell execution policy. The root Python compatibility checker still delegates
to the shared typecheck and all owned tests.

No new institution editing, instrument/document interface, release workflow,
reporting or holdings calculation was introduced in this slice. P3 connects the
existing institution/read/calculator workflow; P4 is not started.
