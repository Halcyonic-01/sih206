import { t as tr, useLanguage } from '@/i18n';
import { DownloadOutlined, SearchOutlined } from '@ant-design/icons'
import { App as AntApp, Button, DatePicker, Drawer, Flex, Form, Input, Select, Table, Tag, Typography } from 'antd'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { download } from '@/api/client'
import { errorMessage } from '@/api/forms'
import { LoadingState, QueryError, EmptyState } from '@/components/states'
import { useAuditEvent, useAuditEvents, useAuditFacets, type AuditEventRow, type Filters } from './api'
import { rangeFilters, show, time } from './format'

interface FormValues {
  q?: string
  institution?: string
  actor?: number
  action?: string[]
  range?: [Dayjs | null, Dayjs | null]
}

function toFilters(values: FormValues): Filters {
  return {
    q: values.q?.trim(), institution: values.institution, actor: values.actor,
    action: values.action ?? [], ...rangeFilters(values.range),
  }
}

function EventDrawer({ id, onClose }: { id: number | null; onClose: () => void }) {
  useLanguage();
  const event = useAuditEvent(id)
  return (
    <Drawer open={id !== null} onClose={onClose} width={640} title={event.data ? `${event.data.action} · ${event.data.instrument.reference}` : tr("Audit event")}>
      {event.isPending ? <LoadingState />
        : event.isError ? <QueryError error={event.error} onRetry={() => void event.refetch()} />
        : (
          <>
            <Typography.Paragraph>
              {time(event.data.created_at)} · {event.data.actor.username} ·{' '}
              <Link to={`/records/${event.data.instrument.id}`}>{event.data.instrument.institution} / {event.data.instrument.reference}</Link>
            </Typography.Paragraph>
            {event.data.reason && <Typography.Paragraph><strong>{tr("Reason:")}</strong> {event.data.reason}</Typography.Paragraph>}
            <Typography.Title level={5}>{tr("What changed")}</Typography.Title>
            <Table size="small" pagination={false} rowKey="field" dataSource={event.data.changes}
                   locale={{ emptyText: tr("No field changed (the event records an action only).") }}
                   columns={[
                     { title: tr("Field"), dataIndex: 'field', width: 160 },
                     { title: tr("Before"), dataIndex: 'before', render: (value) => <code>{show(value)}</code> },
                     { title: tr("After"), dataIndex: 'after', render: (value) => <code>{show(value)}</code> },
                   ]} />
            {event.data.seal && (
              <Typography.Paragraph type="secondary" style={{ marginTop: 16, wordBreak: 'break-all' }}>
                {tr("Seal ")}<code>{event.data.seal.hash.slice(0, 24)}…</code> {tr("  chained to  ")}<code>{event.data.seal.prev_hash ? `${event.data.seal.prev_hash.slice(0, 24)}…` : tr("start of chain")}</code>
                {event.data.seal.backfilled && <Tag style={{ marginInlineStart: 8 }}>{tr("sealed late")}</Tag>}
              </Typography.Paragraph>
            )}
            <Typography.Title level={5} style={{ marginTop: 16 }}>{tr("Full snapshot after the event")}</Typography.Title>
            <pre style={{ maxHeight: 320, overflow: 'auto', background: '#f3f5f9', padding: 12, borderRadius: 8 }}>
              {JSON.stringify(event.data.after, null, 2)}
            </pre>
          </>
        )}
    </Drawer>
  )
}

export default function AuditTrailTab() {
  useLanguage();
  const { message } = AntApp.useApp()
  const [form] = Form.useForm<FormValues>()
  const [filters, setFilters] = useState<Filters>({})
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<number | null>(null)
  const [exporting, setExporting] = useState(false)
  const events = useAuditEvents(filters, page)
  const facets = useAuditFacets()

  async function exportCsv() {
    setExporting(true)
    try {
      await download('/audit/events/export/', filters, 'audit-trail.csv')
    } catch (error) {
      message.error(errorMessage(error))
    } finally {
      setExporting(false)
    }
  }

  return (
    <>
      <Form form={form} layout="vertical" className="filter-form"
            onFinish={(values) => { setFilters(toFilters(values)); setPage(1) }}>
        <Form.Item name="q" label={tr("Reference")}><Input allowClear  /></Form.Item>
        <Form.Item name="institution" label={tr("Institution")}>
          <Select allowClear loading={facets.isPending} options={(facets.data?.institutions ?? []).map((value) => ({ value, label: value }))} />
        </Form.Item>
        <Form.Item name="actor" label={tr("Actor")}>
          <Select allowClear showSearch optionFilterProp="label"
                  options={(facets.data?.actors ?? []).map((actor) => ({ value: actor.id, label: actor.username }))} />
        </Form.Item>
        <Form.Item name="action" label={tr("Action")}>
          <Select mode="multiple" allowClear options={(facets.data?.actions ?? []).map((value) => ({ value, label: value }))} />
        </Form.Item>
        <Form.Item name="range" label={tr("Dates")}><DatePicker.RangePicker /></Form.Item>
        <Flex gap={8} className="filter-form__actions" wrap>
          <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>{tr("Filter")}</Button>
          <Button onClick={() => { form.resetFields(); setFilters({}); setPage(1) }}>{tr("Reset")}</Button>
          <Button icon={<DownloadOutlined />} loading={exporting} onClick={() => void exportCsv()}>{tr("Export CSV")}</Button>
        </Flex>
      </Form>
      {events.isPending ? <LoadingState rows={6} />
        : events.isError ? <QueryError error={events.error} onRetry={() => void events.refetch()} />
        : (
          <Table<AuditEventRow> rowKey="id" size="middle" dataSource={events.data.results} loading={events.isFetching}
                locale={{ emptyText: <EmptyState title={tr("No events match these filters")} /> }}
                pagination={{ current: page, pageSize: 25, total: events.data.count, showSizeChanger: false,
                              onChange: setPage, showTotal: (total) => tr("{0} events", {"0": (total)}) }}
                columns={[
                  { title: tr("Time"), dataIndex: 'created_at', width: 180, render: time },
                  { title: tr("Record"), render: (_, row) => <Link to={`/records/${row.instrument.id}`}>{row.instrument.institution} / {row.instrument.reference}</Link> },
                  { title: tr("Actor"), dataIndex: ['actor', 'username'] },
                  { title: tr("Action"), dataIndex: 'action', render: (action: string) => <Tag>{action}</Tag> },
                  { title: tr("Reason"), dataIndex: 'reason', ellipsis: true },
                  { title: '', width: 90, render: (_, row) => <Button type="link" onClick={() => setSelected(row.id)}>{tr("Details")}</Button> },
                ]} />
        )}
      <EventDrawer id={selected} onClose={() => setSelected(null)} />
    </>
  )
}
