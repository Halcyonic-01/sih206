import { lazy } from 'react'
import type { AppRoute } from '@/routes/types'

const SecurityPage = lazy(() => import('./SecurityPage'))

/** Reached from the account menu; no menu entry of its own. */
export const routes: AppRoute[] = [
  { path: '/account/security', element: <SecurityPage />, roles: ['officer', 'authority', 'clearance', 'auditor'] },
]
