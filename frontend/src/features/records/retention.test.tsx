import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { RetentionPanel } from './RetentionPanel'
import type { Api, Retention } from './types'

const base: Retention = { settled_on: '2015-01-01', archival_due_on: '2025-01-01', archival_due: true, archived: false,
  archived_at: null, legal_hold: false, hold_reason: '', retention_years: 10 }

function show(retention: Retention, actions: Record<string, boolean>, request = vi.fn(async () => ({}))) {
  const api: Api = { request: request as unknown as Api['request'], document: vi.fn() }
  render(<QueryClientProvider client={new QueryClient()}><RetentionPanel api={api} id={7} retention={retention} actions={actions} /></QueryClientProvider>)
  return request
}

describe('retention panel', () => {
  it('is hidden for a record that is not settled', () => {
    const { container } = render(<QueryClientProvider client={new QueryClient()}>
      <RetentionPanel api={{ request: vi.fn(), document: vi.fn() } as Api} id={1} actions={{}}
        retention={{ ...base, settled_on: null, archival_due_on: null, archival_due: false }} /></QueryClientProvider>)
    expect(container).toBeEmptyDOMElement()
  })

  it('lets the authority archive with a reason', async () => {
    const request = show(base, { can_archive: true, can_hold: true })
    expect(screen.getAllByText('Archival due').length).toBeGreaterThan(0)
    await userEvent.click(screen.getByRole('button', { name: 'Archive' }))
    await userEvent.type(await screen.findByLabelText('Reason'), 'Retention period has passed')
    await userEvent.click(screen.getByRole('button', { name: 'Record' }))
    await vi.waitFor(() => expect(request).toHaveBeenCalledWith('/api/instruments/7/archive/', { method: 'POST', body: { reason: 'Retention period has passed' } }))
  })

  it('offers only what the server allows and says when a record is frozen', () => {
    show({ ...base, archived: true, archival_due: false, legal_hold: true, hold_reason: 'Court order 12' }, { can_lift_hold: true })
    expect(screen.getByText('Archived and frozen')).toBeInTheDocument()
    expect(screen.getByText(/Court order 12/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Archive' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Lift legal hold' })).toBeInTheDocument()
  })
})
