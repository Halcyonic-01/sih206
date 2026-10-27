import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { act } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { setLanguage } from '@/i18n'
import { RecordDetail } from './RecordDetail'
import type { Api } from './types'

const detail = {
  id: 7, reference: 'FDR-7', bank: 'Demo Bank', amount: '500000.25', mode: 'RTGS', issue_date: '2026-01-01',
  maturity_date: '2026-12-31', status: 'ACCEPTED', version: 4, verification_level: 'CONFIRMED',
  institution: { id: 1, code: 'A', name: 'Institute A' }, ifsc: 'SBIN0000001', holder_names: 'Trust and AICTE', utr: 'UTR-7',
  lien_marked: true, actions: {}, documents: [], observations: [], findings: [], history: [],
  lineage: { predecessor: null, successor: null },
  field_provenance: {
    amount: { status: 'CONFIRMED', source: 'Bank statement line (SIMULATED)', simulated: true, evidence_id: 3, at: null },
    issue_date: { status: 'MISMATCH', source: 'Bank statement line (SIMULATED)', simulated: true, evidence_id: 3, at: null },
    reference: { status: 'DOCUMENT_REVIEWED', source: 'Officer review', simulated: false, evidence_id: 2, at: null },
    holder_names: { status: 'DECLARED', source: 'Entered by the institution', simulated: false, evidence_id: null, at: null },
  },
}

function renderDetail(body: unknown) {
  const api: Api = { request: vi.fn(async () => body) as unknown as Api['request'], document: vi.fn() }
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter><RecordDetail api={api} id={7} onBack={() => {}} onOpen={() => {}} /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('field provenance on the details tab', () => {
  afterEach(() => act(() => setLanguage('en')))

  it('retains provenance, simulated warnings and original record data when toggled to Hindi', async () => {
    const { container } = renderDetail(detail)
    await screen.findByText('Confirmed (simulated)')
    act(() => setLanguage('hi'))
    expect(screen.getByText('पुष्ट (अनुकरणित)')).toBeInTheDocument()
    expect(screen.getByText(/बैंक की प्रामाणिकता की पुष्टि नहीं/)).toBeInTheDocument()
    expect(screen.getByText('Trust and AICTE')).toBeInTheDocument()
    expect(screen.getByText('Demo Bank')).toBeInTheDocument()
    expect(container.textContent).toContain('FDR-7')
    act(() => setLanguage('en'))
    expect(screen.getByText('Confirmed (simulated)')).toBeInTheDocument()
  })
  it('labels each value in words and marks simulated confirmation as simulated', async () => {
    const { container } = renderDetail(detail)
    expect(await screen.findByText('Confirmed (simulated)')).toBeInTheDocument()
    const tags = Array.from(container.querySelectorAll('.ant-tag')).map((tag) => tag.textContent)
    expect(tags).toEqual(expect.arrayContaining(['Confirmed (simulated)', 'Mismatch', 'Document reviewed', 'Declared']))
    expect(screen.getByText(/not bank authenticity/)).toBeInTheDocument()
  })

  it('shows plain values without tags when the server sends no provenance', async () => {
    renderDetail({ ...detail, field_provenance: undefined })
    expect(await screen.findByText('Trust and AICTE')).toBeInTheDocument()
    const tags = Array.from(document.querySelectorAll('.ant-tag')).map((tag) => tag.textContent)
    for (const label of ['Declared', 'Document reviewed', 'Confirmed (simulated)', 'Mismatch']) expect(tags).not.toContain(label)
    expect(screen.queryByText(/not bank authenticity/)).not.toBeInTheDocument()
  })
})
