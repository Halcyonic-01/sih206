# React frontend (K2)

React 19 · Vite 8 · TypeScript · Ant Design 6 · React Router 7 · TanStack Query 5 · Recharts.

```bash
npm ci              # once
npm run dev         # http://localhost:5173 , proxies /api to Django on :8010
npm test            # Vitest
npm run build       # type-check + production build into dist/ (Django serves it on one port)
```

Start Django separately: `python manage.py runserver 127.0.0.1:8010`. Override the target with
`DJANGO_URL=http://127.0.0.1:9000 npm run dev`.

## Adding a screen (nobody edits shared files)

Create `src/features/<area>/routes.tsx`:

```tsx
import { lazy } from 'react'
import { FileTextOutlined } from '@ant-design/icons'
import type { AppRoute } from '@/routes/types'

const RecordsList = lazy(() => import('./RecordsList'))

export const routes: AppRoute[] = [
  { path: '/records', element: <RecordsList />, roles: ['institution', 'officer'],
    menu: { label: 'Records', icon: <FileTextOutlined />, order: 10 } },
  { path: '/records/:id', element: <RecordDetail />, roles: ['institution', 'officer'] },
]
// Optional, outside the shell and without sign-in (S6 public NOC check):
export const publicRoutes: AppRoute[] = [{ path: '/verify/:token', element: <VerifyPage /> }]
```

* Routes without `menu` are not shown in the sidebar. A route without `roles` is open to any signed-in
  user with a portal role. The server still enforces every rule.
* A feature that registers `/` replaces the fallback home page (Y5 dashboard).
* Header slots: `src/features/<area>/HeaderSearch.tsx` (Y5) and `src/features/<area>/Bell.tsx` (K5), each a
  default-exported component.
* Restart `npm run dev` after adding the first file of a new feature folder.

## Rules

* All HTTP goes through `src/api/client.ts` (`get`, `post`, `patch`, `upload`, `download`, `api`). It sends the
  CSRF header, reads the server's `{detail, code, errors}` envelope into `ApiError`, and ends the session on 401.
  No tokens in localStorage.
* Every screen handles loading, empty, error, 403 and 409 ("record changed, reload"). Use `QueryBoundary`,
  `QueryError`, `ConflictBanner`, `EmptyState` from `src/components/`.
* Show only the buttons the server allows (`actions` object on detail responses).
* Show server field errors with `applyFieldErrors(form, error)`.
* Writes carry the record `version`; a stale one returns 409.
* No `dangerouslySetInnerHTML`, no inline scripts, no CDN assets (the CSP allows our own origin only).
