import {useState} from 'react';
import {useQuery, useQueryClient} from '@tanstack/react-query';
import {Alert, Button, Empty, Input, Table, Upload} from 'antd';
import {PageHeader} from '@/components/PageHeader';
import {Panel} from '@/components/Panel';
import {StatusTag, VerificationTag} from '@/components/StatusTag';
import {LoadingState} from '@/components/states';
import {formatDate, formatDateTime, formatPaise} from '@/lib/format';
import {findingLabel, humanize} from '@/lib/labels';
import type {Api} from './types';

type EvidenceData = {level: string; notice: string; checks: {code: string; explanation: string}[];
  evidence: {id: number; method: string; result: string; source: string; created_at: string; instrument_version: number}[]};
type StatementRow = {number: number; utr: string; amount_paise: number; value_date: string; result: string; instrument_id: number | null};
type Preview = {simulated: boolean; rows: StatementRow[]; versions: Record<string, number>};

export function VerificationTab({api, id, version, canRequestBank}: {api: Api; id: number; version: number; canRequestBank: boolean}) {
  const query = useQuery({queryKey: ['records', id, 'verification'], queryFn: () => api.request<EvidenceData>(`/api/instruments/${id}/verification/`)});
  if (query.isPending) return <LoadingState/>;
  if (query.error) return <Alert type="error" showIcon message="Verification details could not be loaded" description={String(query.error)}/>;
  return <div className="stack">
    <Panel title="Verification level" extra={<VerificationTag value={query.data.level}/>}>
      <p>A deposit moves from <strong>Declared</strong> to <strong>Document reviewed</strong> when an officer checks the PDF, and to <strong>Confirmed</strong> when a bank statement line matches it.</p>
      <p className="muted">{query.data.notice} Statements and bank replies in this environment are SIMULATED, so Confirmed means the fields match a synthetic line, not that a bank authenticated the deposit.</p>
    </Panel>
    {query.data.checks.map(check => <Alert key={check.code} type="warning" showIcon message={findingLabel(check.code)} description={check.explanation}/>)}
    <BankRequests api={api} id={id} version={version} canRequest={canRequestBank}/>
    <Panel title="Evidence recorded" flush>
      <Table rowKey="id" size="middle" scroll={{x: 640}} pagination={false} dataSource={query.data.evidence}
        locale={{emptyText: 'No verification evidence recorded yet.'}} columns={[
        {title: 'Method', dataIndex: 'method', render: (v: string) => humanize(v)},
        {title: 'Result', dataIndex: 'result', render: (v: string) => humanize(v)},
        {title: 'Source', dataIndex: 'source'}, {title: 'Record version', dataIndex: 'instrument_version', width: 130},
        {title: 'Recorded', dataIndex: 'created_at', render: (v: string) => formatDateTime(v)}]}/>
    </Panel>
  </div>;
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
  return <Panel title="Bank confirmation requests" extra={canRequest && <Button loading={busy} onClick={() => void request()}>Request bank confirmation</Button>}>
    <p className="muted">Requests go only to bank contacts reviewed by the operator, with a one-time link and code. A simulated reply never confirms authenticity.</p>
    {(error || query.error) && <Alert type="error" showIcon message={error || String(query.error)} style={{marginBottom: 12}}/>}
    <Table rowKey="id" size="middle" loading={query.isPending} scroll={{x: 520}} pagination={false} dataSource={query.data || []}
      locale={{emptyText: 'No bank confirmation requests yet.'}} columns={[
      {title: 'Channel', dataIndex: 'simulated', render: (v: boolean) => v ? 'Simulated' : 'Bank mailbox'},
      {title: 'Status', dataIndex: 'status', render: (v: string) => <StatusTag value={v}/>},
      {title: 'Expires', dataIndex: 'expires_at', render: (v: string) => formatDateTime(v)},
      {title: 'Delivery issue', dataIndex: 'last_error', render: (v: string) => v || '—'}]}/>
  </Panel>;
}

export function ReconciliationPage({api}: {api: Api}) {
  const [file, setFile] = useState<File>();
  const [source, setSource] = useState('');
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
      if (commit) {setSaved(result.existing ? 'This statement was already imported.' : `Statement batch ${result.id} recorded.`); setPreview(undefined); void cache.invalidateQueries({queryKey: ['records']});}
      else setPreview(result);
    } catch (e) {setError(String(e)); setPreview(undefined);} finally {setBusy(false);}
  }
  const matched = rows.filter(row => row.result === 'SIMULATED_MATCH').length;
  return <div className="stack stack--lg">
    <PageHeader title="Statement reconciliation" subtitle="Match bank statement lines to RTGS deposits by payment reference, amount and value date."/>
    <Alert type="warning" showIcon message="Simulated data only" description="A line that matches confirms the RTGS deposit (simulated statement). A mismatch marks it as a discrepancy and alerts the institution. CSV columns: utr, amount, value_date (up to 1 MB and 1,000 rows)."/>
    <Panel title="1. Choose a statement">
      <div className="stack">
        <div style={{maxWidth: 520}}>
          <label className="field-label" htmlFor="stmt-source">Source label (for example the statement date)</label>
          <Input id="stmt-source" value={source} maxLength={200} onChange={e => {setSource(e.target.value); setPreview(undefined);}}/>
        </div>
        <Upload maxCount={1} accept=".csv,text/csv" beforeUpload={f => {setFile(f); setPreview(undefined); setRows([]); return false;}}
          onRemove={() => {setFile(undefined); setPreview(undefined); setRows([]);}}><Button>Select CSV file</Button></Upload>
        <div className="cluster"><Button disabled={!file || !source.trim()} loading={busy} onClick={() => void run(false)}>Preview matches</Button>
          <Button type="primary" disabled={!preview} loading={busy} onClick={() => void run(true)}>Record previewed batch</Button></div>
      </div>
    </Panel>
    {error && <Alert type="error" showIcon role="alert" message={error}/>}{saved && <Alert type="success" showIcon message={saved}/>}
    <Panel title={rows.length ? `2. Preview: ${matched} of ${rows.length} lines match` : '2. Preview'} flush>
      <Table rowKey="number" size="middle" scroll={{x: 640}} dataSource={rows} locale={{emptyText: <Empty description="Choose a statement and preview its matches."/>}} columns={[
        {title: 'Row', dataIndex: 'number', width: 70}, {title: 'UTR', dataIndex: 'utr'},
        {title: 'Amount', dataIndex: 'amount_paise', align: 'right', render: (v: number) => formatPaise(v)},
        {title: 'Date', dataIndex: 'value_date', render: (v: string) => formatDate(v)},
        {title: 'Result', dataIndex: 'result', render: (v: string) => <StatusTag value={v}/>},
        {title: 'Record', dataIndex: 'instrument_id', render: (v: number | null) => v ?? 'No unique match'}]}/>
    </Panel>
  </div>;
}
