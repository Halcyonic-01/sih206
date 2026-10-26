import { useMemo, useState } from 'react';
import { documentBlob } from '@/api/client';
import { PdfViewer } from '@/features/records/PdfViewer';
import type { Api } from '@/features/records/types';
import type { ClearanceEvidence } from './client';

/** Uses the same local PDF.js viewer and protected session client as deposit PDFs. */
export function ClearancePdf({evidence}: {evidence: ClearanceEvidence}) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const reader = useMemo<Api>(() => ({
    request: async () => { throw new Error('Document-only adapter'); },
    document: () => documentBlob(evidence.download_path.replace(/^\/api/, '')),
  }), [evidence.download_path]);
  return <div>
    <p>{evidence.name} · {evidence.page_count} page(s) · uploaded by {evidence.uploaded_by}</p>
    <button type="button" onClick={() => setOpen(!open)}>{open ? 'Hide supporting PDF' : 'View supporting PDF'}</button>
    {open && <PdfViewer api={reader} id={evidence.id} page={page} onPage={setPage} downloadPath={evidence.download_path} />}
    <p className="muted">Readable PDF is not proof of authenticity.</p>
  </div>;
}
