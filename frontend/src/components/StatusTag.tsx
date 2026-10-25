import { Tag } from 'antd'
import { statusLabel, verificationLabel, type Labelled } from '@/lib/labels'

function ToneTag({ value }: { value: Labelled }) {
  return <Tag bordered={false} className={`tag tag--${value.tone}`}>{value.label}</Tag>
}

/** Colour-coded status (record, release, clearance, obligation). The label always carries the meaning, not the colour. */
export function StatusTag({ value }: { value: string | null | undefined }) {
  return <ToneTag value={statusLabel(value)} />
}

export function VerificationTag({ value }: { value: string | null | undefined }) {
  return <ToneTag value={verificationLabel(value)} />
}
