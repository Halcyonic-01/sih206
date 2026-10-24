// Temporary integration shell, approved by Yash while K2 is unpublished.
import {createRoot} from 'react-dom/client';
import {useState} from 'react';
import './style.css';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {ConfigProvider, Input, Layout, Typography} from 'antd';
import {RecordsWorkspace} from './features/records/RecordsWorkspace';
import type {Api, Role} from './features/records/types';

async function checked(response: Response) {
  if (response.ok) return response;
  let detail = '';
  const messages = (value: unknown): string => {
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return value.map(messages).join(' ');
    if (value && typeof value === 'object') return Object.entries(value).map(([key, text]) =>
      `${['detail', 'errors', 'non_field_errors'].includes(key) ? '' : key.replaceAll('_', ' ') + ': '}${messages(text)}`).join(' ');
    return '';
  };
  try {detail = messages(await response.json());} catch { /* no HTML diagnostics */ }
  const instruction = response.status === 409 ? 'Record changed. Reload before retrying.'
    : response.status === 403 ? 'Access denied or session expired. Sign in again if needed.' : 'Request failed.';
  throw new Error(`${instruction} ${detail}`.trim());
}
const api: Api = {
  async request<T>(path: string, options?: {method?: string; body?: unknown}): Promise<T> {
    const headers: Record<string, string> = {'Accept': 'application/json'};
    const method = options?.method || 'GET';
    if (method !== 'GET') {
      const token = document.cookie.split('; ').find(v => v.startsWith('csrftoken='))?.slice('csrftoken='.length);
      if (token) headers['X-CSRFToken'] = decodeURIComponent(token);
    }
    let body: BodyInit | undefined;
    if (options?.body instanceof FormData) body = options.body;
    else if (options?.body !== undefined) {headers['Content-Type'] = 'application/json'; body = JSON.stringify(options.body);}
    return (await checked(await fetch(path, {method, body, headers, credentials: 'same-origin'}))).json() as Promise<T>;
  },
  async document(id: number) {
    return (await checked(await fetch(`/api/documents/${id}/download/`, {credentials: 'same-origin'}))).blob();
  }
};
const role = document.querySelector<HTMLMetaElement>('meta[name="portal-role"]')?.content as Role;
const queryClient = new QueryClient({defaultOptions: {queries: {retry: false, staleTime: 10000}}});
function WorkspaceShell() {
  const [search, setSearch] = useState<string>();
  return (
      <Layout style={{minHeight: '100vh', background: '#f3f6fa'}}>
        <Layout.Header style={{display: 'flex', flexWrap: 'wrap', gap: 12, height: 'auto', minHeight: 64, alignItems: 'center', justifyContent: 'space-between', background: '#12324b', padding: '12px 24px'}}>
          <Typography.Title level={4} style={{color: 'white', margin: 0}}>Security Deposit / FDR Portal</Typography.Title>
          <Input.Search aria-label="Global record search" placeholder="Search records" onSearch={setSearch} allowClear style={{width: 280, maxWidth: '100%'}}/>
          <a href="/" style={{color: 'white'}}>Legacy portal</a>
        </Layout.Header>
        <Layout.Content style={{padding: 24, maxWidth: 1400, width: '100%', margin: '0 auto'}}>
          <p style={{color: '#486171'}}>Records workspace · {role} · Synthetic local demonstration</p>
          <RecordsWorkspace api={api} role={role} globalQuery={search}/>
        </Layout.Content>
      </Layout>
  );
}
createRoot(document.getElementById('root')!).render(
  <ConfigProvider theme={{token: {colorPrimary: '#125c83', borderRadius: 8, fontFamily: 'Segoe UI, sans-serif'}}}>
    <QueryClientProvider client={queryClient}>
      <WorkspaceShell/>
    </QueryClientProvider>
  </ConfigProvider>
);
