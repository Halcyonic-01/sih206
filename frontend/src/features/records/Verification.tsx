import {useState} from 'react';
import {useQuery, useQueryClient} from '@tanstack/react-query';
import {Alert, Button, Empty, Input, Space, Spin, Table, Tag, Upload} from 'antd';
import type {Api} from './types';

type EvidenceData = {level: string; notice: string; checks: {code: string; explanation: string}[];
  evidence: {id: number; method: string; result: string; source: string; created_at: string; instrument_version: number}[]};
type StatementRow = {number: number; utr: string; amount_paise: number; value_date: string; result: string; instrument_id: number | null};
type Preview = {simulated: boolean; rows: StatementRow[]; versions: Record<string, number>};

export function VerificationTab({api, id, version, canRequestBank}: {api: Api; id: number; version: number; canRequestBank: boolean}) {
  const query = useQuery({queryKey: ['records', id, 'verification'], queryFn: () => api.request<EvidenceData>(`/api/instruments/${id}/verification/`)});
  if (query.isPending) return <Spin/>;
  if (query.error) return <Alert type="error" message={String(query.error)}/>;
  return <Space direction="vertical" style={{width: '100%'}}>
    <Alert type="info" message={query.data.notice}/><Tag>{query.data.level}</Tag>
    <p>Declared → Document reviewed → Independently confirmed facts. Simulated matches cannot establish the final step.</p>
    <BankRequests api={api} id={id} version={version} canRequest={canRequestBank}/>
    {query.data.checks.map(check => <Alert key={check.code} type="warning" message={check.code} description={check.explanation}/>)}
    <Table rowKey="id" scroll={{x: 700}} dataSource={query.data.evidence} locale={{emptyText: 'No verification evidence recorded'}} columns={[
      {title: 'Method', dataIndex: 'method'}, {title: 'Result', dataIndex: 'result'},
      {title: 'Source', dataIndex: 'source'}, {title: 'Record version', dataIndex: 'instrument_version'},
      {title: 'Recorded', dataIndex: 'created_at', render: (v: string) => new Date(v).toLocaleString()}]}/>
  </Space>;
}

function BankRequests({api, id, version, canRequest}: {api: Api; id: number; version: number; canRequest: boolean}) {
  const cache = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const query = useQuery({queryKey: ['records', id, 'bank'], queryFn: () => api.request<{
    id: string; status: string; simulated: boolean; expires_at: string; last_error: string}[]>(`/api/instruments/${id}/bank-requests/`)});
  async function request() {
    setBusy(true); setError('');
    try {await api.request(`/api/instruments/${id}/bank-requests/`, {method: 'POST', body: {version}}); await cache.invalidateQueries({queryKey: ['records']});}
    catch (e) {setError(String(e));} finally {setBusy(false);}
  }
  return <Space direction="vertical" style={{width: '100%'}}>
    <h3>Bank confirmation requests</h3>
    <p>Requests use operator-reviewed bank contacts. Links and one-time codes go only to the configured mailbox. Simulation never confirms authenticity.</p>
    {canRequest && <Button loading={busy} onClick={() => void request()}>Request bank confirmation</Button>}
    {(error || query.error) && <Alert type="error" message={error || String(query.error)}/>}
    <Table rowKey="id" loading={query.isPending} pagination={false} dataSource={query.data || []} locale={{emptyText: 'No bank confirmation requests'}} columns={[
      {title: 'Mode', dataIndex: 'simulated', render: (v: boolean) => v ? 'SIMULATED' : 'Bank mailbox'},
      {title: 'Status', dataIndex: 'status'}, {title: 'Expires', dataIndex: 'expires_at', render: (v: string) => new Date(v).toLocaleString()},
      {title: 'Delivery issue', dataIndex: 'last_error'}]}/>
  </Space>;
}

export function ReconciliationPage({api}: {api: Api}) {
  const [file, setFile] = useState<File>();
  const [source, setSource] = useState('Synthetic statement fixture');
  const [preview, setPreview] = useState<Preview>();
  const [rows, setRows] = useState<StatementRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');
  const cache = useQueryClient();
  async function run(commit: boolean) {
    if (!file) return;
    setBusy(true); setError(''); setSaved('');
    try {
      const body = new FormData(); body.set('document', file); body.set('source', source);
      if (commit) {body.set('commit', 'true'); body.set('versions', JSON.stringify(preview?.versions || {}));}
      const result = await api.request<Preview & {id?: number; existing?: boolean}>('/api/verification/statements/', {method: 'POST', body});
      setRows(result.rows);
      if (commit) {setSaved(result.existing ? 'This synthetic batch was already imported.' : `Synthetic batch ${result.id} recorded.`); setPreview(undefined); void cache.invalidateQueries({queryKey: ['records']});}
      else setPreview(result);
    } catch (e) {setError(String(e)); setPreview(undefined);} finally {setBusy(false);}
  }
  return <Space direction="vertical" style={{width: '100%'}}>
    <h2>Statement reconciliation</h2>
    <Alert type="warning" message="SIMULATED DATA ONLY" description="Use synthetic CSV data. This demo never establishes independent bank confirmation. Required headers: utr,amount,value_date. Maximum 1 MB / 1,000 rows."/>
    <label>Source label<Input value={source} maxLength={200} onChange={e => {setSource(e.target.value); setPreview(undefined);}}/></label>
    <Upload maxCount={1} accept=".csv,text/csv" beforeUpload={f => {setFile(f); setPreview(undefined); setRows([]); return false;}}
      onRemove={() => {setFile(undefined); setPreview(undefined); setRows([]);}}><Button>Select synthetic CSV</Button></Upload>
    <Space><Button disabled={!file || !source.trim()} loading={busy} onClick={() => void run(false)}>Preview matches</Button>
      <Button type="primary" disabled={!preview} loading={busy} onClick={() => void run(true)}>Record previewed batch</Button></Space>
    {error && <Alert type="error" role="alert" message={error}/>}{saved && <Alert type="success" message={saved}/>}
    <Table rowKey="number" scroll={{x: 700}} dataSource={rows} locale={{emptyText: <Empty description="Choose a synthetic statement and preview its matches"/>}} columns={[
      {title: 'Row', dataIndex: 'number'}, {title: 'UTR', dataIndex: 'utr'},
      {title: 'Amount INR', dataIndex: 'amount_paise', render: (v: number) => (v / 100).toFixed(2)},
      {title: 'Date', dataIndex: 'value_date'}, {title: 'Result', dataIndex: 'result', render: (v: string) => <Tag>{v}</Tag>},
      {title: 'Record', dataIndex: 'instrument_id', render: (v: number | null) => v ?? 'No unique match'}]}/>
  </Space>;
}
