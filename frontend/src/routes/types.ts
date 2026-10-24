import type { ReactNode } from 'react'
import type { Role } from '@/api/client'

export interface MenuEntry {
  label: string
  icon?: ReactNode
  /** Lower numbers first. Defaults to 100. */
  order?: number
}

export interface AppRoute {
  /** Absolute path, may contain params: '/records/:id'. */
  path: string
  element: ReactNode
  /** Roles allowed to open it; omit to allow any signed-in user with a portal role. */
  roles?: Role[]
  /** Present only for routes that should appear in the sidebar. */
  menu?: MenuEntry
}
