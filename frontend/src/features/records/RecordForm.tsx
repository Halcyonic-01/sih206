import {useState} from 'react';
import {Alert, Button, Form, Input, InputNumber, Select, Space, Upload} from 'antd';
import type {Api, RecordItem} from './types';

export function RecordForm({api, record, renewal, suggestions, onSaved, onCancel}: {
  api: Api; record?: RecordItem; renewal?: boolean; suggestions?: Record<string, string>; onSaved: (r: RecordItem) => void; onCancel: () => void;
}) {
  const [form] = Form.useForm();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [file, setFile] = useState<File>();
  const mode = Form.useWatch('mode', form) || record?.mode || 'FDR';
  async function save(values: Record<string, unknown>) {
    setBusy(true); setError('');
    try {
      const body = new FormData();
      for (const [key, value] of Object.entries(values)) {
        if (value !== undefined && value !== null && value !== '') body.append(key, String(value));
        if (value === '') body.append(key, '');
      }
      if (record) body.set('version', String(record.version));
      if (file) body.set('document', file);
      const path = renewal ? `/api/instruments/${record!.id}/renew/`
        : record ? `/api/instruments/${record.id}/` : '/api/instruments/';
      onSaved(await api.request<RecordItem>(path, {method: record && !renewal ? 'PATCH' : 'POST', body}));
    } catch (e) {setError(String(e));} finally {setBusy(false);}
  }
  const initial = record ? {...record, lien_marked: record.lien_marked == null ? undefined : String(record.lien_marked),
    ...(renewal ? {reference: '', issue_date: '', maturity_date: ''} : {})} : {mode: 'FDR'};
  return <Form form={form} layout="vertical" initialValues={{...initial, ...suggestions}} onFinish={save}>
    {error && <Alert type="error" role="alert" message={error} style={{marginBottom: 16}}/>}
    <Form.Item name="mode" label="Deposit type" rules={[{required: true}]}><Select options={['FDR', 'RTGS', 'RPGF'].map(value => ({value, label: value}))}/></Form.Item>
    <Form.Item name="reference" label="Instrument reference" rules={[{required: true, max: 100}]}><Input/></Form.Item>
    <Form.Item name="bank" label="Issuing bank" rules={[{required: true, max: 200}]}><Input/></Form.Item>
    <Form.Item name="amount" label="Amount (INR)" rules={[{required: true}]}><Input inputMode="decimal" placeholder="500000.25"/></Form.Item>
    <Form.Item name="issue_date" label="Issue / payment date" rules={[{required: true}]}><Input type="date"/></Form.Item>
    <Form.Item name="maturity_date" label="Maturity / recorded end date" rules={[{required: true}]}><Input type="date"/></Form.Item>
    <Form.Item name="ifsc" label="IFSC" rules={[{pattern: /^[A-Z]{4}0[A-Z0-9]{6}$/, message: 'Use uppercase IFSC format.'}]}><Input maxLength={11}/></Form.Item>
    <Form.Item name="branch" label="Branch"><Input maxLength={200}/></Form.Item>
    <Form.Item name="holder_names" label="Holder names"><Input maxLength={500}/></Form.Item>
    {mode === 'RTGS' && <Form.Item name="utr" label="UTR / payment reference" rules={[{required: true}]}><Input maxLength={100}/></Form.Item>}
    <Form.Item name="lien_marked" label="Declared lien status"><Select allowClear options={[
      {value: 'true', label: 'Lien marked'}, {value: 'false', label: 'No lien declared'}]}/></Form.Item>
    <Form.Item name="obligation_id" label="Obligation ID (optional)" extra="Only an obligation belonging to your institution is accepted."><InputNumber min={1}/></Form.Item>
    <Form.Item label="Supporting PDF"><Upload maxCount={1} accept="application/pdf" beforeUpload={f => {setFile(f); return false;}} onRemove={() => setFile(undefined)}><Button>Select PDF</Button></Upload></Form.Item>
    <Space><Button type="primary" htmlType="submit" loading={busy}>Save draft</Button><Button onClick={onCancel}>Cancel</Button></Space>
  </Form>;
}
