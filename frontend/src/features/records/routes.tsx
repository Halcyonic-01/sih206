import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, documentBlob, type RequestOptions } from '@/api/client'
import { useAuth } from '@/auth/AuthProvider'
import type { AppRoute } from '@/routes/types'
import type { Api, Role } from './types'
import { DashboardPage, RecordsWorkspace } from './RecordsWorkspace'
import { ReconciliationPage } from './Verification'

export const recordsApi: Api = {
  request<T>(path: string, options?: { method?: string; body?: unknown }) {
    const method = options?.method as RequestOptions['method']
    return api<T>(path, { method, ...(options?.body instanceof FormData
      ? { form: options.body } : options?.body !== undefined ? { json: options.body } : {}) })
  },
  document(id: number) { return documentBlob(`/documents/${id}/download/`) },
}

function RecordsPage() {
  const { user } = useAuth()
  const [query] = useSearchParams()
  const { id } = useParams()
  return <RecordsWorkspace key={id || 'list'} api={recordsApi} role={user!.role as Role}
    readinessAction={query.get('readiness') || undefined} readinessKind={query.get('kind') || undefined}
    readinessObligation={/^[1-9]\d*$/.test(query.get('obligation') || '') ? query.get('obligation')! : undefined}
    globalQuery={query.get('q') || ''} initialCategory={query.get('category') || 'all'} initialRecordId={id ? Number(id) : undefined} />
}

function Dashboard() {
  const navigate = useNavigate()
  return <DashboardPage api={recordsApi} onOpen={(id) => navigate(`/records/${id}`)}
    onCategory={(category) => navigate(`/records?category=${category}`)} />
}

const recordRoles = ['institution', 'officer', 'authority'] as const
export const routes: AppRoute[] = [
  { path: '/records', element: <RecordsPage />, roles: [...recordRoles], menu: { label: 'Records', order: 10 } },
  { path: '/records/:id', element: <RecordsPage />, roles: [...recordRoles] },
  { path: '/workspace', element: <RecordsPage />, roles: [...recordRoles] },
  { path: '/dashboard', element: <Dashboard />, roles: [...recordRoles], menu: { label: 'Dashboard', order: 20 } },
  { path: '/reconciliation', element: <ReconciliationPage api={recordsApi} />, roles: ['officer'], menu: { label: 'Reconciliation', order: 30 } },
]
