import { DownloadOutlined, SearchOutlined } from '@ant-design/icons'
import { App as AntApp, Button, DatePicker, Flex, Form, Input, Select, Table, Tag, Typography } from 'antd'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'
import { download } from '@/api/client'
import { errorMessage } from '@/api/forms'
import { EmptyState, LoadingState, QueryError } from '@/components/states'
import { useAccessFacets, useAccessLog, type AccessLogRow, type Filters } from './api'
import { rangeFilters, time } from './format'

interface FormValues {
  username?: string
  action?: string[]
  object_type?: string
  ip?: string
  range?: [Dayjs | null, Dayjs | null]
}

export default function AccessLogTab() {
  const { message } = AntApp.useApp()
  const [form] = Form.useForm<FormValues>()
  const [filters, setFilters] = useState<Filters>({})
  const [page, setPage] = useState(1)
  const [exporting, setExporting] = useState(false)
  const rows = useAccessLog(filters, page)
  const facets = useAccessFacets()

  async function exportCsv() {
    setExporting(true)
    try {
      await download('/audit/access-log/export/', filters, 'access-log.csv')
    } catch (error) {
      message.error(errorMessage(error))
    } finally {
      setExporting(false)
    }
  }

  return (
    <>
      <Typography.Paragraph type="secondary">
        Sign-ins, failed sign-ins, document downloads and exports, with the person, address and request ID.
        Rows cannot be edited or deleted.
      </Typography.Paragraph>
      <Form form={form} layout="inline" style={{ rowGap: 12, marginBottom: 16 }}
            onFinish={(values) => {
              setFilters({ username: values.username?.trim(), action: values.action ?? [], object_type: values.object_type,
                           ip: values.ip?.trim(), ...rangeFilters(values.range) })
              setPage(1)
            }}>
        <Form.Item name="username" label="Username"><Input allowClear placeholder="Contains…" /></Form.Item>
        <Form.Item name="action" label="Action">
          <Select mode="multiple" allowClear style={{ minWidth: 220 }} options={(facets.data?.actions ?? []).map((value) => ({ value, label: value }))} />
        </Form.Item>
        <Form.Item name="object_type" label="Object">
          <Select allowClear style={{ width: 170 }} options={(facets.data?.object_types ?? []).map((value) => ({ value, label: value }))} />
        </Form.Item>
        <Form.Item name="ip" label="IP"><Input allowClear style={{ width: 140 }} /></Form.Item>
        <Form.Item name="range" label="Dates"><DatePicker.RangePicker /></Form.Item>
        <Flex gap={8}>
          <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>Filter</Button>
          <Button onClick={() => { form.resetFields(); setFilters({}); setPage(1) }}>Reset</Button>
          <Button icon={<DownloadOutlined />} loading={exporting} onClick={() => void exportCsv()}>Export CSV</Button>
        </Flex>
      </Form>
      {rows.isPending ? <LoadingState rows={6} />
        : rows.isError ? <QueryError error={rows.error} onRetry={() => void rows.refetch()} />
        : (
          <Table<AccessLogRow> rowKey="id" size="middle" dataSource={rows.data.results} loading={rows.isFetching}
                locale={{ emptyText: <EmptyState title="No access events match these filters" /> }}
                pagination={{ current: page, pageSize: 25, total: rows.data.count, showSizeChanger: false,
                              onChange: setPage, showTotal: (total) => `${total} events` }}
                columns={[
                  { title: 'Time', dataIndex: 'created_at', width: 180, render: time },
                  { title: 'User', dataIndex: 'username', render: (name: string) => name || <em>anonymous</em> },
                  { title: 'Action', dataIndex: 'action', render: (action: string) => <Tag color={action === 'LOGIN_FAILED' ? 'red' : undefined}>{action}</Tag> },
                  { title: 'Object', render: (_, row) => row.object_type ? `${row.object_type} #${row.object_id ?? ''}` : '—' },
                  { title: 'Detail', dataIndex: 'detail', ellipsis: true },
                  { title: 'IP', dataIndex: 'ip_address', width: 130, render: (ip: string | null) => ip ?? '—' },
                  { title: 'Request ID', dataIndex: 'request_id', width: 150, ellipsis: true },
                ]} />
        )}
    </>
  )
}
