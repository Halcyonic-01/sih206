import { Tag, Tooltip } from 'antd'
import type { FieldProvenance } from './types'

const LABELS: Record<string, { text: string; color?: string }> = {
  DECLARED: { text: 'Declared' },
  DOCUMENT_REVIEWED: { text: 'Document reviewed', color: 'blue' },
  CONFIRMED: { text: 'Confirmed', color: 'green' },
  MISMATCH: { text: 'Mismatch', color: 'red' },
}

/** Says where a value stands, in words (never colour alone). "Confirmed" from a simulated source is labelled as such. */
export function ProvenanceTag({ provenance }: { provenance?: FieldProvenance }) {
  if (!provenance) return null
  const label = LABELS[provenance.status] ?? { text: provenance.status }
  const text = provenance.status === 'CONFIRMED' && provenance.simulated ? 'Confirmed (simulated)' : label.text
  return (
    <Tooltip title={provenance.source}>
      <Tag color={label.color} style={{ marginInlineStart: 8 }}>{text}</Tag>
    </Tooltip>
  )
}
