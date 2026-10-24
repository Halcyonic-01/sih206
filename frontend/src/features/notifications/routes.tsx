import { BellOutlined } from '@ant-design/icons'
import { lazy } from 'react'
import type { AppRoute } from '@/routes/types'

const InboxPage = lazy(() => import('./InboxPage'))

export const routes: AppRoute[] = [
  { path: '/notifications', element: <InboxPage />, menu: { label: 'Notifications', icon: <BellOutlined />, order: 90 } },
]
