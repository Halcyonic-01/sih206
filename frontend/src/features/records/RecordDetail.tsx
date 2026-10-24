import {useState} from 'react';
import {useQuery, useQueryClient} from '@tanstack/react-query';
import {Alert, Button, Descriptions, Empty, Form, Input, Modal, Select, Space, Spin, Table, Tabs, Tag, Timeline, Upload} from 'antd';
import {PdfViewer} from './PdfViewer';
import {RecordForm} from './RecordForm';
import {VerificationTab} from './Verification';
import {AiExtraction} from './AiExtraction';
import type {Api, RecordItem} from './types';

export function RecordDetail({api, id, onBack, onOpen}: {api: Api; id: number; onBack: () => void; onOpen: (id: number) => void}) {
  const cache = useQueryClient();
  const query = useQuery({queryKey: ['records', id], queryFn: () => api.request<RecordItem>(`/api/instruments/${id}/`)});
  const [action, setAction] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [doc, setDoc] = useState<number>();
  const [page, setPage] = useState(1);
  const [tab, setTab] = useState('details');
  const [file, setFile] = useState<File>();
  const [suggestions, setSuggestions] = useState<Record<string, string>>();
  if (query.isPending) return <Spin/>;
  if (query.error) return <Alert type="error" message={String(query.error)} action={<Button onClick={() => void query.refetch()}>Reload</Button>}/>;
  const item = query.data;
  const docs = item.documents || [];
  const selected = doc ?? docs[0]?.id;
  function changed() {setAction(''); setError(''); setSuggestions(undefined); setFile(undefined); void cache.invalidateQueries({queryKey: ['records']});}
  async function mutate(values: Record<string, unknown>) {
    setBusy(true); setError('');
    try {
      let suffix = action;
      let body: unknown = {...values, version: item.version};
      if (action === 'accept' || action === 'changes') {suffix = 'review'; body = {...values, version: item.version, decision: action};}
      if (action === 'observations') body = {...values, version: item.version, document: selected, page_number: page};
      if (action === 'documents') {
        if (!file) throw new Error('Select a PDF first.');
        const data = new FormData(); data.set('version', String(item.version)); data.set('kind', String(values.kind)); data.set('document', file); body = data;
      }
      await api.request(`/api/instruments/${id}/${suffix}/`, {method: 'POST', body});
      changed();
    } catch (e) {setError(String(e));} finally {setBusy(false);}
  }
  const formAction = action === 'edit' || action === 'renew';
  return <Space direction="vertical" style={{width: '100%'}}>
    <Button onClick={onBack}>← Records</Button>
    <h2>{item.reference}</h2>
    <Space wrap><Tag>{item.status}</Tag><Tag>{item.verification_level}</Tag><span>Version {item.version}</span></Space>
    <Alert type="info" message="Acceptance is for administrative tracking. Document review and simulated evidence do not establish bank authenticity."/>
    <Space wrap>
      {Object.entries({edit: 'Edit draft', submit: 'Submit for review', review: 'Accept for tracking',
        observe: 'Add observation', correct: 'Officer correction', renew: 'Create renewal', upload: 'Upload document'}).map(([key, label]) =>
        item.actions?.[`can_${key}`] && <Button key={key} onClick={() => {setError(''); setAction(key === 'review' ? 'accept' : key === 'observe' ? 'observations' : key === 'upload' ? 'documents' : key);}}>{label}</Button>)}
      {item.actions?.can_review && <Button onClick={() => setAction('changes')}>Request corrections</Button>}
    </Space>
    <Tabs activeKey={tab} onChange={setTab} items={[
      {key: 'details', label: 'Details', children: <Descriptions bordered column={{xs: 1, sm: 2}} items={[
        ['Institution', item.institution.name], ['Bank', item.bank], ['Amount INR', item.amount],
        ['Mode', item.mode], ['Issue date', item.issue_date], ['Maturity date', item.maturity_date],
        ['IFSC', item.ifsc || 'Unknown'], ['Branch', item.branch || 'Unknown'],
        ['Holder names', item.holder_names || 'Unknown'], ['UTR', item.utr || 'Not supplied'],
        ['Obligation ID', item.obligation_id ?? 'Not linked'], ['Lien status', item.lien_marked == null ? 'Unknown' : item.lien_marked ? 'Marked' : 'Not declared marked']
      ].map(([label, value]) => ({key: String(label), label, children: value}))}/>},
      {key: 'documents', label: `Documents (${docs.length})`, children: docs.length ? <Space direction="vertical" style={{width: '100%'}}>
        <Select aria-label="Supporting document" style={{width: '100%'}} value={selected} options={docs.map(d => ({value: d.id, label: `${d.name} · ${d.kind}`}))}
          onChange={value => {setDoc(value); setPage(1);}}/>
        {selected && <><PdfViewer api={api} id={selected} page={page} onPage={setPage}/>
          <AiExtraction key={selected} api={api} documentId={selected} canUse={!!item.actions?.can_edit}
            onUse={values => {setSuggestions(values); setAction('edit');}}/></>}</Space> : <Empty description="No documents uploaded"/>},
      {key: 'checks', label: 'Checks & observations', children: <Space direction="vertical" style={{width: '100%'}}>
        {item.findings?.map(f => <Alert key={f.code} type={f.severity === 'blocking' ? 'error' : 'warning'} message={f.code} description={f.explanation}/>)}
        <Table rowKey="id" scroll={{x: 600}} dataSource={item.observations} columns={[
          {title: 'Observation', dataIndex: 'comment'}, {title: 'Severity', dataIndex: 'severity'},
          {title: 'Evidence', render: (_, o: NonNullable<RecordItem['observations']>[number]) => <Button onClick={() => {setDoc(o.document_id); setPage(o.page_number || 1); setTab('documents');}}>Page {o.page_number ?? 'unspecified'}</Button>},
          {title: 'Resolution', render: (_, o: NonNullable<RecordItem['observations']>[number]) => o.resolved_at ? o.resolution : item.actions?.can_observe ? <Button onClick={() => setAction(`observations/${o.id}/resolve`)}>Resolve</Button> : 'Pending officer action'}]}/></Space>},
      {key: 'verification', label: 'Verification', children: <VerificationTab api={api} id={id} version={item.version} canRequestBank={!!item.actions?.can_request_bank}/>},
      {key: 'lineage', label: 'Lineage', children: <Space direction="vertical">
        {(['predecessor', 'successor'] as const).map(key => <div key={key}>{key}: {item.lineage?.[key] ? <Button onClick={() => onOpen(item.lineage![key]!.id)}>{item.lineage[key]!.reference}</Button> : 'No visible linked record'}</div>)}
        <p>The original stays current until its successor is accepted.</p></Space>},
      {key: 'history', label: 'History', children: <Timeline items={item.history?.map(e => ({key: e.id, children: <><strong>{e.action}</strong><p>{e.reason}</p><small>{new Date(e.at).toLocaleString()}</small></>}))}/>}
    ]}/>
    <Modal open={!!action} title={action.replaceAll('/', ' · ')} footer={null} destroyOnHidden onCancel={() => {setAction(''); setSuggestions(undefined); setFile(undefined);}}>
      {error && <Alert type="error" role="alert" message={error} action={<Button onClick={() => {changed(); void query.refetch();}}>Reload record</Button>}/>}
      {formAction ? <RecordForm api={api} record={item} renewal={action === 'renew'} suggestions={action === 'edit' ? suggestions : undefined} onCancel={() => {setAction(''); setSuggestions(undefined);}}
        onSaved={saved => {changed(); onOpen(saved.id);}}/> : <Form layout="vertical" onFinish={mutate}>
        {['accept', 'changes', 'correct'].includes(action) && <Form.Item name="reason" label="Reason" rules={[{required: true}]}><Input.TextArea maxLength={2000}/></Form.Item>}
        {action === 'correct' && <><Form.Item name="amount" label="Corrected amount INR"><Input/></Form.Item><Form.Item name="bank" label="Corrected bank"><Input/></Form.Item></>}
        {action === 'observations' && <><p>Document {selected ?? 'not selected'}, page {page}. Choose evidence in the Documents tab first.</p>
          <Form.Item name="severity" label="Severity" rules={[{required: true}]}><Select options={[{value: 'WARNING', label: 'Warning'}, {value: 'BLOCKING', label: 'Blocking'}]}/></Form.Item>
          <Form.Item name="comment" label="Observation" rules={[{required: true}]}><Input.TextArea maxLength={2000}/></Form.Item></>}
        {action.endsWith('/resolve') && <Form.Item name="resolution" label="How was it resolved?" rules={[{required: true}]}><Input.TextArea maxLength={2000}/></Form.Item>}
        {action === 'documents' && <><Form.Item name="kind" label="Document category" rules={[{required: true}]}><Select options={['FDR', 'PAYMENT_PROOF', 'RPGF_PROOF', 'AFFIDAVIT_3', 'AFFIDAVIT_6', 'APPROVAL_LETTER', 'BANK_CERTIFICATE', 'REQUEST_LETTER', 'STUDENT_CLEARANCE', 'EXTERNAL_NOC'].map(value => ({value, label: value.replaceAll('_', ' ')}))}/></Form.Item>
          <Upload maxCount={1} beforeUpload={f => {setFile(f); return false;}} onRemove={() => setFile(undefined)} accept=".pdf"><Button>Select PDF</Button></Upload></>}
        {action === 'submit' && <p>Submit this record and its supporting document for officer review?</p>}
        <Button type="primary" htmlType="submit" loading={busy} style={{marginTop: 16}}>Record action</Button>
      </Form>}
    </Modal>
  </Space>;
}
