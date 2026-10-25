import {
  AuditOutlined, BankOutlined, BarChartOutlined, BellOutlined, CheckSquareOutlined, DashboardOutlined, FileTextOutlined,
  FolderOpenOutlined, LineChartOutlined, SafetyCertificateOutlined, SwapOutlined, UploadOutlined,
} from '@ant-design/icons'
import type { ReactNode } from 'react'
import type { AppRoute } from '@/routes/types'

export const GROUPS = ['Overview', 'Deposits', 'Institutions', 'Release', 'Insights', 'Administration'] as const
export type Group = typeof GROUPS[number]

interface Meta { group: Group; label?: string; icon: ReactNode; description: string }

/** Presentation of each screen: its sidebar group, label, icon and the one-line description on the start page. */
const META: Record<string, Meta> = {
  '/dashboard': { group: 'Overview', icon: <DashboardOutlined />, description: 'Deposit status, items needing action and upcoming maturities.' },
  '/notifications': { group: 'Overview', icon: <BellOutlined />, description: 'Reminders, review results and alerts for your account.' },
  '/records': { group: 'Deposits', label: 'Deposit records', icon: <FileTextOutlined />, description: 'Search deposits, review documents and follow each one to its outcome.' },
  '/reconciliation': { group: 'Deposits', label: 'Reconciliation', icon: <SwapOutlined />, description: 'Match bank statement lines against RTGS deposits.' },
  '/institutions': { group: 'Institutions', icon: <BankOutlined />, description: 'Profiles, programme approvals and the deposit each institution owes.' },
  '/releases': { group: 'Release', label: 'Release cases', icon: <FolderOpenOutlined />, description: 'Track release requests through clearances, decision and letter.' },
  '/clearance-tasks': { group: 'Release', label: 'Clearance work', icon: <CheckSquareOutlined />, description: 'Release cases waiting for your unit’s decision.' },
  '/reports': { group: 'Insights', icon: <BarChartOutlined />, description: 'Download pending, maturing, missing-document and released registers.' },
  '/kpis': { group: 'Insights', label: 'Process KPIs', icon: <LineChartOutlined />, description: 'Turnaround, correction cycles and renewal timeliness.' },
  '/imports/institutions': { group: 'Administration', label: 'Import institutions', icon: <UploadOutlined />, description: 'Preview and load institutions from a CSV file.' },
  '/audit': { group: 'Administration', label: 'Audit and access', icon: <SafetyCertificateOutlined />, description: 'Full change history, access log and audit-trail verification.' },
}

export interface NavItem { path: string; label: string; icon: ReactNode; group: Group; description: string; order: number }

export function navItemsFor(routes: AppRoute[], role: string | null): NavItem[] {
  return routes
    .filter((route) => route.menu && (!route.roles || (role && route.roles.includes(role as never))))
    .map((route) => {
      const meta = META[route.path]
      return {
        path: route.path,
        label: meta?.label ?? route.menu!.label,
        icon: meta?.icon ?? route.menu!.icon ?? <AuditOutlined />,
        group: meta?.group ?? 'Overview',
        description: meta?.description ?? '',
        order: route.menu!.order ?? 100,
      }
    })
    .sort((a, b) => GROUPS.indexOf(a.group) - GROUPS.indexOf(b.group) || a.order - b.order)
}

/** Longest matching path wins, so /records/12 highlights "Deposit records". */
export function selectedPath(items: NavItem[], pathname: string): string[] {
  const match = items
    .filter((item) => pathname === item.path || pathname.startsWith(item.path.replace(/\/$/, '') + '/'))
    .sort((a, b) => b.path.length - a.path.length)[0]
  return match ? [match.path] : []
}
