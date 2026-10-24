import {useEffect, useRef, useState} from 'react';
import {Alert, Button, InputNumber, Space, Spin} from 'antd';
import * as pdfjs from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import type {Api} from './types';

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

export function PdfViewer({api, id, page, onPage}: {api: Api; id: number; page: number; onPage: (n: number) => void}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [pdf, setPdf] = useState<pdfjs.PDFDocumentProxy>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  useEffect(() => {
    let disposed = false;
    let task: pdfjs.PDFDocumentLoadingTask | undefined;
    setPdf(undefined); setError(''); setBusy(true);
    api.document(id).then(blob => blob.arrayBuffer()).then(data => {
      if (disposed) return;
      task = pdfjs.getDocument({data: new Uint8Array(data)});
      return task.promise;
    }).then(doc => {if (doc && !disposed) setPdf(doc);})
      .catch(() => {if (!disposed) {setError('Unable to display this PDF. Download it for manual review.'); setBusy(false);}});
    return () => {disposed = true; void task?.destroy();};
  }, [api, id]);
  useEffect(() => {
    if (!pdf || !canvas.current) return;
    let disposed = false;
    let render: pdfjs.RenderTask | undefined;
    setBusy(true); setError('');
    pdf.getPage(Math.min(Math.max(1, page), pdf.numPages)).then(p => {
      if (disposed || !canvas.current) return;
      const viewport = p.getViewport({scale: 1.2});
      canvas.current.width = viewport.width; canvas.current.height = viewport.height;
      render = p.render({canvas: canvas.current, canvasContext: canvas.current.getContext('2d')!, viewport});
      return render.promise;
    }).then(() => {if (!disposed) setBusy(false);})
      .catch(e => {if (!disposed && e.name !== 'RenderingCancelledException') {setError('This page could not be rendered.'); setBusy(false);}});
    return () => {disposed = true; render?.cancel();};
  }, [pdf, page]);
  return <section aria-label="Supporting PDF">
    <Space wrap>
      <Button disabled={!pdf || page <= 1} onClick={() => onPage(page - 1)}>Previous page</Button>
      <InputNumber aria-label="PDF page" min={1} max={pdf?.numPages || 1} value={page} onChange={n => onPage(Number(n) || 1)}/>
      <span>of {pdf?.numPages ?? '…'}</span>
      <Button disabled={!pdf || page >= pdf.numPages} onClick={() => onPage(page + 1)}>Next page</Button>
      <a href={`/api/documents/${id}/download/`}>Download original</a>
    </Space>
    {error && <Alert type="error" message={error}/>}
    <Spin spinning={busy}><canvas ref={canvas} role="img" aria-label={`PDF page ${page}`} style={{width: '100%', height: 'auto', marginTop: 16}}/></Spin>
    <p>Use the original download with an accessible PDF reader if the canvas is unsuitable.</p>
  </section>;
}
