import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import {MemoryRouter} from 'react-router-dom'
import {RecordDetail} from './RecordDetail'
import { DashboardPage } from './Dashboard'
import { RecordsWorkspace } from './RecordsWorkspace'
import type { Api } from './types'

const record = {
  id: 7, reference: 'FDR-7', bank: 'Demo Bank', amount: '500000.25', mode: 'FDR', issue_date: '2026-01-01',
  maturity_date: '2026-12-31', status: 'CHANGES_REQUESTED', version: 2, verification_level: 'DISCREPANCY',
  institution: { id: 1, code: 'A', name: 'Institute A' },
}

function api(responses: Record<string, unknown>): Api {
  return {
    request: vi.fn(async (path: string) => {
      const key = Object.keys(responses).find((prefix) => path.startsWith(prefix))
      if (!key) throw new Error(`unexpected request ${path}`)
      return responses[key]
    }) as unknown as Api['request'],
    document: vi.fn(),
  }
}
const wrap = (node: React.ReactNode) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>
)

describe('readiness action entry points', () => {
  const detail = {...record, actions: {can_upload: true, can_submit: true}, documents: [], observations: [], findings: [], history: [], lineage: {}};
  it('opens the permitted upload form with the exact category without writing', async () => {
    const source = api({'/api/instruments/7/': detail});
    render(wrap(<MemoryRouter><RecordDetail api={source} id={7} onBack={() => {}} onOpen={() => {}}
      readinessAction="upload" readinessKind="AFFIDAVIT_3" /></MemoryRouter>));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('combobox', {name: 'Document category'})).toBeInTheDocument();
    expect(screen.getByText('Affidavit 3')).toBeInTheDocument();
    expect(vi.mocked(source.request).mock.calls.every(call => !call[1]?.method)).toBe(true);
  });
  it('cannot open an upload dialog when the server denies upload', async () => {
    render(wrap(<MemoryRouter><RecordDetail api={api({'/api/instruments/7/': {...detail, actions: {}}})} id={7}
      onBack={() => {}} onOpen={() => {}} readinessAction="upload" readinessKind="AFFIDAVIT_3" /></MemoryRouter>));
    await screen.findByRole('heading', {name: 'FDR-7'});
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
  it('opens the new-deposit form with the chosen obligation', async () => {
    render(wrap(<RecordsWorkspace api={api({'/api/instruments/?': {count: 0, results: []}})} role="institution"
      readinessAction="new" readinessObligation="12" />));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('spinbutton', {name: 'Obligation ID (optional)'})).toHaveValue('12');
  });
});

describe('records list', () => {
  it('shows each deposit as a card on a phone, with money, status and verification in words', async () => {
    render(wrap(<RecordsWorkspace api={api({ '/api/instruments/?': { count: 1, page: 1, page_size: 20, results: [record] } })} role="officer" />))
    expect(await screen.findByRole('button', { name: 'FDR-7' })).toBeInTheDocument()
    expect(screen.getByText('₹5,00,000.25')).toBeInTheDocument()
    expect(screen.getByText('Changes requested')).toBeInTheDocument()
    expect(screen.getByText('Discrepancy')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Deposit records' })).toBeInTheDocument()
    // Filters sit in a collapsed panel on small screens; only institutions can add deposits.
    expect(screen.getByText('Filters')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /New deposit/ })).not.toBeInTheDocument()
  })

  it('offers New deposit to an institution and an empty state when nothing matches', async () => {
    render(wrap(<RecordsWorkspace api={api({ '/api/instruments/?': { count: 0, page: 1, page_size: 20, results: [] } })} role="institution" />))
    expect(await screen.findByText('No deposit records yet.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /New deposit/ })).toBeInTheDocument()
  })

  it('shows a retryable error instead of a blank page', async () => {
    const failing: Api = { request: vi.fn(async () => { throw new Error('boom') }) as unknown as Api['request'], document: vi.fn() }
    render(wrap(<RecordsWorkspace api={failing} role="officer" />))
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be loaded')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Try again' }))
  })
})

describe('dashboard', () => {
  const data = {
    as_of: '2026-10-25', coverage_available: false,
    counts: { all: 20, active: 12, expiring: 9, matured: 2, renewed: 1, released: 1, pending: 2 },
    interventions: [{ id: 3, reference: 'FDR-3', kind: 'blocking_observation', next_action: 'Resolve blocking evidence observations' }],
    coverage: [{ obligation_id: 1, institution: 'Institute A', required_paise: 150000000, held_paise: 0, shortfall_paise: 150000000, term_gap: true }],
    maturity_chart: [{ month: '2026-11', count: 3 }],
  }

  it('shows the six categories, plain-language issues, rupee amounts and the month chart as a table', async () => {
    const onCategory = vi.fn()
    render(wrap(<DashboardPage api={api({ '/api/dashboard/': data })} onOpen={vi.fn()} onCategory={onCategory} />))
    expect(await screen.findByRole('button', { name: /Active/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument()
    for (const label of ['Active', 'Expiring', 'Matured', 'Renewed', 'Released', 'Pending']) {
      expect(screen.getByRole('button', { name: new RegExp(label) })).toBeInTheDocument()
    }
    expect(screen.getByText('Blocking observation unresolved')).toBeInTheDocument()
    expect(screen.getAllByText('₹15,00,000.00').length).toBeGreaterThan(0)
    expect(screen.getByRole('row', { name: /Nov 2026/ })).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: /Matured/ }))
    expect(onCategory).toHaveBeenCalledWith('matured')
  })
})
