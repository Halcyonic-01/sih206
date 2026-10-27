import { Tag, Tooltip } from 'antd'
import type { Waiting } from './types'

type Look = { color?: string; word: string }
const OK: Look = { word: '' }
const STYLE: Record<string, Look> = { ok: OK, soon: { color: 'orange', word: 'getting late' }, overdue: { color: 'red', word: 'overdue' } }

/** "Waiting 3 working days", coloured by the escalation matrix limit. The words say it too, not only the colour. */
export function WaitingBadge({ waiting }: { waiting?: Waiting | null }) {
  if (!waiting) return null
  const style = STYLE[waiting.band] ?? OK
  const days = waiting.working_days
  const text = `Waiting ${days} working day${days === 1 ? '' : 's'}${style.word ? ` · ${style.word}` : ''}`
  return (
    <Tooltip title={`Since ${waiting.since}. The limit is ${waiting.limit} working days.`}>
      <Tag color={style.color} style={{ marginInlineStart: 8 }}>{text}</Tag>
    </Tooltip>
  )
}
