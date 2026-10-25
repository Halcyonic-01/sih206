import { describe, expect, it } from 'vitest'
import { allowedDestination } from './LoginPage'

describe('allowedDestination', () => {
  it('keeps a remembered page the new account may open', () => {
    expect(allowedDestination('/records/5?tab=history', 'officer')).toBe('/records/5?tab=history')
    expect(allowedDestination('/clearance-tasks', 'clearance')).toBe('/clearance-tasks')
  })

  it("sends a different role to the home page instead of the previous user's page", () => {
    expect(allowedDestination('/clearance-tasks', 'officer')).toBe('/')
    expect(allowedDestination('/reconciliation', 'institution')).toBe('/')
  })

  it('leaves pages outside the feature registry to the router', () => {
    expect(allowedDestination('/', 'auditor')).toBe('/')
    expect(allowedDestination('/no-such-page', 'officer')).toBe('/no-such-page')
  })
})
