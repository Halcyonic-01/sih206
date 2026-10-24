import {createContext, useContext, type ReactNode} from 'react';
import {useQuery} from '@tanstack/react-query';
import {Alert, Spin} from 'antd';
import {api} from '../api/client';
import type {Role} from '../features/records/types';

type Session = {id: number; username: string; role: Role; institution_id: number | null};
const Auth = createContext<Session | undefined>(undefined);
export function AuthProvider({children}: {children: ReactNode}) {
  const query = useQuery({queryKey: ['session'], queryFn: () => api.request<Session>('/api/auth/me/'), staleTime: 60000});
  if (query.isPending) return <Spin fullscreen/>;
  if (query.error) return <Alert type="error" message="Unable to load your portal session" description={<a href="/accounts/login/?next=/workspace/">Sign in again</a>}/>;
  return <Auth.Provider value={query.data}>{children}</Auth.Provider>;
}
export function useAuth() {
  const session = useContext(Auth);
  if (!session) throw new Error('Portal session is required.');
  return session;
}
