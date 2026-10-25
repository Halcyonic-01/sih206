import { useState } from 'react'
import { Alert, Button, Col, Form, Input, InputNumber, Row, Select, Upload } from 'antd'
import type { Api, RecordItem } from './types'

const half = { xs: 24, md: 12 }

export function RecordForm({ api, record, renewal, suggestions, onSaved, onCancel }: {
  api: Api; record?: RecordItem; renewal?: boolean; suggestions?: Record<string, string>; onSaved: (r: RecordItem) => void; onCancel: () => void
}) {
  const [form] = Form.useForm()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [file, setFile] = useState<File>()
  const mode = Form.useWatch('mode', form) || record?.mode || 'FDR'
  async function save(values: Record<string, unknown>) {
    setBusy(true); setError('')
    try {
      const body = new FormData()
      for (const [key, value] of Object.entries(values)) {
        if (value !== undefined && value !== null && value !== '') body.append(key, String(value))
        if (value === '') body.append(key, '')
      }
      if (record) body.set('version', String(record.version))
      if (file) body.set('document', file)
      const path = renewal ? `/api/instruments/${record!.id}/renew/`
        : record ? `/api/instruments/${record.id}/` : '/api/instruments/'
      onSaved(await api.request<RecordItem>(path, { method: record && !renewal ? 'PATCH' : 'POST', body }))
    } catch (e) { setError(String(e)) } finally { setBusy(false) }
  }
  const initial = record ? { ...record, lien_marked: record.lien_marked == null ? undefined : String(record.lien_marked),
    ...(renewal ? { reference: '', issue_date: '', maturity_date: '' } : {}) } : { mode: 'FDR' }
  return (
    <Form form={form} layout="vertical" initialValues={{ ...initial, ...suggestions }} onFinish={save}>
      {error && <Alert type="error" showIcon role="alert" message={error} style={{ marginBottom: 16 }} />}
      <h3>Deposit</h3>
      <Row gutter={16}>
        <Col {...half}><Form.Item name="mode" label="Deposit type" rules={[{ required: true }]}>
          <Select options={['FDR', 'RTGS', 'RPGF'].map((value) => ({ value, label: value }))} /></Form.Item></Col>
        <Col {...half}><Form.Item name="reference" label="Instrument reference" rules={[{ required: true, max: 100 }]}><Input /></Form.Item></Col>
        <Col {...half}><Form.Item name="bank" label="Issuing bank" rules={[{ required: true, max: 200 }]}><Input /></Form.Item></Col>
        <Col {...half}><Form.Item name="amount" label="Amount (INR)" rules={[{ required: true }]} extra="In rupees, with up to two decimals."><Input inputMode="decimal" /></Form.Item></Col>
        <Col {...half}><Form.Item name="issue_date" label="Issue / payment date" rules={[{ required: true }]}><Input type="date" /></Form.Item></Col>
        <Col {...half}><Form.Item name="maturity_date" label="Maturity / recorded end date" rules={[{ required: true }]}><Input type="date" /></Form.Item></Col>
      </Row>
      <h3>Bank and holders</h3>
      <Row gutter={16}>
        <Col {...half}><Form.Item name="ifsc" label="IFSC" rules={[{ pattern: /^[A-Z]{4}0[A-Z0-9]{6}$/, message: 'Use the uppercase 11-character IFSC.' }]}><Input maxLength={11} /></Form.Item></Col>
        <Col {...half}><Form.Item name="branch" label="Branch"><Input maxLength={200} /></Form.Item></Col>
        <Col xs={24}><Form.Item name="holder_names" label="Holder names"><Input maxLength={500} /></Form.Item></Col>
        {mode === 'RTGS' && <Col {...half}><Form.Item name="utr" label="UTR / payment reference" rules={[{ required: true }]}><Input maxLength={100} /></Form.Item></Col>}
        <Col {...half}><Form.Item name="lien_marked" label="Declared lien status"><Select allowClear options={[
          { value: 'true', label: 'Lien marked' }, { value: 'false', label: 'No lien declared' }]} /></Form.Item></Col>
      </Row>
      <h3>Link and document</h3>
      <Row gutter={16}>
        <Col {...half}><Form.Item name="obligation_id" label="Obligation ID (optional)" extra="Only an obligation of your institution is accepted."><InputNumber min={1} /></Form.Item></Col>
        <Col {...half}><Form.Item label="Supporting PDF">
          <Upload maxCount={1} accept="application/pdf" beforeUpload={(f) => { setFile(f); return false }} onRemove={() => setFile(undefined)}><Button>Select PDF</Button></Upload>
        </Form.Item></Col>
      </Row>
      <div className="cluster" style={{ justifyContent: 'flex-end' }}>
        <Button onClick={onCancel}>Cancel</Button>
        <Button type="primary" htmlType="submit" loading={busy}>Save draft</Button>
      </div>
    </Form>
  )
}
