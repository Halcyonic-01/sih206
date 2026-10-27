import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MaturityCalendar } from './MaturityCalendar'
import { WaitingBadge } from './WaitingBadge'

describe('queue ageing', () => {
  it('says how long something has waited in words, including when it is late', () => {
    const { rerender } = render(<WaitingBadge waiting={{ working_days: 3, calendar_days: 5, limit: 7, band: 'ok', since: '2026-10-20' }} />)
    expect(screen.getByText('Waiting 3 working days')).toBeInTheDocument()
    rerender(<WaitingBadge waiting={{ working_days: 9, calendar_days: 12, limit: 7, band: 'overdue', since: '2026-10-15' }} />)
    expect(screen.getByText('Waiting 9 working days · overdue')).toBeInTheDocument()
    rerender(<WaitingBadge waiting={{ working_days: 1, calendar_days: 1, limit: 7, band: 'ok', since: '2026-10-26' }} />)
    expect(screen.getByText('Waiting 1 working day')).toBeInTheDocument()
    rerender(<WaitingBadge waiting={null} />)
    expect(screen.queryByText(/Waiting/)).not.toBeInTheDocument()
  })

  it('lists the deposits maturing on the day that is picked', async () => {
    const onOpen = vi.fn()
    render(<QueryClientProvider client={new QueryClient()}>
      <MaturityCalendar asOf="2026-10-10" onOpen={onOpen}
        days={[{ date: '2026-10-20', count: 8, records: [{ id: 4, reference: 'FDR-4' }, { id: 5, reference: 'FDR-5' }] }]} />
    </QueryClientProvider>)
    await userEvent.click(screen.getByTitle('2026-10-20'))
    await userEvent.click(await screen.findByRole('button', { name: 'FDR-4' }))
    expect(onOpen).toHaveBeenCalledWith(4)
    expect(screen.getByText('and 6 more')).toBeInTheDocument()
  })
})
