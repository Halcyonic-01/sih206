import { useAuth } from '@/auth/AuthProvider';
import { InstitutionSession } from './InstitutionPages';
import { ErrorBox } from './shared';
import { InstitutionImport, Kpis, Reports } from './reports';
import { platformTransport } from './platformTransport';

export function ReportsPage() {
  return <InstitutionSession>{identityKey => <Reports client={platformTransport} identityKey={identityKey} />}</InstitutionSession>;
}
export function KpisPage() {
  return <InstitutionSession>{identityKey => <Kpis client={platformTransport} identityKey={identityKey} />}</InstitutionSession>;
}
export function InstitutionImportPage() {
  const { user } = useAuth();
  return <InstitutionSession>{identityKey => user?.role === 'officer' ?
    <InstitutionImport client={platformTransport} identityKey={identityKey} /> : <ErrorBox error={{ status: 403 }} />}</InstitutionSession>;
}
