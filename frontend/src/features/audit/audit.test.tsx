import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App as AntApp } from 'antd'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AuditPage from './AuditPage'
import { rangeFilters, show } from './format'

const fetchMock = vi.fn<typeof fetch>()
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
})
const event = {
  id: 7, created_at: '2026-10-24T10:00:00Z', action: 'ACCEPTED', reason: 'Looks fine.',
  instrument: { id: 3, reference: 'FDR-3', institution: 'A' }, actor: { id: 2, username: 'officer' },
}
const page = (results: unknown[]) => ({ count: results.length, page: 1, page_size: 25, total_pages: 1, results })

function route(overrides: Record<string, () => Response> = {}) {
  fetchMock.mockImplementation(async (url) => {
    const path = String(url)
    for (const [needle, make] of Object.entries(overrides)) if (path.includes(needle)) return make()
    if (path.includes('/audit/events/facets/')) return json({ actions: ['ACCEPTED'], actors: [{ id: 2, username: 'officer' }], institutions: ['A'] })
    if (path.includes('/audit/events/7/')) return json({ ...event, before: { status: 'SUBMITTED' }, after: { status: 'ACCEPTED' },
      changes: [{ field: 'status', before: 'SUBMITTED', after: 'ACCEPTED' }] })
    if (path.includes('/audit/events/')) return json(page([event]))
    if (path.includes('/audit/access-log/facets/')) return json({ actions: ['LOGIN'], object_types: [] })
    if (path.includes('/audit/access-log/')) return json(page([]))
    return json({ detail: 'Not found.', code: 'not_found' }, 404)
  })
}

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}><AntApp><MemoryRouter><AuditPage /></MemoryRouter></AntApp></QueryClientProvider>,
  )
}

beforeEach(() => { vi.stubGlobal('fetch', fetchMock); document.cookie = 'csrftoken=t; path=/' })
afterEach(() => { fetchMock.mockReset(); vi.unstubAllGlobals() })

describe('format helpers', () => {
  it('shows values safely and builds inclusive date filters', () => {
    expect(show(null)).toBe('—')
    expect(show({ a: 1 })).toBe('{"a":1}')
    expect(show('<img src=x onerror=alert(1)>')).toBe('<img src=x onerror=alert(1)>') // plain text; React escapes it
    expect(rangeFilters(null)).toEqual({ date_from: undefined, date_to: undefined })
  })
})

describe('AuditPage', () => {
  it('lists audit events with a link to the record and opens the change details', async () => {
    route()
    mount()
    expect(await screen.findByRole('link', { name: 'A / FDR-3' })).toHaveAttribute('href', '/records/3')
    expect(screen.getByText('ACCEPTED', { selector: '.ant-tag' })).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Details' }))
    expect(await screen.findByText('What changed')).toBeInTheDocument()
    expect(await screen.findByText('SUBMITTED', { selector: 'code' })).toBeInTheDocument()
  })

  it('sends the filters to the API', async () => {
    route()
    mount()
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText('Reference'), 'FDR-3')
    await user.click(screen.getByRole('button', { name: /Filter/ }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes('q=FDR-3'))).toBe(true))
  })

  it('shows an empty state when nothing matches', async () => {
    route({ '/audit/events/?': () => json(page([])) })
    mount()
    expect(await screen.findByText('No events match these filters')).toBeInTheDocument()
  })

  it('verifies the chain and reports a broken event', async () => {
    route({ '/audit/chain/verify/': () => json({ status: 'broken', checked: 5, backfilled: 0, unsealed: 0, head: 'ab'.repeat(32),
      broken: [{ event_id: 4, reason: 'event_modified', detail: 'x' }] }) })
    mount()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('tab', { name: 'Integrity' }))
    await user.click(await screen.findByRole('button', { name: /Verify chain/ }))
    expect(await screen.findByText(/Chain broken/)).toBeInTheDocument()
    expect(screen.getByText(/Event #4: Event was changed after it was recorded/)).toBeInTheDocument()
  })

  it('shows a success message for an intact chain', async () => {
    route({ '/audit/chain/verify/': () => json({ status: 'ok', checked: 12, backfilled: 2, unsealed: 0, head: 'cd'.repeat(32), broken: [] }) })
    mount()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('tab', { name: 'Integrity' }))
    await user.click(await screen.findByRole('button', { name: /Verify chain/ }))
    expect(await screen.findByText('Chain verified')).toBeInTheDocument()
    expect(screen.getByText(/12 events sealed, 2 of them sealed late/)).toBeInTheDocument()
  })

  it('shows a not-allowed state when the server says 403', async () => {
    route({ '/audit/events/?': () => json({ detail: 'An auditor account is required.', code: 'permission_denied' }, 403) })
    mount()
    expect(await screen.findByText('Not allowed')).toBeInTheDocument()
  })
})
