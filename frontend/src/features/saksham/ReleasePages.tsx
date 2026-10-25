import { useCallback, useRef, useState, useSyncExternalStore, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Table } from 'antd'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Brand } from '@/components/Logo'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { StatusTag } from '@/components/StatusTag'
import { humanize, RELEASE_PATH_LABELS } from '@/lib/labels'
import { ME_KEY, useAuth } from '@/auth/AuthProvider'
import { ClearanceQueue, PublicVerification, ReleaseCase, ReleaseWizard } from './releases'
import type { Case, Page } from './client'
import { ErrorBox, Loading, Notice, useRemote } from './shared'
import { platformTransport } from './platformTransport'
import { routeIdentity } from './InstitutionPages'

/** Session-bound wrapper for the release screens. It deliberately does not
 * manufacture a questionnaire, document capability, or clearance assignment. */
function ReleaseSession({ children }: { children: (identityKey: string) => ReactNode }) {
  const auth = useAuth()
  const cache = useQueryClient()
  const subscribe = useCallback((notify: () => void) => cache.getQueryCache().subscribe(event => {
    if (event.query.queryKey[0] === ME_KEY[0] && event.query.queryKey[1] === ME_KEY[1]) notify()
  }), [cache])
  const snapshot = useCallback(() => cache.getQueryState(ME_KEY)?.dataUpdateCount ?? 0, [cache])
  const generation = useSyncExternalStore(subscribe, snapshot, snapshot)
  if (auth.status === 'loading') return <Loading />
  if (auth.status !== 'authenticated' || !auth.user) return <ErrorBox error={{ status: auth.status === 'error' ? 503 : 401 }} />
  if (!auth.user.role || !['institution', 'officer', 'authority', 'clearance'].includes(auth.user.role)) {
    return <ErrorBox error={{ status: 403 }} />
  }
  const key = JSON.stringify([generation, auth.user.id, auth.user.role, auth.user.institution?.id, auth.user.unit])
  return <div className="native-ui" key={key}>{children(key)}</div>
}

function requestedIdentity(value: string | null): number | null {
  return routeIdentity(value ?? undefined)
}

interface Requirements {
  questionnaire: { version: string; questions: { id: string; label: string }[] }
  path: string; mode: string; eligible: boolean; documents_ready: boolean; instrument_version: number
  term_end: string | null; term_elapsed: boolean
  documents: { name: string; kind: string; present: boolean; parsed: boolean }[]
}

/** Loads the server's questionnaire and checklist for the chosen path; the server still decides every gate. */
function RequestWithRequirements({ identityKey, instrumentId, obligationId, instrumentVersion, onCreated }: {
  identityKey: string; instrumentId: number; obligationId: number; instrumentVersion: number; onCreated: (id: number) => void
}) {
  const [path, setPath] = useState('TERM_COMPLETE')
  const remote = useRemote<Requirements>(platformTransport,
    `releases/requirements?instrument=${instrumentId}&obligation=${obligationId}&path=${path}`, identityKey)
  // Keep the last answer while a new path loads, so the wizard (keyed on the questionnaire) keeps its state.
  const last = useRef<Requirements>(undefined)
  if (remote.data) last.current = remote.data
  const requirements = last.current
  if (remote.error) return <ErrorBox error={remote.error} />
  if (!requirements) return <Loading />
  const current = remote.data !== undefined
  const documents = <>
    <ul aria-label="Required documents" className="checklist">{requirements.documents.map(d => <li key={d.name}>
      <StatusTag value={d.parsed ? 'CLEARED' : d.present ? 'HOLD' : 'OBJECTION'} />
      {' '}{humanize(d.name)}: {d.parsed ? 'uploaded and readable' : d.present ? 'uploaded, but could not be read' : 'missing'}
    </li>)}</ul>
    {!requirements.documents_ready && <p role="alert">Upload the missing documents on the <Link to={`/records/${instrumentId}`}>record page</Link> (Upload release document), then reload this page.</p>}
    {path === 'TERM_COMPLETE' && !requirements.term_elapsed && <p role="alert">The obligation term ends on {requirements.term_end ?? 'an unknown date'}; a term-complete release is blocked until it has elapsed.</p>}
  </>
  return <ReleaseWizard client={platformTransport} identityKey={identityKey} onCreated={onCreated} inputs={{
    instrumentId, obligationId, instrumentVersion: requirements.instrument_version ?? instrumentVersion,
    canRequest: current && requirements.eligible, questionnaire: requirements.questionnaire,
    documentPath: current ? requirements.path : undefined, onPathChange: setPath,
    documentsReady: current && requirements.documents_ready, documents,
  }} />
}

export function ReleaseRequestPage() {
  const [query] = useSearchParams()
  const navigate = useNavigate()
  const instrumentId = requestedIdentity(query.get('instrument'))
  const obligationId = requestedIdentity(query.get('obligation'))
  const instrumentVersion = requestedIdentity(query.get('version'))
  return <ReleaseSession>{identityKey => {
    if (instrumentId === null || obligationId === null || instrumentVersion === null) return <>
      <h1>Request release</h1><p role="alert">Open a current accepted record that is linked to an obligation and choose <strong>Request release</strong> there.</p>
      <Link to="/records">Go to records</Link>
    </>
    return <RequestWithRequirements identityKey={identityKey} instrumentId={instrumentId} obligationId={obligationId}
      instrumentVersion={instrumentVersion} onCreated={id => navigate(`/releases/${id}`)} />
  }}</ReleaseSession>
}

/** Officers, the authority and institutions find their cases here; clearance units use their queue. */
export function ReleaseCasesPage() {
  const [page, setPage] = useState(1)
  return <ReleaseSession>{identityKey => <CaseList identityKey={identityKey} page={page} setPage={setPage} />}</ReleaseSession>
}

function CaseList({ identityKey, page, setPage }: { identityKey: string; page: number; setPage: (page: number) => void }) {
  const remote = useRemote<Page<Case>>(platformTransport, `releases?page=${page}`, identityKey)
  if (remote.error) return <ErrorBox error={remote.error} />
  if (!remote.data) return <Loading />
  return <section>
    <PageHeader title="Release cases" subtitle="Release requests from submission through clearances, decision, letter and completion." />
    <Notice />
    <Panel flush>
      <Table<Case> rowKey="id" size="middle" scroll={{ x: 760 }} dataSource={remote.data.results}
        locale={{ emptyText: 'No release cases yet. An institution requests release from an accepted deposit record.' }}
        pagination={{ current: page, pageSize: 25, total: remote.data.count ?? 0, onChange: setPage, hideOnSinglePage: true, showSizeChanger: false }}
        columns={[
          { title: 'Case', dataIndex: 'id', render: (id: number) => <Link to={`/releases/${id}`}>Case {id}</Link> },
          { title: 'Path', dataIndex: 'path', render: (v: string) => RELEASE_PATH_LABELS[v] ?? humanize(v) },
          { title: 'Type', dataIndex: 'mode', width: 90 },
          { title: 'Status', dataIndex: 'status', render: (v: string) => <StatusTag value={v} /> },
          { title: 'Clearances', render: (_, c) => `${c.clearances.filter(t => t.status === 'CLEARED').length} of ${c.clearances.length} cleared` },
          { title: 'Next step', dataIndex: 'next_action' }]} />
    </Panel>
  </section>
}

export function ReleaseCasePage() {
  const id = routeIdentity(useParams().caseId)
  return <ReleaseSession>{identityKey => id === null ? <ErrorBox error={{ status: 404 }} /> :
    <ReleaseCase client={platformTransport} identityKey={identityKey} caseId={id} />}</ReleaseSession>
}

export function ClearanceQueuePage() {
  const navigate = useNavigate()
  return <ReleaseSession>{identityKey => <ClearanceQueue client={platformTransport} identityKey={identityKey}
    onSelect={id => navigate(`/releases/${id}`)} />}</ReleaseSession>
}

export function PublicVerificationPage() {
  const token = useParams().token
  const valid = token && /^[A-Za-z0-9_-]{20,100}$/.test(token)
  return <main className="verify-page">
    <Brand size={42} />
    <div className="verify-card native-ui">
      {valid ? <PublicVerification client={platformTransport} token={token} />
        : <section><h1>Verify letter</h1><p role="alert">Verification record unavailable.</p></section>}
    </div>
  </main>
}
