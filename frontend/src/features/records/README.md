# Yash records workspace (Y4, Y5, Y7)

`RecordsWorkspace` receives the authenticated role and an `Api` adapter. Mount it
inside Kushagra's QueryClientProvider/AppShell. Keep the shared API client and
authentication ownership with K2. API calls use the injected adapter; no credentials
or tokens are stored in browser storage. The adapter must use same-origin Django
session cookies, obtain/send CSRF for writes, throw useful 400/403/409 messages,
and implement a protected document Blob download.

Dependencies: React 19, Ant Design 6, TanStack Query and `pdfjs-dist` (PDF.js viewer
from the agreed document-review design). PDF.js's worker is bundled by Vite.
Use Vite client types for the worker URL import. The document view renders pages
to canvas and retains the original protected download for accessible/manual review.

Features: paginated scoped record search/filter/CSV; mode-aware draft/renewal forms;
detail tabs, protected PDF navigation, officer correction/review/observations and
resolution; typed document uploads; dashboard categories, intervention queues and
accessible maturity data; evidence ladder and synthetic statement preview/commit.

S2's approved shortfall/coverage interface is not published, so the dashboard
explicitly reports coverage unavailable. Notification hooks likewise return
`notification_queued=false` until K5's adapter is configured. No simulated statement
match is displayed or counted as independent bank confirmation.
