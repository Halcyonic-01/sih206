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
          <h3>Read on this computer</h3>
          <p className="muted">Reads up to five English pages with local OCR. Nothing leaves this computer.</p>
          <Button loading={busy} onClick={() => void extract(true)}>Read with local OCR</Button>
        </div>
        <div className="stack">
          <h3>AI assistance</h3>
          <p className="muted">Optional and off unless enabled by the administrator. Suggestions never change a decision.</p>
          <Checkbox checked={consent} onChange={(e) => setConsent(e.target.checked)}>
            This document is synthetic, and I agree to send it to Google Gemini. Free-tier requests may be used by Google to improve its products.
          </Checkbox>
          <Button loading={busy} onClick={() => void extract(false)}>Extract with AI</Button>
        </div>
      </div>
      {error && <Alert type="error" showIcon message={error} />}
      {result && <Alert type={result.status === 'success' ? 'warning' : 'info'} showIcon message={result.label}
                        description={result.detail || 'Check each suggested value against its source page.'} />}
      {result?.status === 'success' && (
        <>
          {result.pages?.map((page) => (
            <details key={page.page}><summary>Page {page.page} · OCR score {page.confidence}/100</summary><pre style={{ whiteSpace: 'pre-wrap' }}>{page.text}</pre></details>
          ))}
          <Table rowKey="field" size="small" pagination={false} scroll={{ x: 420 }}
                 dataSource={Object.entries(result.fields).map(([field, value]) => ({ field, ...value }))} columns={[
            { title: 'Field', dataIndex: 'field', render: (v: string) => humanize(v) },
            { title: 'Suggested value', dataIndex: 'value', render: (v: string | null) => v ?? 'Not found' },
            { title: 'Page', dataIndex: 'page', width: 80, render: (v: number | null) => v ?? '—' }]} />
          {result.findings.map((f) => (
            <Alert key={f.field} type="warning" showIcon message={`Differs from the record: ${humanize(f.field)}`}
                   description={`Record says ${f.declared}; the document suggests ${f.suggested}. Needs human review.`} />
          ))}
          <div>
            <Button type="primary" disabled={!canUse} onClick={() => onUse(Object.fromEntries(Object.entries(result.fields)
              .filter(([, value]) => value.value !== null).map(([key, value]) => [key, value.value!])))}>Use these values in the form</Button>
            <p className="muted" style={{ marginTop: 8 }}>This only fills the form. Review it and save yourself. Accepted records cannot be edited here.</p>
          </div>
        </>
      )}
    </div>
  )
}
