import { t as tr, useLanguage } from '@/i18n';
import { Tag } from 'antd'
import { statusLabel, verificationLabel, type Labelled } from '@/lib/labels'

function ToneTag({ value }: { value: Labelled }) {
  useLanguage();
  return <Tag bordered={false} className={`tag tag--${value.tone}`}>{tr(value.label)}</Tag>
}

/** Colour-coded status (record, release, clearance, obligation). The label always carries the meaning, not the colour. */
export function StatusTag({ value }: { value: string | null | undefined }) {
  useLanguage();
  return <ToneTag value={statusLabel(value)} />
}

export function VerificationTag({ value }: { value: string | null | undefined }) {
  useLanguage();
  return <ToneTag value={verificationLabel(value)} />
}
