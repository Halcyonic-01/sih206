import {useEffect, useState} from 'react';
import {useQuery, useQueryClient} from '@tanstack/react-query';
import {Alert, Button, Card, Col, Empty, Input, Modal, Row, Select, Space, Spin, Statistic, Table, Tabs, Tag} from 'antd';
import {RecordDetail} from './RecordDetail';
import {RecordForm} from './RecordForm';
import {ReconciliationPage} from './Verification';
import type {Api, DashboardData, Page, RecordItem, Role} from './types';

export function DashboardPage({api, onOpen, onCategory}: {api: Api; onOpen: (id: number) => void; onCategory: (category: string) => void}) {
  const query = useQuery({queryKey: ['records', 'dashboard'], queryFn: () => api.request<DashboardData>('/api/dashboard/')});
  if (query.isPending) return <Spin/>;
  if (query.error) return <Alert type="error" message={String(query.error)} action={<Button onClick={() => void query.refetch()}>Retry</Button>}/>;
  const data = query.data;
  const max = Math.max(1, ...data.maturity_chart.map(m => m.count));
  return <Space direction="vertical" size="large" style={{width: '100%'}}>
    <h2>Deposit overview</h2><span>Business date: {data.as_of} · Asia/Kolkata</span>
    <Row gutter={[16, 16]}>{Object.entries(data.counts).filter(([name]) => name !== 'all').map(([name, count]) => <Col xs={12} md={8} key={name}>
      <Card><Statistic title={name.charAt(0).toUpperCase() + name.slice(1)} value={count}/><Button type="link" onClick={() => onCategory(name)}>View records</Button></Card>
    </Col>)}</Row>
    <Alert type="info" message="Active means accepted and not superseded/released; it includes matured records awaiting action. Expiring and matured are subsets, so do not add all cards."/>
    {!data.coverage_available && <Alert type="warning" message="Requirement shortfall calculation is awaiting Saksham’s S2 integration. Coverage must not be assumed sufficient."/>}
    <Card title="Cases requiring attention"><Table rowKey={r => `${r.kind}:${r.id}`} scroll={{x: 650}} dataSource={data.interventions} locale={{emptyText: 'No cases in these intervention queues'}} columns={[
      {title: 'Reference', dataIndex: 'reference', render: (value: string, row) => <Button type="link" onClick={() => onOpen(row.id)}>{value}</Button>},
      {title: 'Issue', dataIndex: 'kind'}, {title: 'Next action', dataIndex: 'next_action'}]}/></Card>
    <Card title="Upcoming maturities by month">
      {data.maturity_chart.length ? <table style={{width: '100%'}}><thead><tr><th scope="col">Month</th><th scope="col">Records</th><th scope="col">Distribution</th></tr></thead><tbody>
        {data.maturity_chart.map(m => <tr key={m.month}><th scope="row">{m.month}</th><td>{m.count}</td><td style={{width: '60%'}}><div aria-hidden style={{width: `${m.count / max * 100}%`, height: 16, background: '#1677ff', borderRadius: 4}}/></td></tr>)}
      </tbody></table> : <Empty description="No upcoming maturities"/>}
    </Card>
  </Space>;
}

export function RecordsWorkspace({api, role, globalQuery}: {api: Api; role: Role; globalQuery?: string}) {
  const [section, setSection] = useState('records');
  const [selected, setSelected] = useState<number>();
  const [create, setCreate] = useState(false);
  const [q, setQ] = useState('');
  const [category, setCategory] = useState('all');
  const [mode, setMode] = useState('');
  const [page, setPage] = useState(1);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  useEffect(() => {if (globalQuery !== undefined) {setQ(globalQuery); setPage(1); setSelected(undefined); setSection('records');}}, [globalQuery]);
  const cache = useQueryClient();
  const params = new URLSearchParams({q, category, page: String(page), page_size: '20'});
  if (mode) params.set('mode', mode);
  if (from) params.set('maturity_from', from);
  if (to) params.set('maturity_to', to);
  const query = useQuery({queryKey: ['records', 'list', params.toString()], queryFn: () => api.request<Page>(`/api/instruments/?${params}`)});
  if (selected) return <RecordDetail key={selected} api={api} id={selected} onOpen={setSelected} onBack={() => setSelected(undefined)}/>;
  const list = <Space direction="vertical" size="middle" style={{width: '100%'}}>
    <div><h2>Deposit records</h2><p>Search, inspect supporting evidence, and track the next administrative action.</p></div>
    <Space wrap>
      <Input.Search aria-label="Search deposit records" placeholder="Reference, institution, bank, IFSC or UTR" allowClear onSearch={value => {setQ(value); setPage(1);}} style={{width: 340, maxWidth: '100%'}}/>
      <Select aria-label="Record category" value={category} onChange={value => {setCategory(value); setPage(1);}} style={{width: 150}}
        options={['all', 'active', 'expiring', 'matured', 'renewed', 'released', 'pending'].map(value => ({value, label: value}))}/>
      <Select aria-label="Deposit type" value={mode} onChange={value => {setMode(value); setPage(1);}} style={{width: 150}} options={[{value: '', label: 'All deposit types'}, ...['FDR', 'RTGS', 'RPGF'].map(value => ({value, label: value}))]}/>
      <label>Maturity from<Input type="date" aria-label="Maturity from" value={from} onChange={e => {setFrom(e.target.value); setPage(1);}}/></label>
      <label>Maturity to<Input type="date" aria-label="Maturity to" value={to} onChange={e => {setTo(e.target.value); setPage(1);}}/></label>
      <a href={`/api/instruments/export.csv?${params}`}>Export filtered CSV</a>
      {role === 'institution' && <Button type="primary" onClick={() => setCreate(true)}>New deposit</Button>}
    </Space>
    {query.error && <Alert type="error" role="alert" message={String(query.error)} action={<Button onClick={() => void query.refetch()}>Retry</Button>}/>}
    <Table<RecordItem> rowKey="id" loading={query.isPending} dataSource={query.data?.results || []} scroll={{x: 850}}
      pagination={{current: page, pageSize: 20, total: query.data?.count || 0, showSizeChanger: false, onChange: setPage}}
      locale={{emptyText: <Empty description="No records match these filters"/>}} columns={[
        {title: 'Reference', dataIndex: 'reference', render: (value: string, row) => <Button type="link" onClick={() => setSelected(row.id)}>{value}</Button>},
        {title: 'Institution', render: (_, row) => row.institution.name}, {title: 'Type', dataIndex: 'mode'},
        {title: 'Amount INR', dataIndex: 'amount'}, {title: 'Maturity', dataIndex: 'maturity_date'},
        {title: 'Status', dataIndex: 'status', render: (value: string) => <Tag>{value}</Tag>},
        {title: 'Verification', dataIndex: 'verification_level'}]}/>
    <Modal open={create} title="New deposit draft" footer={null} destroyOnHidden onCancel={() => setCreate(false)}>
      <RecordForm api={api} onCancel={() => setCreate(false)} onSaved={item => {setCreate(false); setSelected(item.id); void cache.invalidateQueries({queryKey: ['records']});}}/>
    </Modal>
  </Space>;
  return <Tabs activeKey={section} onChange={setSection} items={[
    {key: 'records', label: 'Records', children: list},
    {key: 'dashboard', label: 'Dashboard', children: <DashboardPage api={api} onOpen={setSelected} onCategory={value => {setCategory(value); setPage(1); setSection('records');}}/>},
    ...(role === 'officer' ? [{key: 'reconciliation', label: 'Reconciliation', children: <ReconciliationPage api={api}/>}] : [])]}/>;
}
