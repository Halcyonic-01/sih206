import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { safeLink } from './api'
import Bell from './Bell'
import InboxPage from './InboxPage'

const fetchMock = vi.fn<typeof fetch>()
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
})
const item = (id: number, read = false) => ({
  id, template_id: 't', subject: `Subject ${id}`, body: `Body ${id}`, link: `/records/${id}`, severity: 'warning',
  created_at: '2026-10-24T10:00:00Z', read_at: read ? '2026-10-24T11:00:00Z' : null, is_read: read,
})

function mount(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter>{node}</MemoryRouter></QueryClientProvider>)
}

beforeEach(() => { vi.stubGlobal('fetch', fetchMock); document.cookie = 'csrftoken=t; path=/' })
afterEach(() => { fetchMock.mockReset(); vi.unstubAllGlobals() })

describe('safeLink', () => {
  it('only allows in-app paths', () => {
    expect(safeLink('/records/4')).toBe('/records/4')
    expect(safeLink('https://evil.example')).toBeNull()
    expect(safeLink('//evil.example')).toBeNull()
    expect(safeLink('')).toBeNull()
  })
})

describe('Bell', () => {
  it('shows the unread count in its accessible name and lists notifications when opened', async () => {
    fetchMock.mockImplementation(async (url) => String(url).includes('unread-count')
      ? json({ count: 3 })
      : json({ count: 2, page: 1, page_size: 6, total_pages: 1, results: [item(1), item(2, true)] }))
    mount(<Bell />)
    const button = await screen.findByRole('button', { name: 'Notifications, 3 unread' })
    await userEvent.setup().click(button)
    expect(await screen.findByText('Subject 1')).toBeInTheDocument()
    expect(screen.getByText('Subject 2')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View all' })).toHaveAttribute('href', '/notifications')
  })
})

describe('InboxPage', () => {
  it('shows an empty state', async () => {
    fetchMock.mockImplementation(async (url) => String(url).includes('unread-count')
      ? json({ count: 0 }) : json({ count: 0, page: 1, page_size: 20, total_pages: 1, results: [] }))
    mount(<InboxPage />)
    expect(await screen.findByText('No notifications yet')).toBeInTheDocument()
  })

  it('shows a server error with a retry', async () => {
    fetchMock.mockImplementation(async (url) => String(url).includes('unread-count')
      ? json({ count: 0 }) : json({ detail: 'Boom', code: 'error' }, 500))
    mount(<InboxPage />)
    expect(await screen.findByText('Something went wrong')).toBeInTheDocument()
  })

  it('marks one notification read and refreshes', async () => {
    const calls: string[] = []
    fetchMock.mockImplementation(async (url, init) => {
      const path = String(url)
      calls.push(`${init?.method ?? 'GET'} ${path}`)
      if (path.includes('unread-count')) return json({ count: 1 })
      if (path.endsWith('/read/')) return json(item(1, true))
      return json({ count: 1, page: 1, page_size: 20, total_pages: 1, results: [item(1)] })
    })
    mount(<InboxPage />)
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Mark read' }))
    await waitFor(() => expect(calls).toContain('POST /api/notifications/1/read/'))
  })
})
