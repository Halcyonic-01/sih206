import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { PageHeader } from '@/components/PageHeader'
import { StatCard, SummaryList } from '@/components/Panel'
import { StatusTag } from '@/components/StatusTag'
import { Brand } from '@/components/Logo'
import type { AppRoute } from '@/routes/types'
import { GROUPS, navItemsFor, selectedPath } from './navigation'

const routes: AppRoute[] = [
  { path: '/audit', element: null, roles: ['auditor'], menu: { label: 'Audit and access', order: 80 } },
  { path: '/records', element: null, roles: ['institution', 'officer'], menu: { label: 'Records', order: 10 } },
  { path: '/records/:id', element: null, roles: ['institution', 'officer'] },
  { path: '/dashboard', element: null, roles: ['institution', 'officer'], menu: { label: 'Dashboard', order: 20 } },
  { path: '/notifications', element: null, menu: { label: 'Notifications', order: 90 } },
]

describe('navigation', () => {
  it('lists only what the role may open, grouped and in order', () => {
    const officer = navItemsFor(routes, 'officer').map((item) => item.label)
    expect(officer).toEqual(['Dashboard', 'Notifications', 'Deposit records'])
    expect(navItemsFor(routes, 'auditor').map((item) => item.label)).toEqual(['Notifications', 'Audit and access'])
    expect(navItemsFor(routes, null).map((item) => item.label)).toEqual(['Notifications'])
    const groups = navItemsFor(routes, 'officer').map((item) => GROUPS.indexOf(item.group))
    expect(groups).toEqual([...groups].sort((a, b) => a - b))
  })

  it('highlights the longest matching path', () => {
    const items = navItemsFor(routes, 'officer')
    expect(selectedPath(items, '/records/12')).toEqual(['/records'])
    expect(selectedPath(items, '/elsewhere')).toEqual([])
  })
})

describe('shared components', () => {
  it('renders one h1, a breadcrumb and actions; crumbs are plain text outside a router', () => {
    render(<PageHeader title="Deposit records" subtitle="Search deposits." extra={<button>Export</button>}
                       breadcrumb={[{ label: 'Home', to: '/' }, { label: 'Records' }]} />)
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByText('Home')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Home' })).not.toBeInTheDocument()
    expect(screen.getByText('Records')).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: 'Export' })).toBeInTheDocument()
  })

  it('links breadcrumb items inside a router', () => {
    render(<MemoryRouter><PageHeader title="Case" breadcrumb={[{ label: 'Release cases', to: '/releases' }, { label: 'Case 1' }]} /></MemoryRouter>)
    expect(screen.getByRole('link', { name: 'Release cases' })).toHaveAttribute('href', '/releases')
  })

  it('shows status as words, not only colour, and a dash for empty summary values', () => {
    render(<><StatusTag value="CHANGES_REQUESTED" /><StatCard label="Active" value={12} hint="Accepted deposits" />
      <SummaryList items={[{ label: 'Branch', value: '' }, { label: 'IFSC', value: 'SBIN0001234' }]} /></>)
    expect(screen.getByText('Changes requested')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('Branch').nextElementSibling).toHaveTextContent('—')
    expect(screen.getByText('IFSC').nextElementSibling).toHaveTextContent('SBIN0001234')
  })

  it('keeps the logo decorative next to the name, and labelled on its own', () => {
    const { container } = render(<Brand />)
    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
    expect(screen.getByText('Pramaan')).toBeInTheDocument()
  })
})
