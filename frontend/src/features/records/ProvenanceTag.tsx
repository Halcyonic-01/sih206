import { Tag, Tooltip } from 'antd'
import type { FieldProvenance } from './types'
import { t, useLanguage } from '@/i18n'

const LABELS: Record<string, { text: string; color?: string }> = {
  DECLARED: { text: 'Declared' },
  DOCUMENT_REVIEWED: { text: 'Document reviewed', color: 'blue' },
  CONFIRMED: { text: 'Confirmed', color: 'green' },
  MISMATCH: { text: 'Mismatch', color: 'red' },
}
const SYSTEM_SOURCES = new Set(['Entered by the institution', 'Officer review', 'Bank statement line',
  'Bank statement line (SIMULATED)', 'Bank email confirmation', 'Bank email confirmation (SIMULATED)'])

/** Says where a value stands, in words (never colour alone). "Confirmed" from a simulated source is labelled as such. */
export function ProvenanceTag({ provenance }: { provenance?: FieldProvenance }) {
  useLanguage()
  if (!provenance) return null
  const label = LABELS[provenance.status] ?? { text: provenance.status }
  const text = provenance.status === 'CONFIRMED' && provenance.simulated ? 'Confirmed (simulated)' : label.text
  return (
    <Tooltip title={SYSTEM_SOURCES.has(provenance.source) ? t(provenance.source) : provenance.source}>
      <Tag color={label.color} style={{ marginInlineStart: 8 }}>{LABELS[provenance.status] ? t(text) : text}</Tag>
    </Tooltip>
  )
}
