import { AuditOutlined } from '@ant-design/icons'
import { lazy } from 'react'
import type { AppRoute } from '@/routes/types'

const AuditPage = lazy(() => import('./AuditPage'))

export const routes: AppRoute[] = [
  { path: '/audit', element: <AuditPage />, roles: ['auditor'], menu: { label: 'Audit and access', icon: <AuditOutlined />, order: 80 } },
]
