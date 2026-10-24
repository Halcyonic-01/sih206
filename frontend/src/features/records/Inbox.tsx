import {useState} from 'react';
import {useQuery, useQueryClient} from '@tanstack/react-query';
import {Alert, Button, Space, Spin, Table, Tag} from 'antd';
import type {Api, Role} from './types';

type Notice = {id: number; title: string; reference: string; created_at: string; read_at: string | null};
export function Inbox({api, role}: {api: Api; role: Role}) {
  const cache = useQueryClient();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<number>();
  const query = useQuery({queryKey: ['inbox'], queryFn: () => api.request<Notice[]>('/api/notifications/')});
  const deliveries = useQuery({queryKey: ['deliveries'], enabled: role === 'officer', queryFn: () => api.request<{
    id: number; channel: string; status: string; attempts: number; last_error: string}[]>('/api/notifications/deliveries/')});
  async function read(id: number) {
    setBusy(id); setError('');
    try {await api.request(`/api/notifications/${id}/read/`, {method: 'POST', body: {}}); await cache.invalidateQueries({queryKey: ['inbox']});}
    catch (e) {setError(String(e));} finally {setBusy(undefined);}
  }
  if (query.isPending) return <Spin/>;
  if (query.error) return <Alert type="error" message={String(query.error)} action={<Button onClick={() => void query.refetch()}>Retry</Button>}/>;
  return <Space direction="vertical" style={{width: '100%'}}><h2>Notifications</h2>
    {error && <Alert type="error" message={error}/>}
    <Table rowKey="id" dataSource={query.data} scroll={{x: 650}} locale={{emptyText: 'No notifications'}} columns={[
      {title: 'Update', dataIndex: 'title'}, {title: 'Reference', dataIndex: 'reference'},
      {title: 'Created', dataIndex: 'created_at', render: v => new Date(v).toLocaleString()},
      {title: 'Read', render: (_, row) => row.read_at ? <Tag>Read</Tag> : <Button loading={busy === row.id} onClick={() => void read(row.id)}>Mark read</Button>}]
    }/>
    {role === 'officer' && <><h3>Delivery operations</h3><p>CAPTURED means local test email only. SENT email means accepted by the SMTP relay; it does not prove the recipient read it.</p>
      {deliveries.error && <Alert type="error" message={String(deliveries.error)}/>}
      <Table rowKey="id" loading={deliveries.isPending} dataSource={deliveries.data || []} columns={[
        {title: 'Channel', dataIndex: 'channel'}, {title: 'Status', dataIndex: 'status'},
        {title: 'Attempts', dataIndex: 'attempts'}, {title: 'Issue', dataIndex: 'last_error'}]}/></>}
  </Space>;
}
