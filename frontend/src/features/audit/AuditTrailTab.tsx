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
  const event = useAuditEvent(id)
  return (
    <Drawer open={id !== null} onClose={onClose} width={640} title={event.data ? `${event.data.action} · ${event.data.instrument.reference}` : 'Audit event'}>
      {event.isPending ? <LoadingState />
        : event.isError ? <QueryError error={event.error} onRetry={() => void event.refetch()} />
        : (
          <>
            <Typography.Paragraph>
              {time(event.data.created_at)} · {event.data.actor.username} ·{' '}
              <Link to={`/records/${event.data.instrument.id}`}>{event.data.instrument.institution} / {event.data.instrument.reference}</Link>
            </Typography.Paragraph>
            {event.data.reason && <Typography.Paragraph><strong>Reason:</strong> {event.data.reason}</Typography.Paragraph>}
            <Typography.Title level={5}>What changed</Typography.Title>
            <Table size="small" pagination={false} rowKey="field" dataSource={event.data.changes}
                   locale={{ emptyText: 'No field changed (the event records an action only).' }}
                   columns={[
                     { title: 'Field', dataIndex: 'field', width: 160 },
                     { title: 'Before', dataIndex: 'before', render: (value) => <code>{show(value)}</code> },
                     { title: 'After', dataIndex: 'after', render: (value) => <code>{show(value)}</code> },
                   ]} />
            <Typography.Title level={5} style={{ marginTop: 16 }}>Full snapshot after the event</Typography.Title>
            <pre style={{ maxHeight: 320, overflow: 'auto', background: '#f4f6fa', padding: 12 }}>
              {JSON.stringify(event.data.after, null, 2)}
            </pre>
          </>
        )}
    </Drawer>
  )
}

export default function AuditTrailTab() {
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
      <Form form={form} layout="inline" style={{ rowGap: 12, marginBottom: 16 }}
            onFinish={(values) => { setFilters(toFilters(values)); setPage(1) }}>
        <Form.Item name="q" label="Reference"><Input allowClear placeholder="Contains…" /></Form.Item>
        <Form.Item name="institution" label="Institution">
          <Select allowClear style={{ width: 140 }} loading={facets.isPending} options={(facets.data?.institutions ?? []).map((value) => ({ value, label: value }))} />
        </Form.Item>
        <Form.Item name="actor" label="Actor">
          <Select allowClear showSearch optionFilterProp="label" style={{ width: 170 }}
                  options={(facets.data?.actors ?? []).map((actor) => ({ value: actor.id, label: actor.username }))} />
        </Form.Item>
        <Form.Item name="action" label="Action">
          <Select mode="multiple" allowClear style={{ minWidth: 200 }} options={(facets.data?.actions ?? []).map((value) => ({ value, label: value }))} />
        </Form.Item>
        <Form.Item name="range" label="Dates"><DatePicker.RangePicker /></Form.Item>
        <Flex gap={8}>
          <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>Filter</Button>
          <Button onClick={() => { form.resetFields(); setFilters({}); setPage(1) }}>Reset</Button>
          <Button icon={<DownloadOutlined />} loading={exporting} onClick={() => void exportCsv()}>Export CSV</Button>
        </Flex>
      </Form>
      {events.isPending ? <LoadingState rows={6} />
        : events.isError ? <QueryError error={events.error} onRetry={() => void events.refetch()} />
        : (
          <Table<AuditEventRow> rowKey="id" size="middle" dataSource={events.data.results} loading={events.isFetching}
                locale={{ emptyText: <EmptyState title="No events match these filters" /> }}
                pagination={{ current: page, pageSize: 25, total: events.data.count, showSizeChanger: false,
                              onChange: setPage, showTotal: (total) => `${total} events` }}
                columns={[
                  { title: 'Time', dataIndex: 'created_at', width: 180, render: time },
                  { title: 'Record', render: (_, row) => <Link to={`/records/${row.instrument.id}`}>{row.instrument.institution} / {row.instrument.reference}</Link> },
                  { title: 'Actor', dataIndex: ['actor', 'username'] },
                  { title: 'Action', dataIndex: 'action', render: (action: string) => <Tag>{action}</Tag> },
                  { title: 'Reason', dataIndex: 'reason', ellipsis: true },
                  { title: '', width: 90, render: (_, row) => <Button type="link" onClick={() => setSelected(row.id)}>Details</Button> },
                ]} />
        )}
      <EventDrawer id={selected} onClose={() => setSelected(null)} />
    </>
  )
}
