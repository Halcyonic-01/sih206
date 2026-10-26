import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Collapse, Empty, Form, Input, Modal, Select, Table, Tabs, Tag, Timeline, Upload } from 'antd'
import { PageHeader } from '@/components/PageHeader'
import { Panel, SummaryList } from '@/components/Panel'
import { StatusTag, VerificationTag } from '@/components/StatusTag'
import { LoadingState } from '@/components/states'
import { formatDate, formatDateTime, formatInr } from '@/lib/format'
import { findingLabel, humanize } from '@/lib/labels'
import { AiExtraction } from './AiExtraction'
import { PdfViewer } from './PdfViewer'
import { ProvenanceTag } from './ProvenanceTag'
import { RecordForm } from './RecordForm'
import { VerificationTab } from './Verification'
import type { Api, RecordItem } from './types'

const DOCUMENT_KINDS = ['FDR', 'PAYMENT_PROOF', 'RPGF_PROOF', 'AFFIDAVIT_3', 'AFFIDAVIT_6', 'APPROVAL_LETTER', 'BANK_CERTIFICATE', 'REQUEST_LETTER', 'STUDENT_CLEARANCE', 'EXTERNAL_NOC']
const RELEASE_KINDS = ['REQUEST_LETTER', 'AFFIDAVIT_6', 'APPROVAL_LETTER', 'STUDENT_CLEARANCE', 'EXTERNAL_NOC']
const kindOptions = (kinds: string[]) => kinds.map((value) => ({ value, label: humanize(value) }))

const MODAL_TITLES: Record<string, string> = {
  edit: 'Edit draft', renew: 'Create renewal', submit: 'Submit for review', accept: 'Accept for tracking',
  changes: 'Request corrections', correct: 'Officer correction', observations: 'Add observation',
  documents: 'Upload document', 'release documents': 'Upload release document',
}

export function RecordDetail({ api, id, onBack, onOpen }: { api: Api; id: number; onBack: () => void; onOpen: (id: number) => void }) {
  const cache = useQueryClient()
  const query = useQuery({ queryKey: ['records', id], queryFn: () => api.request<RecordItem>(`/api/instruments/${id}/`) })
  const [action, setAction] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [doc, setDoc] = useState<number>()
  const [page, setPage] = useState(1)
  const [tab, setTab] = useState('details')
  const [file, setFile] = useState<File>()
  const [suggestions, setSuggestions] = useState<Record<string, string>>()
  if (query.isPending) return <><PageHeader title="Deposit record" /><LoadingState rows={6} /></>
  if (query.error) {
    return <><Button className="back-link" type="link" onClick={onBack}>← All deposit records</Button><PageHeader title="Deposit record" />
      <Alert type="error" showIcon message="This record could not be loaded" description={String(query.error)}
             action={<Button onClick={() => void query.refetch()}>Try again</Button>} /></>
  }
  const item = query.data
  const docs = item.documents || []
  const selected = doc ?? docs[0]?.id
  const can = (key: string) => Boolean(item.actions?.[`can_${key}`])
  const tagged = (value: ReactNode, field: string) => (value ? <>{value}<ProvenanceTag provenance={item.field_provenance?.[field]} /></> : value)
  function changed() { setAction(''); setError(''); setSuggestions(undefined); setFile(undefined); void cache.invalidateQueries({ queryKey: ['records'] }) }
  async function mutate(values: Record<string, unknown>) {
    setBusy(true); setError('')
    try {
      let suffix = action
      let body: unknown = { ...values, version: item.version }
      if (action === 'accept' || action === 'changes') { suffix = 'review'; body = { ...values, version: item.version, decision: action } }
      if (action === 'observations') body = { ...values, version: item.version, document: selected, page_number: page }
      if (action === 'release documents') suffix = 'documents'
      if (action === 'documents' || action === 'release documents') {
        if (!file) throw new Error('Select a PDF first.')
        const data = new FormData(); data.set('version', String(item.version)); data.set('kind', String(values.kind)); data.set('document', file); body = data
      }
      await api.request(`/api/instruments/${id}/${suffix}/`, { method: 'POST', body })
      changed()
    } catch (e) { setError(String(e)) } finally { setBusy(false) }
  }
  const formAction = action === 'edit' || action === 'renew'
  const modalTitle = MODAL_TITLES[action] ?? (action.endsWith('/resolve') ? 'Resolve observation' : 'Record action')
  const openAction = (next: string) => { setError(''); setAction(next) }

  const actions = (
    <>
      {can('edit') && <Button onClick={() => openAction('edit')}>Edit draft</Button>}
      {can('submit') && <Button type="primary" onClick={() => openAction('submit')}>Submit for review</Button>}
      {can('review') && <Button type="primary" onClick={() => openAction('accept')}>Accept for tracking</Button>}
      {can('review') && <Button onClick={() => openAction('changes')}>Request corrections</Button>}
      {can('observe') && <Button onClick={() => openAction('observations')}>Add observation</Button>}
      {can('correct') && <Button onClick={() => openAction('correct')}>Officer correction</Button>}
      {can('renew') && <Button onClick={() => openAction('renew')}>Create renewal</Button>}
      {can('upload') && <Button onClick={() => openAction('documents')}>Upload document</Button>}
      {can('upload_release_documents') && <Button onClick={() => openAction('release documents')}>Upload release document</Button>}
      {can('request_release') && <Link to={`/releases/request?instrument=${item.id}&obligation=${item.obligation_id}&version=${item.version}`}><Button type="primary">Request release</Button></Link>}
      {item.release_case_id && <Link to={`/releases/${item.release_case_id}`}><Button>Open release case</Button></Link>}
    </>
  )

  return (
    <div className="stack">
      <Button className="back-link" type="link" onClick={onBack}>← All deposit records</Button>
      <PageHeader title={item.reference}
                  subtitle={<span className="cluster"><StatusTag value={item.status} /><VerificationTag value={item.verification_level} />
                    <span className="muted">{item.institution.name} · Version {item.version}</span></span>}
                  extra={actions} />
      {can('upload_release_documents') && !item.obligation_id && (
        <Alert type="warning" showIcon message="Release cannot be requested yet"
               description="This deposit is not linked to an obligation. Enter the Obligation ID when creating or correcting the record." />
      )}
      <Alert type="info" showIcon message="Acceptance is for tracking. Document review does not establish bank authenticity." />
      <Tabs activeKey={tab} onChange={setTab} items={[
        { key: 'details', label: 'Details', children: (
          <div className="two-col">
            <Panel title="Deposit">
              <SummaryList items={[
                { label: 'Institution', value: item.institution.name }, { label: 'Deposit type', value: item.mode },
                { label: 'Amount', value: tagged(formatInr(item.amount), 'amount') }, { label: 'Issue date', value: tagged(formatDate(item.issue_date), 'issue_date') },
                { label: 'Maturity date', value: tagged(formatDate(item.maturity_date), 'maturity_date') }, { label: 'Issuing bank', value: tagged(item.bank, 'bank') },
                { label: 'Reference', value: tagged(item.reference, 'reference') }]} />
            </Panel>
            <Panel title="Bank and holders">
              <SummaryList items={[
                { label: 'IFSC', value: tagged(item.ifsc, 'ifsc') }, { label: 'Branch', value: item.branch }, { label: 'Holder names', value: tagged(item.holder_names, 'holder_names') },
                { label: 'UTR', value: tagged(item.utr, 'utr') }, { label: 'Lien', value: tagged(item.lien_marked == null ? 'Not stated' : item.lien_marked ? 'Marked' : 'Not marked', 'lien_marked') },
                { label: 'Obligation', value: item.obligation_id ? `#${item.obligation_id}` : 'Not linked' }]} />
            </Panel>
            {item.field_provenance && (
              <p className="muted" style={{ gridColumn: '1 / -1', margin: 0 }}>
                <strong>Declared</strong>: entered by the institution. <strong>Document reviewed</strong>: an officer accepted the record for tracking.
                {' '}<strong>Confirmed</strong>: the value agrees with a bank statement line or bank response (simulated in this prototype, not bank authenticity).
                {' '}<strong>Mismatch</strong>: such a source shows a different value.
              </p>
            )}
          </div>) },
        { key: 'documents', label: `Documents (${docs.length})`, children: docs.length ? (
          <div className="stack">
            <Select aria-label="Supporting document" style={{ width: '100%', maxWidth: 480 }} value={selected}
                    options={docs.map((d) => ({ value: d.id, label: `${d.name} · ${humanize(d.kind)}` }))}
                    onChange={(value) => { setDoc(value); setPage(1) }} />
            {selected && <Panel><PdfViewer api={api} id={selected} page={page} onPage={setPage} /></Panel>}
            {selected && (
              <Collapse items={[{ key: 'extract', label: 'Read details from this document', children: (
                <AiExtraction key={selected} api={api} documentId={selected} canUse={can('edit')}
                              onUse={(values) => { setSuggestions(values); setAction('edit') }} />) }]} />
            )}
          </div>) : <Empty description="No documents uploaded yet." /> },
        { key: 'checks', label: 'Checks and observations', children: (
          <div className="stack">
            {item.findings?.length ? item.findings.map((f) => (
              <Alert key={f.code} showIcon type={f.severity === 'blocking' ? 'error' : 'warning'} message={findingLabel(f.code)} description={f.explanation} />
            )) : <Alert type="success" showIcon message="No automatic checks need attention." />}
            <Panel title="Officer observations" flush>
              <Table rowKey="id" size="middle" scroll={{ x: 640 }} pagination={false} dataSource={item.observations}
                     locale={{ emptyText: 'No observations recorded.' }} columns={[
                { title: 'Observation', dataIndex: 'comment' },
                { title: 'Severity', dataIndex: 'severity', width: 110, render: (v: string) => <Tag bordered={false} className={`tag tag--${v === 'BLOCKING' ? 'danger' : 'warning'}`}>{humanize(v)}</Tag> },
                { title: 'Evidence', width: 130, render: (_, o: NonNullable<RecordItem['observations']>[number]) => (
                  <Button type="link" onClick={() => { setDoc(o.document_id); setPage(o.page_number || 1); setTab('documents') }}>Page {o.page_number ?? '—'}</Button>) },
                { title: 'Resolution', render: (_, o: NonNullable<RecordItem['observations']>[number]) =>
                  o.resolved_at ? o.resolution : can('observe') ? <Button type="link" onClick={() => openAction(`observations/${o.id}/resolve`)}>Resolve</Button> : 'Awaiting officer' }]} />
            </Panel>
          </div>) },
        { key: 'verification', label: 'Verification', children: <VerificationTab api={api} id={id} version={item.version} canRequestBank={can('request_bank')} /> },
        { key: 'lineage', label: 'Renewal history', children: (
          <Panel>
            <SummaryList items={(['predecessor', 'successor'] as const).map((key) => ({
              label: key === 'predecessor' ? 'Renews' : 'Renewed by',
              value: item.lineage?.[key] ? <Button type="link" onClick={() => onOpen(item.lineage![key]!.id)}>{item.lineage[key]!.reference}</Button> : 'None',
            }))} />
            <p className="muted">The original deposit stays current until its renewal is accepted.</p>
          </Panel>) },
        { key: 'history', label: 'History', children: (
          <Panel><Timeline items={item.history?.map((e) => ({ key: e.id, children: (
            <><strong>{humanize(e.action)}</strong>{e.reason && <div>{e.reason}</div>}<small className="muted">{formatDateTime(e.at)}</small></>) }))} /></Panel>) },
      ]} />
      <Modal open={!!action} title={modalTitle} footer={null} destroyOnHidden width={formAction ? 720 : 520}
             onCancel={() => { setAction(''); setSuggestions(undefined); setFile(undefined) }}>
        {error && <Alert type="error" showIcon role="alert" message={error} style={{ marginBottom: 16 }}
                         action={<Button size="small" onClick={() => { changed(); void query.refetch() }}>Reload record</Button>} />}
        {formAction ? <RecordForm api={api} record={item} renewal={action === 'renew'} suggestions={action === 'edit' ? suggestions : undefined}
                                  onCancel={() => { setAction(''); setSuggestions(undefined) }} onSaved={(saved) => { changed(); onOpen(saved.id) }} />
          : <Form layout="vertical" onFinish={mutate}>
            {['accept', 'changes', 'correct'].includes(action) && <Form.Item name="reason" label="Reason" rules={[{ required: true }]}><Input.TextArea rows={3} maxLength={2000} /></Form.Item>}
            {action === 'correct' && <><Form.Item name="amount" label="Corrected amount (INR)"><Input inputMode="decimal" /></Form.Item><Form.Item name="bank" label="Corrected bank"><Input /></Form.Item></>}
            {action === 'observations' && <>
              <Alert type="info" showIcon style={{ marginBottom: 16 }} message={`Document ${selected ?? 'not selected'}, page ${page}`}
                     description="To point at other evidence, choose the document and page in the Documents tab first." />
              <Form.Item name="severity" label="Severity" rules={[{ required: true }]}><Select options={[{ value: 'WARNING', label: 'Warning' }, { value: 'BLOCKING', label: 'Blocking' }]} /></Form.Item>
              <Form.Item name="comment" label="Observation" rules={[{ required: true }]}><Input.TextArea rows={3} maxLength={2000} /></Form.Item></>}
            {action.endsWith('/resolve') && <Form.Item name="resolution" label="How was it resolved?" rules={[{ required: true }]}><Input.TextArea rows={3} maxLength={2000} /></Form.Item>}
            {(action === 'documents' || action === 'release documents') && <>
              {action === 'release documents' && <p className="muted">Release application documents are added to the accepted record. Its deposit details do not change.</p>}
              <Form.Item name="kind" label="Document category" rules={[{ required: true }]}><Select options={kindOptions(action === 'documents' ? DOCUMENT_KINDS : RELEASE_KINDS)} /></Form.Item>
              <Upload maxCount={1} beforeUpload={(f) => { setFile(f); return false }} onRemove={() => setFile(undefined)} accept=".pdf"><Button>Select PDF</Button></Upload></>}
            {action === 'submit' && <p>Submit this record and its supporting document for officer review?</p>}
            <Button type="primary" htmlType="submit" loading={busy} style={{ marginTop: 16 }}>Record action</Button>
          </Form>}
      </Modal>
    </div>
  )
}
