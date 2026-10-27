import { t as tr, useLanguage } from '@/i18n';
import { LanguageToggle } from '@/i18n/LanguageToggle';
import { useEffect, useRef, useState, type ReactNode } from 'react'
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
import { RENEWAL_REASONS } from './renewal'
import { RetentionPanel } from './RetentionPanel'
import { VerificationTab } from './Verification'
import type { Api, RecordItem } from './types'

const DOCUMENT_KINDS = ['FDR', 'PAYMENT_PROOF', 'RPGF_PROOF', 'AFFIDAVIT_3', 'AFFIDAVIT_6', 'APPROVAL_LETTER', 'BANK_CERTIFICATE', 'REQUEST_LETTER', 'STUDENT_CLEARANCE', 'EXTERNAL_NOC']
const RELEASE_KINDS = ['REQUEST_LETTER', 'AFFIDAVIT_6', 'APPROVAL_LETTER', 'STUDENT_CLEARANCE', 'EXTERNAL_NOC']
const kindOptions = (kinds: string[]) => kinds.map((value) => ({ value, label: humanize(value) }))

const SCAN_NOTE: Record<string, string> = { PENDING: ' · not scanned for malware', CLEAN: '', REJECTED: ' · quarantined (malware found)' }

const MODAL_TITLES: Record<string, string> = {
  edit: 'Edit draft', renew: 'Create renewal', submit: 'Submit for review', accept: 'Accept for tracking',
  changes: 'Request corrections', correct: 'Officer correction', observations: 'Add observation',
  documents: 'Upload document', 'release documents': 'Upload release document',
}

export function RecordDetail({ api, id, onBack, onOpen, readinessAction, readinessKind }: { api: Api; id: number; onBack: () => void; onOpen: (id: number) => void; readinessAction?: string; readinessKind?: string }) {
  useLanguage();
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
  const [documentKind, setDocumentKind] = useState<string>()
  const handledReadiness = useRef(false)
  useEffect(() => {
    const current = query.data
    if (!current || handledReadiness.current) return
    handledReadiness.current = true
    if (readinessAction === 'verification') setTab('verification')
    if (readinessAction === 'submit' && current.actions?.can_submit) setAction('submit')
    if (readinessAction === 'upload' && current.actions?.can_upload &&
      ['AFFIDAVIT_3', 'PAYMENT_PROOF'].includes(readinessKind || '')) {
      setDocumentKind(readinessKind); setAction('documents')
    }
  }, [query.data, readinessAction, readinessKind])
  if (query.isPending) return <><PageHeader title={tr("Deposit record")} /><LoadingState rows={6} /></>
  if (query.error) {
    return <><Button className="back-link" type="link" onClick={onBack}>{tr("← All deposit records")}</Button><PageHeader title={tr("Deposit record")} />
      <Alert type="error" showIcon message={tr("This record could not be loaded")} description={String(query.error)}
             action={<Button onClick={() => void query.refetch()}>{tr("Try again")}</Button>} /></>
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
      {can('edit') && <Button onClick={() => openAction('edit')}>{tr("Edit draft")}</Button>}
      {can('submit') && <Button type="primary" onClick={() => openAction('submit')}>{tr("Submit for review")}</Button>}
      {can('review') && <Button type="primary" onClick={() => openAction('accept')}>{tr("Accept for tracking")}</Button>}
      {can('review') && <Button onClick={() => openAction('changes')}>{tr("Request corrections")}</Button>}
      {can('observe') && <Button onClick={() => openAction('observations')}>{tr("Add observation")}</Button>}
      {can('correct') && <Button onClick={() => openAction('correct')}>{tr("Officer correction")}</Button>}
      {can('renew') && <Button onClick={() => openAction('renew')}>{tr("Create renewal")}</Button>}
      {can('upload') && <Button onClick={() => openAction('documents')}>{tr("Upload document")}</Button>}
      {can('upload_release_documents') && <Button onClick={() => openAction('release documents')}>{tr("Upload release document")}</Button>}
      {can('request_release') && <Link to={`/releases/request?instrument=${item.id}&obligation=${item.obligation_id}&version=${item.version}`}><Button type="primary">{tr("Request release")}</Button></Link>}
      {item.release_case_id && <Link to={`/releases/${item.release_case_id}`}><Button>{tr("Open release case")}</Button></Link>}
    </>
  )

  return (
    <div className="stack">
      <Button className="back-link" type="link" onClick={onBack}>{tr("← All deposit records")}</Button>
      <PageHeader title={item.reference}
                  subtitle={<span className="cluster"><StatusTag value={item.status} /><VerificationTag value={item.verification_level} />
                    <span className="muted">{item.institution.name} {tr("  · Version  ")}{item.version}</span></span>}
                  extra={actions} />
      {can('upload_release_documents') && !item.obligation_id && (
        <Alert type="warning" showIcon message={tr("Release cannot be requested yet")}
               description={tr("This deposit is not linked to an obligation. Enter the Obligation ID when creating or correcting the record.")} />
      )}
      <Alert type="info" showIcon message={tr("Acceptance is for tracking. Document review does not establish bank authenticity.")} />
      <Tabs activeKey={tab} onChange={setTab} items={[
        { key: 'details', label: tr("Details"), children: (
          <div className="two-col">
            <Panel title={tr("Deposit")}>
              <SummaryList items={[
                { label: tr('Institution'), value: item.institution.name }, { label: tr('Deposit type'), value: item.mode },
                { label: tr('Amount'), value: tagged(formatInr(item.amount), 'amount') }, { label: tr('Issue date'), value: tagged(formatDate(item.issue_date), 'issue_date') },
                { label: tr('Maturity date'), value: tagged(formatDate(item.maturity_date), 'maturity_date') }, { label: tr('Issuing bank'), value: tagged(item.bank, 'bank') },
                { label: tr('Reference'), value: tagged(item.reference, 'reference') }]} />
            </Panel>
            <Panel title={tr("Bank and holders")}>
              <SummaryList items={[
                { label: 'IFSC', value: tagged(item.ifsc, 'ifsc') }, { label: tr('Branch'), value: item.branch }, { label: tr('Holder names'), value: tagged(item.holder_names, 'holder_names') },
                { label: 'UTR', value: tagged(item.utr, 'utr') }, { label: tr('Lien'), value: tagged(item.lien_marked == null ? tr('Not stated') : item.lien_marked ? tr('Marked') : tr('Not marked'), 'lien_marked') },
                { label: tr('Obligation'), value: item.obligation_id ? `#${item.obligation_id}` : tr('Not linked') }]} />
            </Panel>
            {item.retention && <div style={{ gridColumn: '1 / -1' }}><RetentionPanel api={api} id={item.id} retention={item.retention} actions={item.actions ?? {}} /></div>}
            {item.field_provenance && (
              <p className="muted" style={{ gridColumn: '1 / -1', margin: 0 }}>
                <strong>{tr('Declared')}</strong>: {tr('Entered by the institution.')} <strong>{tr('Document reviewed')}</strong>: {tr('An officer accepted the record for tracking.')}
                {' '}<strong>{tr('Confirmed')}</strong>: {tr('The value agrees with a bank statement line or bank response (simulated in this prototype, not bank authenticity).')}
                {' '}<strong>{tr('Mismatch')}</strong>: {tr('Such a source shows a different value.')}
              </p>
            )}
          </div>) },
        { key: 'documents', label: tr("Documents ({0})", {"0": (docs.length)}), children: docs.length ? (
          <div className="stack">
            <Select aria-label={tr("Supporting document")} style={{ width: '100%', maxWidth: 480 }} value={selected}
                    options={docs.map((d) => ({ value: d.id, label: `${d.name} · ${humanize(d.kind)}${SCAN_NOTE[d.scan_status ?? 'CLEAN']}` }))}
                    onChange={(value) => { setDoc(value); setPage(1) }} />
            {docs.find((d) => d.id === selected)?.scan_status === 'REJECTED' && (
              <Alert type="error" showIcon message="This document was quarantined by the malware scan and cannot be opened." />
            )}
            {selected && <Panel><PdfViewer api={api} id={selected} page={page} onPage={setPage} /></Panel>}
            {selected && (
              <Collapse items={[{ key: 'extract', label: tr("Read details from this document"), children: (
                <AiExtraction key={selected} api={api} documentId={selected} canUse={can('edit')}
                              onUse={(values) => { setSuggestions(values); setAction('edit') }} />) }]} />
            )}
          </div>) : <Empty description={tr("No documents uploaded yet.")} /> },
        { key: 'checks', label: tr("Checks and observations"), children: (
          <div className="stack">
            {item.findings?.length ? item.findings.map((f) => (
              <Alert key={f.code} showIcon type={f.severity === 'blocking' ? 'error' : 'warning'} message={findingLabel(f.code)} description={f.explanation} />
            )) : <Alert type="success" showIcon message={tr("No automatic checks need attention.")} />}
            <Panel title={tr("Officer observations")} flush>
              <Table rowKey="id" size="middle" scroll={{ x: 640 }} pagination={false} dataSource={item.observations}
                     locale={{ emptyText: tr("No observations recorded.") }} columns={[
                { title: tr("Observation"), dataIndex: 'comment' },
                { title: tr("Severity"), dataIndex: 'severity', width: 110, render: (v: string) => <Tag bordered={false} className={`tag tag--${v === 'BLOCKING' ? 'danger' : 'warning'}`}>{humanize(v)}</Tag> },
                { title: tr("Evidence"), width: 130, render: (_, o: NonNullable<RecordItem['observations']>[number]) => (
                  <Button type="link" onClick={() => { setDoc(o.document_id); setPage(o.page_number || 1); setTab('documents') }}>{tr("Page  ")}{o.page_number ?? '—'}</Button>) },
                { title: tr("Resolution"), render: (_, o: NonNullable<RecordItem['observations']>[number]) =>
                  o.resolved_at ? o.resolution : can('observe') ? <Button type="link" onClick={() => openAction(`observations/${o.id}/resolve`)}>{tr("Resolve")}</Button> : 'Awaiting officer' }]} />
            </Panel>
          </div>) },
        { key: 'verification', label: tr("Verification"), children: <VerificationTab api={api} id={id} version={item.version} canRequestBank={can('request_bank')} /> },
        { key: 'lineage', label: tr("Renewal history"), children: (
          <Panel>
            <SummaryList items={(['predecessor', 'successor'] as const).map((key) => ({
              label: key === 'predecessor' ? 'Renews' : 'Renewed by',
              value: item.lineage?.[key] ? <Button type="link" onClick={() => onOpen(item.lineage![key]!.id)}>{item.lineage[key]!.reference}</Button> : 'None',
            }))} />
            {item.lineage?.link && (
              <p><strong>Why it was renewed:</strong> {RENEWAL_REASONS[item.lineage.link.reason] ?? 'Not recorded'}
                {item.lineage.link.note && ` — ${item.lineage.link.note}`}</p>
            )}
            <p className="muted">{tr("The original deposit stays current until its renewal is accepted.")}</p>
          </Panel>) },
        { key: 'history', label: tr("History"), children: (
          <Panel><Timeline items={item.history?.map((e) => ({ key: e.id, children: (
            <><strong>{humanize(e.action)}</strong>{e.reason && <div>{e.reason}</div>}<small className="muted">{formatDateTime(e.at)}</small></>) }))} /></Panel>) },
      ]} />
      <Modal open={!!action} title={<div className="localized-modal-title"><span>{tr(modalTitle)}</span><LanguageToggle /></div>} footer={null} destroyOnHidden width={formAction ? 720 : 520}
             onCancel={() => { setAction(''); setSuggestions(undefined); setFile(undefined) }}>
        {error && <Alert type="error" showIcon role="alert" message={error} style={{ marginBottom: 16 }}
                         action={<Button size="small" onClick={() => { changed(); void query.refetch() }}>{tr("Reload record")}</Button>} />}
        {formAction ? <RecordForm api={api} record={item} renewal={action === 'renew'} suggestions={action === 'edit' ? suggestions : undefined}
                                  onCancel={() => { setAction(''); setSuggestions(undefined) }} onSaved={(saved) => { changed(); onOpen(saved.id) }} />
          : <Form key={`${action}:${documentKind || ''}`} layout="vertical" initialValues={{kind: documentKind}} onFinish={mutate}>
            {['accept', 'changes', 'correct'].includes(action) && <Form.Item name="reason" label={tr("Reason")} rules={[{ required: true }]}><Input.TextArea rows={3} maxLength={2000} /></Form.Item>}
            {action === 'correct' && <><Form.Item name="amount" label={tr("Corrected amount (INR)")}><Input inputMode="decimal" /></Form.Item><Form.Item name="bank" label={tr("Corrected bank")}><Input /></Form.Item></>}
            {action === 'observations' && <>
              <Alert type="info" showIcon style={{ marginBottom: 16 }} message={tr("Document {0}, page {1}", {"0": (selected ?? 'not selected'), "1": (page)})}
                     description={tr("To point at other evidence, choose the document and page in the Documents tab first.")} />
              <Form.Item name="severity" label={tr("Severity")} rules={[{ required: true }]}><Select options={[{ value: 'WARNING', label: tr("Warning") }, { value: 'BLOCKING', label: tr("Blocking") }]} /></Form.Item>
              <Form.Item name="comment" label={tr("Observation")} rules={[{ required: true }]}><Input.TextArea rows={3} maxLength={2000} /></Form.Item></>}
            {action.endsWith('/resolve') && <Form.Item name="resolution" label={tr("How was it resolved?")} rules={[{ required: true }]}><Input.TextArea rows={3} maxLength={2000} /></Form.Item>}
            {(action === 'documents' || action === 'release documents') && <>
              {action === 'release documents' && <p className="muted">{tr("Release application documents are added to the accepted record. Its deposit details do not change.")}</p>}
              <Form.Item name="kind" label={tr("Document category")} rules={[{ required: true }]}><Select options={kindOptions(action === 'documents' ? DOCUMENT_KINDS : RELEASE_KINDS)} /></Form.Item>
              <Upload maxCount={1} beforeUpload={(f) => { setFile(f); return false }} onRemove={() => setFile(undefined)} accept=".pdf"><Button>{tr("Select PDF")}</Button></Upload></>}
            {action === 'submit' && <p>{tr("Submit this record and its supporting document for officer review?")}</p>}
            <Button type="primary" htmlType="submit" loading={busy} style={{ marginTop: 16 }}>{tr("Record action")}</Button>
          </Form>}
      </Modal>
    </div>
  )
}
