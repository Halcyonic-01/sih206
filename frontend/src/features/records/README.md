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

The shared session client/AuthProvider is mounted in main.tsx. The dashboard now
shows coverage from reviewed stored requirements and marks missing policy unknown.
Notifications include a scoped inbox and officer delivery operations. Documents
include local OCR and advisory prefill. Verification includes bank request history
and officer requests to operator-reviewed contacts. Simulations never independently
confirm funds. See docs/pending-integrations.md for configuration and limitations.
