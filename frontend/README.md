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

## Design system

One look for every screen. Tokens live in `src/theme.ts` (Ant Design theme) and as CSS variables in `src/styles.css`;
change both together. All text colours meet WCAG 2.1 AA (4.5:1) and control borders 3:1, which is what GIGW 3.0 builds on.

| Piece | Where | Use |
|---|---|---|
| Colours, type scale, spacing | `theme.ts`, `styles.css` (`:root`) | Navy primary, saffron accent used only for marks and highlights; 15 px body, 4 px spacing steps |
| Logo | `components/Logo.tsx` (`LogoMark`, `Brand`), `public/favicon.svg` | Original Pramaan mark; the official AICTE emblem is not bundled |
| Page title block | `components/PageHeader.tsx` | One `<h1>` per page, with breadcrumb, description and actions |
| Cards, stat tiles, summary lists, filter bar | `components/Panel.tsx` | `Panel`, `StatCard`, `SummaryList`, `FilterBar` |
| Status and verification tags | `components/StatusTag.tsx`, `lib/labels.ts` | Colour never carries meaning alone: the label always says it |
| Money and dates | `lib/format.ts` | ₹ in lakh/crore grouping, `D MMM YYYY` |
| Plain-HTML screens | `.native-ui`, `.data-table`, `.table-scroll` in `styles.css` | Native inputs and buttons styled like the Ant Design ones |
| Shell and navigation | `layout/AppShell.tsx`, `layout/navigation.tsx` | Sidebar from 992 px, drawer below; groups and icons are set in `navigation.tsx` |

Breakpoints: phone < 768 px (record cards instead of wide tables, filters collapse), tablet 768-991 px (drawer navigation),
laptop and desktop from 992 px (fixed sidebar). Tables scroll inside their card; the page never scrolls sideways.
