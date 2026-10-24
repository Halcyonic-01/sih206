import { useCallback, useRef, useState, useSyncExternalStore, type ReactNode } from 'react'
import { Card } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ME_KEY, useAuth } from '@/auth/AuthProvider'
import { ClearanceQueue, PublicVerification, ReleaseCase, ReleaseWizard } from './releases'
import type { Case, Page } from './client'
import { ErrorBox, Loading, useRemote } from './shared'
import { platformTransport } from './platformTransport'
import { routeIdentity } from './InstitutionPages'
import './institutions.css'

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
  return <Card className="institution-feature"><div key={key}>{children(key)}</div></Card>
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
    <ul aria-label="Required documents">{requirements.documents.map(d => <li key={d.name}>
      {d.name.replaceAll('_', ' ').toLowerCase()}: {d.parsed ? 'uploaded and parsed' : d.present ? 'uploaded, could not be parsed' : 'missing'}
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
  const cases = remote.data.results
  return <section><h1>Release cases</h1>
    {cases.length === 0 ? <p>No release cases yet. Institutions request release from an accepted record.</p> :
      <table><thead><tr><th scope="col">Case</th><th scope="col">Path</th><th scope="col">Mode</th><th scope="col">Status</th><th scope="col">Clearances</th><th scope="col">Next action</th></tr></thead>
        <tbody>{cases.map(c => <tr key={c.id}><td><Link to={`/releases/${c.id}`}>Case {c.id}</Link></td><td>{c.path.replaceAll('_', ' ').toLowerCase()}</td><td>{c.mode}</td>
          <td>{c.status}</td><td>{c.clearances.filter(t => t.status === 'CLEARED').length} of {c.clearances.length} cleared</td><td>{c.next_action}</td></tr>)}</tbody></table>}
    <button disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button>
    <button disabled={page * 25 >= (remote.data.count ?? 0)} onClick={() => setPage(page + 1)}>Next</button>
  </section>
}

export function ReleaseCasePage() {
  const id = routeIdentity(useParams().caseId)
  return <ReleaseSession>{identityKey => id === null ? <ErrorBox error={{ status: 404 }} /> : <>
    <nav aria-label="Release navigation"><Link to="/releases/request">Request release</Link><Link to="/clearance-tasks">Clearance work</Link></nav>
    <ReleaseCase client={platformTransport} identityKey={identityKey} caseId={id} />
  </>}</ReleaseSession>
}

export function ClearanceQueuePage() {
  const navigate = useNavigate()
  return <ReleaseSession>{identityKey => <ClearanceQueue client={platformTransport} identityKey={identityKey}
    onSelect={id => navigate(`/releases/${id}`)} />}</ReleaseSession>
}

export function PublicVerificationPage() {
  const token = useParams().token
  if (!token || !/^[A-Za-z0-9_-]{20,100}$/.test(token)) return <section className="institution-feature"><h1>Verify demo letter</h1><p role="alert">Verification record unavailable.</p></section>
  return <section className="institution-feature"><PublicVerification client={platformTransport} token={token} /></section>
}
