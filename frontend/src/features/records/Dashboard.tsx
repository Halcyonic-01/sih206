import { t as tr, useLanguage } from '@/i18n';
import { useQuery } from '@tanstack/react-query'
import { Alert, Button, Table } from 'antd'
import { PageHeader } from '@/components/PageHeader'
import { Panel, StatCard } from '@/components/Panel'
import { LoadingState } from '@/components/states'
import { formatPaise } from '@/lib/format'
import { CATEGORY_HINTS, CATEGORY_LABELS, interventionLabel } from '@/lib/labels'
import dayjs from 'dayjs'
import type { Api, DashboardData } from './types'

const CARD_ORDER = ['active', 'expiring', 'matured', 'renewed', 'released', 'pending'] as const
const TONES = { active: 'info', expiring: 'warning', matured: 'danger', renewed: 'success', released: 'success', pending: 'info' } as const

export function DashboardPage({ api, onOpen, onCategory }: { api: Api; onOpen: (id: number) => void; onCategory: (category: string) => void }) {
  useLanguage();
  const query = useQuery({ queryKey: ['records', 'dashboard'], queryFn: () => api.request<DashboardData>('/api/dashboard/') })
  if (query.isPending) return <><PageHeader title={tr("Dashboard")} /><LoadingState rows={6} /></>
  if (query.error) {
    return <><PageHeader title={tr("Dashboard")} />
      <Alert type="error" showIcon message={tr("The dashboard could not be loaded")} description={String(query.error)}
             action={<Button onClick={() => void query.refetch()}>{tr("Try again")}</Button>} /></>
  }
  const data = query.data
  const max = Math.max(1, ...data.maturity_chart.map((m) => m.count))
  const coverage = data.coverage ?? []
  return (
    <div className="stack stack--lg">
      <PageHeader title={tr("Dashboard")} subtitle={tr("Position as of {0}.", {"0": (dayjs(data.as_of).format('D MMMM YYYY'))})} />
      <div className="stat-grid">
        {CARD_ORDER.map((name) => (
          <StatCard key={name} label={CATEGORY_LABELS[name] ?? name} value={data.counts[name] ?? 0} hint={CATEGORY_HINTS[name]}
                    tone={TONES[name]} onClick={() => onCategory(name)} />
        ))}
      </div>

      <Panel title={tr("Needs attention")} flush>
        <Table rowKey={(r) => `${r.kind}:${r.id}`} size="middle" scroll={{ x: 560 }} pagination={{ pageSize: 8, hideOnSinglePage: true, showSizeChanger: false }}
               dataSource={data.interventions} locale={{ emptyText: tr("Nothing needs attention right now.") }} columns={[
          { title: tr("Record"), dataIndex: 'reference', render: (value: string, row) => <Button type="link" onClick={() => onOpen(row.id)}>{value}</Button> },
          { title: tr("Issue"), dataIndex: 'kind', render: (kind: string) => interventionLabel(kind) },
          { title: tr("Next step"), dataIndex: 'next_action' }]} />
      </Panel>

      <div className="two-col">
        <Panel title={tr("Obligation coverage")} flush>
          {!data.coverage_available && coverage.length > 0 && (
            <Alert type="warning" showIcon banner message={tr("Some requirements are not established yet, so coverage cannot be assumed sufficient.")} />
          )}
          <Table rowKey="obligation_id" size="middle" scroll={{ x: 520 }} pagination={false} dataSource={coverage}
                 locale={{ emptyText: tr("No obligations recorded.") }} columns={[
            { title: tr("Institution"), dataIndex: 'institution' },
            { title: tr("Required"), dataIndex: 'required_paise', align: 'right', render: (v: number | null) => v === null ? tr('To be established') : formatPaise(v) },
            { title: tr("Held"), dataIndex: 'held_paise', align: 'right', render: (v: number) => formatPaise(v) },
            { title: tr("Shortfall"), dataIndex: 'shortfall_paise', align: 'right', render: (v: number | null) => v === null ? '—' : formatPaise(v) },
            { title: tr("Term"), dataIndex: 'term_gap', render: (v: boolean) => v ? tr('Gap in coverage') : tr('Covered') }]} />
        </Panel>
        <Panel title={tr("Maturities by month")}>
          {data.maturity_chart.length ? (
            <table className="bar-table">
              <thead><tr><th scope="col">{tr("Month")}</th><th scope="col">{tr("Deposits")}</th><th scope="col"><span className="sr-only">{tr("Share")}</span></th></tr></thead>
              <tbody>
                {data.maturity_chart.map((m) => (
                  <tr key={m.month}>
                    <th scope="row">{dayjs(`${m.month}-01`).format('MMM YYYY')}</th>
                    <td>{m.count}</td>
                    <td className="bar-cell"><div className="bar" aria-hidden style={{ width: `${(m.count / max) * 100}%` }} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted">{tr("No upcoming maturities.")}</p>}
        </Panel>
      </div>
    </div>
  )
}
