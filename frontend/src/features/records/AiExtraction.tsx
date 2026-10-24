import {useState} from 'react';
import {Alert, Button, Checkbox, Space, Table} from 'antd';
import type {Api} from './types';

type Result = {status: string; label: string; detail?: string;
  fields: Record<string, {value: string | null; page: number | null}>;
  findings: {code: string; field: string; declared: string; suggested: string}[]};

export function AiExtraction({api, documentId, canUse, onUse}: {
  api: Api; documentId: number; canUse: boolean; onUse: (values: Record<string, string>) => void;
}) {
  const [consent, setConsent] = useState(false);
  const [result, setResult] = useState<Result>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function extract() {
    setBusy(true); setError(''); setResult(undefined);
    try {setResult(await api.request<Result>(`/api/documents/${documentId}/ai-extract/`, {
      method: 'POST', body: {consent, synthetic: consent}}));}
    catch (e) {setError(String(e));} finally {setBusy(false);}
  }
  return <Space direction="vertical" style={{width: '100%'}}>
    <Alert type="info" message="Optional AI assistance · off by default" description="Manual review remains available. Suggestions cannot change verification, approval or release decisions."/>
    <Checkbox checked={consent} onChange={e => setConsent(e.target.checked)}>I confirm this document is synthetic and authorize sending it to Anthropic for extraction if AI is enabled.</Checkbox>
    <Button loading={busy} onClick={() => void extract()}>Extract with AI</Button>
    {error && <Alert type="error" message={error}/>}
    {result && <Alert type={result.status === 'success' ? 'warning' : 'info'} message={result.label} description={result.detail || 'Review each suggested value against its source page.'}/>}
    {result?.status === 'success' && <>
      <Table rowKey="field" pagination={false} dataSource={Object.entries(result.fields).map(([field, value]) => ({field, ...value}))} columns={[
        {title: 'Field', dataIndex: 'field'}, {title: 'Suggested value', dataIndex: 'value', render: v => v ?? 'Unknown'},
        {title: 'Evidence page', dataIndex: 'page', render: v => v ?? 'Unknown'}]}/>
      {result.findings.map(f => <Alert key={f.field} type="warning" message={`AI_MISMATCH: ${f.field}`} description={`Declared: ${f.declared}. Suggested: ${f.suggested}. Human review required.`}/>)}
      <Button disabled={!canUse} onClick={() => onUse(Object.fromEntries(Object.entries(result.fields)
        .filter(([, value]) => value.value !== null).map(([key, value]) => [key, value.value!])))}>Use extracted values in editable form</Button>
      <small>Prefills only. Review and save explicitly. Accepted records cannot be edited here.</small>
    </>}
  </Space>;
}
