import { t as tr, useLanguage } from '@/i18n';
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
  useLanguage();
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
        {tr("Sign-ins, failed sign-ins, document downloads and exports, with the person, address and request ID. Rows cannot be edited or deleted.")}</Typography.Paragraph>
      <Form form={form} layout="vertical" className="filter-form"
            onFinish={(values) => {
              setFilters({ username: values.username?.trim(), action: values.action ?? [], object_type: values.object_type,
                           ip: values.ip?.trim(), ...rangeFilters(values.range) })
              setPage(1)
            }}>
        <Form.Item name="username" label={tr("Username")}><Input allowClear  /></Form.Item>
        <Form.Item name="action" label={tr("Action")}>
          <Select mode="multiple" allowClear style={{ minWidth: 220 }} options={(facets.data?.actions ?? []).map((value) => ({ value, label: value }))} />
        </Form.Item>
        <Form.Item name="object_type" label={tr("Object")}>
          <Select allowClear options={(facets.data?.object_types ?? []).map((value) => ({ value, label: value }))} />
        </Form.Item>
        <Form.Item name="ip" label="IP"><Input allowClear /></Form.Item>
        <Form.Item name="range" label={tr("Dates")}><DatePicker.RangePicker /></Form.Item>
        <Flex gap={8} className="filter-form__actions" wrap>
          <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>{tr("Filter")}</Button>
          <Button onClick={() => { form.resetFields(); setFilters({}); setPage(1) }}>{tr("Reset")}</Button>
          <Button icon={<DownloadOutlined />} loading={exporting} onClick={() => void exportCsv()}>{tr("Export CSV")}</Button>
        </Flex>
      </Form>
      {rows.isPending ? <LoadingState rows={6} />
        : rows.isError ? <QueryError error={rows.error} onRetry={() => void rows.refetch()} />
        : (
          <Table<AccessLogRow> rowKey="id" size="middle" dataSource={rows.data.results} loading={rows.isFetching}
                locale={{ emptyText: <EmptyState title={tr("No access events match these filters")} /> }}
                pagination={{ current: page, pageSize: 25, total: rows.data.count, showSizeChanger: false,
                              onChange: setPage, showTotal: (total) => tr("{0} events", {"0": (total)}) }}
                columns={[
                  { title: tr("Time"), dataIndex: 'created_at', width: 180, render: time },
                  { title: tr("User"), dataIndex: 'username', render: (name: string) => name || <em>{tr("anonymous")}</em> },
                  { title: tr("Action"), dataIndex: 'action', render: (action: string) => <Tag color={action === 'LOGIN_FAILED' ? 'red' : undefined}>{action}</Tag> },
                  { title: tr("Object"), render: (_, row) => row.object_type ? `${row.object_type} #${row.object_id ?? ''}` : '—' },
                  { title: tr("Detail"), dataIndex: 'detail', ellipsis: true },
                  { title: 'IP', dataIndex: 'ip_address', width: 130, render: (ip: string | null) => ip ?? '—' },
                  { title: tr("Request ID"), dataIndex: 'request_id', width: 150, ellipsis: true },
                ]} />
        )}
    </>
  )
}
