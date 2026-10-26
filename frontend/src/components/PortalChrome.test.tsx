import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { PortalFooter, PortalIdentity } from './PortalChrome'

describe('prototype identity', () => {
  it('labels the project without claiming official endorsement', () => {
    render(<MemoryRouter><PortalIdentity /><PortalFooter /></MemoryRouter>)
    expect(screen.getByRole('link', { name: 'Pramaan home' })).toHaveAttribute('href', '/')
    expect(screen.getByText('AICTE Security Deposit / FDR Portal')).toBeVisible()
    expect(screen.queryByText(/Independent student project/)).not.toBeInTheDocument()
    expect(screen.queryByText('Emblem placeholder')).not.toBeInTheDocument()
    expect(screen.getByText(/Not an official AICTE service or endorsement/)).toBeVisible()
    expect(screen.getByText(/simulated matches do not establish bank authenticity/)).toBeVisible()
  })

  it('keeps the prototype and bank-authenticity warnings in the footer', () => {
    render(<PortalFooter />)
    expect(screen.getByRole('contentinfo')).toHaveTextContent('AICTE Security Deposit / FDR Portal — Prototype.')
    expect(screen.getByRole('contentinfo')).toHaveTextContent('Acceptance is for tracking.')
  })
})
