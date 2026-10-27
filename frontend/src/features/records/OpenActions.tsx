import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Form, Input, Modal, Table, Tag } from 'antd'
import { Panel } from '@/components/Panel'
import { humanize } from '@/lib/labels'
import type { Api, OpenAlert } from './types'

const WHO: Record<string, string> = { OPEN: 'Nobody has taken charge', ACKNOWLEDGED: 'Taken charge by' }

/** Actions raised by the daily rules. They clear by themselves when the condition ends; a person can take charge with a note,
 * and one nobody acknowledges is escalated. */
export function OpenActions({ api, alerts, onOpen }: { api: Api; alerts: OpenAlert[]; onOpen: (id: number) => void }) {
  const cache = useQueryClient()
  const [target, setTarget] = useState<OpenAlert | null>(null)
  const [form] = Form.useForm<{ note: string }>()
  const acknowledge = useMutation({
    mutationFn: (values: { note: string }) => api.request(`/api/alerts/${target!.id}/acknowledge/`, { method: 'POST', body: values }),
    onSuccess: () => { setTarget(null); form.resetFields(); void cache.invalidateQueries({ queryKey: ['records', 'dashboard'] }) },
  })
  return (
    <Panel title="Open actions" flush>
      <Table rowKey="id" size="middle" scroll={{ x: 640 }} pagination={{ pageSize: 8, hideOnSinglePage: true, showSizeChanger: false }}
             dataSource={alerts} locale={{ emptyText: 'No open actions. They close by themselves when the condition ends.' }} columns={[
        { title: 'Record', dataIndex: 'reference', render: (value: string, row: OpenAlert) =>
          row.instrument_id ? <Button type="link" onClick={() => onOpen(row.instrument_id!)}>{value}</Button> : value },
        { title: 'What', dataIndex: 'rule', render: (rule: string, row: OpenAlert) => (
          <span>{humanize(rule)}{row.escalation_level > 0 && <Tag color="red" style={{ marginInlineStart: 8 }}>Escalated</Tag>}</span>) },
        { title: 'Open since', dataIndex: 'opened_on' },
        { title: 'Who', render: (_: unknown, row: OpenAlert) => (
          <span>{WHO[row.status] ?? row.status}{row.acknowledged_by ? ` ${row.acknowledged_by}` : ''}
            {row.note && <div className="muted">{row.note}</div>}</span>) },
        { title: '', render: (_: unknown, row: OpenAlert) => row.can_acknowledge
          ? <Button size="small" onClick={() => setTarget(row)}>Take charge</Button> : null }]} />
      <Modal open={target !== null} title="Take charge of this action" okText="Acknowledge" confirmLoading={acknowledge.isPending}
             onOk={() => form.submit()} onCancel={() => setTarget(null)} destroyOnHidden>
        <p>{target?.reference}: {target?.summary}</p>
        {acknowledge.error && <Alert type="error" showIcon role="alert" message={String(acknowledge.error.message ?? acknowledge.error)} style={{ marginBottom: 12 }} />}
        <Form form={form} layout="vertical" onFinish={(values) => acknowledge.mutate(values)} requiredMark={false}>
          <Form.Item name="note" label="What are you doing about it?" rules={[{ required: true, message: 'Write a short note.' }]}>
            <Input.TextArea rows={3} maxLength={1000} showCount />
          </Form.Item>
        </Form>
      </Modal>
    </Panel>
  )
}
