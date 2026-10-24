import { useCallback, useSyncExternalStore, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Card } from 'antd';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ME_KEY, useAuth } from '@/auth/AuthProvider';
import type { Institution } from './client';
import { Calculator, InstitutionDetail, InstitutionList } from './institutions';
import { ErrorBox, Loading, useRemote } from './shared';
import { platformTransport } from './platformTransport';
import './institutions.css';

export function InstitutionSession({ children }: { children: (identityKey: string) => ReactNode }) {
  const auth = useAuth();
  const cache = useQueryClient();
  const subscribe = useCallback((notify: () => void) => cache.getQueryCache().subscribe(event => {
    if (event.query.queryKey[0] === ME_KEY[0] && event.query.queryKey[1] === ME_KEY[1]) notify();
  }), [cache]);
  const snapshot = useCallback(() => cache.getQueryState(ME_KEY)?.dataUpdateCount ?? 0, [cache]);
  const generation = useSyncExternalStore(subscribe, snapshot, snapshot);
  if (auth.status === 'loading') return <Loading />;
  if (auth.status !== 'authenticated' || !auth.user) {
    return <ErrorBox error={{ status: auth.status === 'error' ? 503 : 401 }} />;
  }
  if (!auth.user.role || !['institution', 'officer', 'authority'].includes(auth.user.role)) {
    return <ErrorBox error={{ status: 403 }} />;
  }
  // dataUpdateCount changes on setQueryData even for a structurally identical
  // same-user login; no auth state, session generation or token is invented here.
  const key = JSON.stringify([generation, auth.user.id, auth.user.role, auth.user.institution?.id, auth.user.unit]);
  return <Card className="institution-feature"><div key={key}>{children(key)}</div></Card>;
}

export function routeIdentity(raw: string | undefined): number | null {
  if (!raw || !/^[1-9]\d*$/.test(raw)) return null;
  const value = Number(raw);
  return Number.isSafeInteger(value) ? value : null;
}

export function InstitutionsPage() {
  const navigate = useNavigate();
  return <InstitutionSession>{identityKey => <InstitutionList client={platformTransport} identityKey={identityKey}
    onSelect={id => navigate(`/institutions/${id}`)} />}</InstitutionSession>;
}

export function InstitutionPage() {
  const id = routeIdentity(useParams().id);
  return <InstitutionSession>{identityKey => id === null ? <ErrorBox error={{ status: 404 }} /> : <>
    <nav aria-label="Institution navigation"><Link to="/institutions">Institutions</Link>
      <Link to={`/institutions/${id}/calculator`}>Requirement calculator</Link></nav>
    <InstitutionDetail client={platformTransport} identityKey={identityKey} institutionId={id} />
  </>}</InstitutionSession>;
}

function ScopedCalculator({ id, identityKey }: { id: number; identityKey: string }) {
  const parent = useRemote<Institution>(platformTransport, `institutions/${id}`, identityKey);
  if (parent.error) return <ErrorBox error={parent.error} />;
  if (!parent.data) return <Loading />;
  return <><nav aria-label="Calculator navigation"><Link to="/institutions">Institutions</Link>
    <Link to={`/institutions/${id}`}>{parent.data.name}</Link></nav>
    <Calculator client={platformTransport} institutionId={id} identityKey={identityKey} /></>;
}

export function InstitutionCalculatorPage() {
  const id = routeIdentity(useParams().id);
  return <InstitutionSession>{identityKey => id === null ? <ErrorBox error={{ status: 404 }} /> :
    <ScopedCalculator key={`${identityKey}:${id}`} id={id} identityKey={identityKey} />}</InstitutionSession>;
}
