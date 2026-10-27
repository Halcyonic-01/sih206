import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Form, Input, Modal } from 'antd'
import { Panel, SummaryList } from '@/components/Panel'
import { formatDate } from '@/lib/format'
import type { Api, Retention } from './types'

type Kind = 'archive' | 'hold' | 'lift'
const TITLES: Record<Kind, string> = { archive: 'Archive this record', hold: 'Place a legal hold', lift: 'Lift the legal hold' }

/** Retention state of a settled record, with the authority's archive and legal-hold actions. */
export function RetentionPanel({ api, id, retention, actions }: { api: Api; id: number; retention: Retention; actions: Record<string, boolean> }) {
  const cache = useQueryClient()
  const [kind, setKind] = useState<Kind | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [form] = Form.useForm<{ reason: string }>()
  if (!retention.settled_on && !retention.legal_hold) return null

  async function submit(values: { reason: string }) {
    setBusy(true); setError('')
    try {
      const path = kind === 'archive' ? `/api/instruments/${id}/archive/` : `/api/instruments/${id}/legal-hold/`
      await api.request(path, { method: kind === 'lift' ? 'DELETE' : 'POST', body: values })
      setKind(null); form.resetFields()
      await cache.invalidateQueries({ queryKey: ['records'] })
    } catch (e) { setError(String(e)) } finally { setBusy(false) }
  }

  return (
    <Panel title="Retention">
      <SummaryList items={[
        { label: 'Settled on', value: retention.settled_on ? formatDate(retention.settled_on) : 'Not settled' },
        { label: 'Archival due', value: retention.archival_due_on ? `${formatDate(retention.archival_due_on)} (${retention.retention_years} years after settlement)` : 'Not applicable' },
        { label: 'Status', value: retention.archived ? 'Archived and frozen' : retention.archival_due ? 'Archival due' : 'Retained' },
        { label: 'Legal hold', value: retention.legal_hold ? `Yes: ${retention.hold_reason}` : 'No' }]} />
      {retention.archived && <Alert type="info" showIcon style={{ marginTop: 12 }} message="This record is frozen. No further changes can be made to it." />}
      <div className="cluster" style={{ marginTop: 12 }}>
        {actions.can_archive && <Button type="primary" onClick={() => setKind('archive')}>Archive</Button>}
        {actions.can_hold && <Button onClick={() => setKind('hold')}>Place legal hold</Button>}
        {actions.can_lift_hold && <Button onClick={() => setKind('lift')}>Lift legal hold</Button>}
      </div>
      <Modal open={kind !== null} title={kind ? TITLES[kind] : ''} okText="Record" confirmLoading={busy} onOk={() => form.submit()}
             onCancel={() => setKind(null)} destroyOnHidden>
        {error && <Alert type="error" showIcon role="alert" message={error} style={{ marginBottom: 12 }} />}
        <Form form={form} layout="vertical" onFinish={submit} requiredMark={false}>
          <Form.Item name="reason" label="Reason" rules={[{ required: true, min: 5, message: 'Give a reason of at least 5 characters.' }]}>
            <Input.TextArea rows={3} maxLength={500} showCount />
          </Form.Item>
        </Form>
      </Modal>
    </Panel>
  )
}
