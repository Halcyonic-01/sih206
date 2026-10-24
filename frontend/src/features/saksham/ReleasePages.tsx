import { useCallback, useSyncExternalStore, type ReactNode } from 'react'
import { Card } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ME_KEY, useAuth } from '@/auth/AuthProvider'
import { ClearanceQueue, PublicVerification, ReleaseCase, ReleaseWizard } from './releases'
import { ErrorBox, Loading } from './shared'
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

export function ReleaseRequestPage() {
  const [query] = useSearchParams()
  const navigate = useNavigate()
  const instrumentId = requestedIdentity(query.get('instrument'))
  const obligationId = requestedIdentity(query.get('obligation'))
  const instrumentVersion = requestedIdentity(query.get('version'))
  return <ReleaseSession>{identityKey => {
    if (instrumentId === null || obligationId === null || instrumentVersion === null) return <>
      <h1>Request release</h1><p role="alert">Select a current instrument and linked obligation from the record workspace. This route needs positive <code>instrument</code>, <code>obligation</code> and <code>version</code> parameters.</p>
    </>
    return <ReleaseWizard client={platformTransport} identityKey={identityKey} onCreated={id => navigate(`/releases/${id}`)} inputs={{
      instrumentId, obligationId, instrumentVersion, canRequest: false, documentsReady: false, documentPath: undefined,
      documents: <p role="alert">The reviewed Affidavit-6 template and path-specific document capability are not yet supplied by the authorized source. Submission remains blocked.</p>,
    }} />
  }}</ReleaseSession>
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
