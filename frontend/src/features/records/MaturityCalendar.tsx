import { useMemo, useState } from 'react'
import { Badge, Button, Calendar } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { Panel } from '@/components/Panel'
import { formatDate } from '@/lib/format'
import type { MaturityDay } from './types'

/** Month view of when current accepted deposits mature. Pick a day to open its records. */
export function MaturityCalendar({ days, asOf, onOpen }: { days: MaturityDay[]; asOf: string; onOpen: (id: number) => void }) {
  const byDate = useMemo(() => new Map(days.map((day) => [day.date, day])), [days])
  const [picked, setPicked] = useState<string | null>(null)
  const chosen = picked ? byDate.get(picked) : undefined
  return (
    <Panel title="Maturity calendar">
      {days.length === 0 ? <p className="muted">No current deposit matures in the next twelve months.</p> : (
        <div className="stack">
          <Calendar fullscreen={false} defaultValue={dayjs(asOf)}
                    cellRender={(date: Dayjs, info) => {
                      if (info.type !== 'date') return info.originNode
                      const day = byDate.get(date.format('YYYY-MM-DD'))
                      return <div>{info.originNode}{day && <Badge count={day.count} size="small" title={`${day.count} maturing`} />}</div>
                    }}
                    onSelect={(date) => setPicked(date.format('YYYY-MM-DD'))} />
          {picked && (
            <div aria-live="polite">
              <strong>{formatDate(picked)}</strong>
              {chosen ? <ul>{chosen.records.map((record) => (
                <li key={record.id}><Button type="link" onClick={() => onOpen(record.id)}>{record.reference}</Button></li>))}
                {chosen.count > chosen.records.length && <li className="muted">and {chosen.count - chosen.records.length} more</li>}</ul>
                : <p className="muted">No deposit matures on this day.</p>}
            </div>
          )}
        </div>
      )}
    </Panel>
  )
}
