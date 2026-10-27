import { t as tr, useLanguage } from '@/i18n';
import { LanguageToggle } from '@/i18n/LanguageToggle';
import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { DownloadOutlined, PlusOutlined } from '@ant-design/icons'
import { Alert, Button, Collapse, Empty, Grid, Input, Modal, Pagination, Select, Table, Tag } from 'antd'
import { PageHeader } from '@/components/PageHeader'
import { FilterBar, Panel } from '@/components/Panel'
import { StatusTag, VerificationTag } from '@/components/StatusTag'
import { formatDate, formatInr } from '@/lib/format'
import { CATEGORY_LABELS } from '@/lib/labels'
import { RecordDetail } from './RecordDetail'
import { RecordForm } from './RecordForm'
import type { Api, Page, RecordItem, Role } from './types'

export { DashboardPage } from './Dashboard'

const PAGE_SIZE = 20

function RecordCards({ rows, onOpen }: { rows: RecordItem[]; onOpen: (id: number) => void }) {
  useLanguage();
  return (
    <ul className="record-list">
      {rows.map((row) => (
        <li key={row.id} className="record-card">
          <div className="record-card__top">
            <button type="button" className="record-card__ref" onClick={() => onOpen(row.id)}>{row.reference}</button>
            <StatusTag value={row.status} />
          </div>
          <dl className="record-card__meta">
            <div><dt>{tr("Institution")}</dt><dd>{row.institution.name}</dd></div>
            <div><dt>{tr("Amount")}</dt><dd>{formatInr(row.amount)}</dd></div>
            <div><dt>{tr("Type")}</dt><dd>{row.mode}</dd></div>
            <div><dt>{tr("Maturity")}</dt><dd>{formatDate(row.maturity_date)}</dd></div>
            <div><dt>{tr("Verification")}</dt><dd><VerificationTag value={row.verification_level} /></dd></div>
          </dl>
        </li>
      ))}
    </ul>
  )
}

export function RecordsWorkspace({ api, role, globalQuery, initialRecordId, initialCategory }: {
  api: Api; role: Role; globalQuery?: string; initialRecordId?: number; initialCategory?: string
}) {
  useLanguage();
  const screens = Grid.useBreakpoint()
  const wide = screens.md === true
  const [selected, setSelected] = useState<number | undefined>(initialRecordId)
  const [create, setCreate] = useState(false)
  const [q, setQ] = useState('')
  const [category, setCategory] = useState(initialCategory || 'all')
  const [mode, setMode] = useState('')
  const [page, setPage] = useState(1)
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  useEffect(() => { setCategory(initialCategory || 'all'); setPage(1) }, [initialCategory])
  useEffect(() => {
    if (globalQuery !== undefined) { setQ(globalQuery); setPage(1); if (!initialRecordId) setSelected(undefined) }
  }, [globalQuery, initialRecordId])
  const cache = useQueryClient()
  const params = new URLSearchParams({ q, category, page: String(page), page_size: String(PAGE_SIZE) })
  if (mode) params.set('mode', mode)
  if (from) params.set('maturity_from', from)
  if (to) params.set('maturity_to', to)
  const query = useQuery({ queryKey: ['records', 'list', params.toString()], queryFn: () => api.request<Page>(`/api/instruments/?${params}`) })
  if (selected) return <RecordDetail key={selected} api={api} id={selected} onOpen={setSelected} onBack={() => setSelected(undefined)} />

  const rows = query.data?.results ?? []
  const total = query.data?.count ?? 0
  const filtered = Boolean(q || mode || from || to || category !== 'all')
  const reset = () => { setQ(''); setMode(''); setFrom(''); setTo(''); setCategory('all'); setPage(1) }

  const filterBar = (
    <FilterBar actions={filtered && <Button onClick={reset}>{tr("Clear filters")}</Button>}>
        <div>
          <span className="field-label" id="rec-category">{tr("Category")}</span>
          <Select aria-label={tr("Record category")} value={category} onChange={(value) => { setCategory(value); setPage(1) }}
                  options={Object.entries(CATEGORY_LABELS).map(([value, label]) => ({ value, label }))} />
        </div>
        <div>
          <span className="field-label" id="rec-mode">{tr("Deposit type")}</span>
          <Select aria-label={tr("Deposit type")} value={mode} onChange={(value) => { setMode(value); setPage(1) }}
                  options={[{ value: '', label: tr("All types") }, ...['FDR', 'RTGS', 'RPGF'].map((value) => ({ value, label: value }))]} />
        </div>
        <div>
          <label className="field-label" htmlFor="rec-from">{tr("Maturity from")}</label>
          <Input id="rec-from" type="date" value={from} onChange={(e) => { setFrom(e.target.value); setPage(1) }} />
        </div>
        <div>
          <label className="field-label" htmlFor="rec-to">{tr("Maturity to")}</label>
          <Input id="rec-to" type="date" value={to} onChange={(e) => { setTo(e.target.value); setPage(1) }} />
        </div>
    </FilterBar>
  )

  return (
    <div className="stack stack--lg">
      <PageHeader title={tr("Deposit records")} subtitle={tr("Search deposits, open their documents and track the next action.")}
                  extra={<>
                    <Button icon={<DownloadOutlined />} href={`/api/instruments/export.csv?${params}`}>{tr("Export CSV")}</Button>
                    {role === 'institution' && <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreate(true)}>{tr("New deposit")}</Button>}
                  </>} />
      {q && <div className="cluster"><span className="muted">{tr("Showing results for")}</span>
        <Tag closable onClose={(e) => { e.preventDefault(); setQ(''); setPage(1) }}>{q}</Tag></div>}
      {wide ? filterBar : <Collapse items={[{ key: 'filters', label: filtered ? tr('Filters (active)') : tr('Filters'), children: filterBar }]} />}

      {query.error && <Alert type="error" showIcon role="alert" message={tr("The records could not be loaded")} description={String(query.error)}
                             action={<Button onClick={() => void query.refetch()}>{tr("Try again")}</Button>} />}

      {wide ? (
        <Panel flush>
          <Table<RecordItem> rowKey="id" loading={query.isPending} dataSource={rows} scroll={{ x: 880 }}
            pagination={{ current: page, pageSize: PAGE_SIZE, total, showSizeChanger: false, onChange: setPage, hideOnSinglePage: true,
                          showTotal: (count) => tr("{0} records", {"0": (count)}) }}
            locale={{ emptyText: <Empty description={filtered ? tr("No records match these filters.") : tr("No deposit records yet.")} /> }}
            columns={[
              { title: tr("Reference"), dataIndex: 'reference', render: (value: string, row) => <Button type="link" onClick={() => setSelected(row.id)}>{value}</Button> },
              { title: tr("Institution"), render: (_, row) => row.institution.name },
              { title: tr("Type"), dataIndex: 'mode', width: 90 },
              { title: tr("Amount"), dataIndex: 'amount', align: 'right', render: (value: string) => formatInr(value) },
              { title: tr("Maturity"), dataIndex: 'maturity_date', render: (value: string) => formatDate(value) },
              { title: tr("Status"), dataIndex: 'status', render: (value: string) => <StatusTag value={value} /> },
              { title: tr("Verification"), dataIndex: 'verification_level', render: (value: string) => <VerificationTag value={value} /> }]} />
        </Panel>
      ) : (
        <>
          {rows.length === 0 && !query.isPending
            ? <Empty description={filtered ? tr("No records match these filters.") : tr("No deposit records yet.")} />
            : <RecordCards rows={rows} onOpen={setSelected} />}
          {total > PAGE_SIZE && <Pagination current={page} pageSize={PAGE_SIZE} total={total} showSizeChanger={false} simple onChange={setPage} />}
        </>
      )}

      <Modal open={create} title={<div className="localized-modal-title"><span>{tr("New deposit")}</span><LanguageToggle /></div>} footer={null} destroyOnHidden width={720} onCancel={() => setCreate(false)}>
        <RecordForm api={api} onCancel={() => setCreate(false)}
                    onSaved={(item) => { setCreate(false); setSelected(item.id); void cache.invalidateQueries({ queryKey: ['records'] }) }} />
      </Modal>
    </div>
  )
}
