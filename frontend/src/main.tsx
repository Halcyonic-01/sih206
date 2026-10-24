// Shared session/client integration for the records workspace.
import {createRoot} from 'react-dom/client';
import {useState} from 'react';
import './style.css';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {ConfigProvider, Input, Layout, Typography} from 'antd';
import {RecordsWorkspace} from './features/records/RecordsWorkspace';
import {api} from './api/client';
import {AuthProvider, useAuth} from './auth/AuthProvider';

const queryClient = new QueryClient({defaultOptions: {queries: {retry: false, staleTime: 10000}}});
function WorkspaceShell() {
  const {role} = useAuth();
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
      <AuthProvider><WorkspaceShell/></AuthProvider>
    </QueryClientProvider>
  </ConfigProvider>
);
