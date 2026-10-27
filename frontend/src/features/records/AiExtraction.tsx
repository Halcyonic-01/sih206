import { t as tr, useLanguage } from '@/i18n';
import { useState } from 'react'
import { Alert, Button, Checkbox, Table } from 'antd'
import { humanize } from '@/lib/labels'
import type { Api } from './types'

type Result = {
  status: string; label: string; detail?: string
  fields: Record<string, { value: string | null; page: number | null }>
  pages?: { page: number; text: string; confidence: number }[]
  findings: { code: string; field: string; declared: string; suggested: string }[]
}

export function AiExtraction({ api, documentId, canUse, onUse }: {
  api: Api; documentId: number; canUse: boolean; onUse: (values: Record<string, string>) => void
}) {
  useLanguage();
  const [consent, setConsent] = useState(false)
  const [result, setResult] = useState<Result>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function extract(local = false) {
    setBusy(true); setError(''); setResult(undefined)
    try {
      setResult(await api.request<Result>(`/api/documents/${documentId}/${local ? 'ocr' : 'ai-extract'}/`, {
        method: 'POST', body: { consent, synthetic: consent } }))
    } catch (e) { setError(String(e)) } finally { setBusy(false) }
  }
  return (
    <div className="stack">
      <div className="two-col">
        <div className="stack">
          <h3>{tr("Read on this computer")}</h3>
          <p className="muted">{tr("Reads up to five English pages with local OCR. Nothing leaves this computer.")}</p>
          <Button loading={busy} onClick={() => void extract(true)}>{tr("Read with local OCR")}</Button>
        </div>
        <div className="stack">
          <h3>{tr("AI assistance")}</h3>
          <p className="muted">{tr("Optional and off unless enabled by the administrator. Suggestions never change a decision.")}</p>
          <Checkbox checked={consent} onChange={(e) => setConsent(e.target.checked)}>
            {tr("This document is synthetic, and I agree to send it to Google Gemini. Free-tier requests may be used by Google to improve its products.")}</Checkbox>
          <Button loading={busy} onClick={() => void extract(false)}>{tr("Extract with AI")}</Button>
        </div>
      </div>
      {error && <Alert type="error" showIcon message={error} />}
      {result && <Alert type={result.status === 'success' ? 'warning' : 'info'} showIcon message={tr(result.label)}
                        description={tr(result.detail || 'Check each suggested value against its source page.')} />}
      {result?.status === 'success' && (
        <>
          {result.pages?.map((page) => (
            <details key={page.page}><summary>{tr("Page  ")}{page.page} {tr("  · OCR score  ")}{page.confidence}/100</summary><pre style={{ whiteSpace: 'pre-wrap' }}>{page.text}</pre></details>
          ))}
          <Table rowKey="field" size="small" pagination={false} scroll={{ x: 420 }}
                 dataSource={Object.entries(result.fields).map(([field, value]) => ({ field, ...value }))} columns={[
            { title: tr("Field"), dataIndex: 'field', render: (v: string) => humanize(v) },
            { title: tr("Suggested value"), dataIndex: 'value', render: (v: string | null) => v ?? tr('Not found') },
            { title: tr("Page"), dataIndex: 'page', width: 80, render: (v: number | null) => v ?? '—' }]} />
          {result.findings.map((f) => (
            <Alert key={f.field} type="warning" showIcon message={tr("Differs from the record: {0}", {"0": (humanize(f.field))})}
                   description={tr("Record says {0}; the document suggests {1}. Needs human review.", {"0": (f.declared), "1": (f.suggested)})} />
          ))}
          <div>
            <Button type="primary" disabled={!canUse} onClick={() => onUse(Object.fromEntries(Object.entries(result.fields)
              .filter(([, value]) => value.value !== null).map(([key, value]) => [key, value.value!])))}>{tr("Use these values in the form")}</Button>
            <p className="muted" style={{ marginTop: 8 }}>{tr("This only fills the form. Review it and save yourself. Accepted records cannot be edited here.")}</p>
          </div>
        </>
      )}
    </div>
  )
}
