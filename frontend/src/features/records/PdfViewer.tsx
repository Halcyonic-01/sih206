import { t as tr, useLanguage } from '@/i18n';
import { useEffect, useRef, useState } from 'react'
import { Alert, Button, InputNumber, Spin } from 'antd'
import { DownloadOutlined, LeftOutlined, RightOutlined } from '@ant-design/icons'
import * as pdfjs from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import type { Api } from './types'

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl

export function PdfViewer({ api, id, page, onPage, downloadPath }: { api: Api; id: number; page: number; onPage: (n: number) => void; downloadPath?: string }) {
  useLanguage();
  const canvas = useRef<HTMLCanvasElement>(null)
  const [pdf, setPdf] = useState<pdfjs.PDFDocumentProxy>()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(true)
  useEffect(() => {
    let disposed = false
    let task: pdfjs.PDFDocumentLoadingTask | undefined
    setPdf(undefined); setError(''); setBusy(true)
    api.document(id).then((blob) => blob.arrayBuffer()).then((data) => {
      if (disposed) return
      task = pdfjs.getDocument({ data: new Uint8Array(data) })
      return task.promise
    }).then((doc) => { if (doc && !disposed) setPdf(doc) })
      .catch(() => { if (!disposed) { setError(tr('This PDF cannot be displayed here. Download it to review it.')); setBusy(false) } })
    return () => { disposed = true; void task?.destroy() }
  }, [api, id])
  useEffect(() => {
    if (!pdf || !canvas.current) return
    let disposed = false
    let render: pdfjs.RenderTask | undefined
    setBusy(true); setError('')
    pdf.getPage(Math.min(Math.max(1, page), pdf.numPages)).then((p) => {
      if (disposed || !canvas.current) return
      const viewport = p.getViewport({ scale: 1.2 })
      canvas.current.width = viewport.width; canvas.current.height = viewport.height
      render = p.render({ canvas: canvas.current, canvasContext: canvas.current.getContext('2d')!, viewport })
      return render.promise
    }).then(() => { if (!disposed) setBusy(false) })
      .catch((e) => { if (!disposed && e.name !== 'RenderingCancelledException') { setError(tr('This page could not be shown.')); setBusy(false) } })
    return () => { disposed = true; render?.cancel() }
  }, [pdf, page])
  return (
    <section aria-label={tr("Supporting PDF")}>
      <div className="cluster pdf-toolbar">
        <Button icon={<LeftOutlined />} disabled={!pdf || page <= 1} onClick={() => onPage(page - 1)} aria-label={tr("Previous page")} />
        <InputNumber aria-label={tr("PDF page")} min={1} max={pdf?.numPages || 1} value={page} onChange={(n) => onPage(Number(n) || 1)} style={{ width: 84 }} />
        <span className="muted">{tr("of  ")}{pdf?.numPages ?? '…'}</span>
        <Button icon={<RightOutlined />} disabled={!pdf || page >= pdf.numPages} onClick={() => onPage(page + 1)} aria-label={tr("Next page")} />
        <Button type="link" icon={<DownloadOutlined />} href={downloadPath ?? `/api/documents/${id}/download/`} style={{ marginInlineStart: 'auto' }}>{tr("Download original")}</Button>
      </div>
      {error && <Alert type="error" showIcon message={error} style={{ marginTop: 12 }} />}
      <Spin spinning={busy}><div className="pdf-stage"><canvas ref={canvas} role="img" aria-label={tr("PDF page {0}", {"0": (page)})} /></div></Spin>
    </section>
  )
}
