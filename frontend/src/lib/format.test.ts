import { describe, expect, it } from 'vitest'
import { formatDate, formatDateTime, formatInr, formatPaise } from './format'
import { findingLabel, humanize, interventionLabel, statusLabel, verificationLabel } from './labels'

describe('money and dates', () => {
  it('groups rupees in lakh and crore', () => {
    expect(formatInr('500000.25')).toBe('₹5,00,000.25')
    expect(formatInr(10000000)).toBe('₹1,00,00,000.00')
    expect(formatPaise(150000000)).toBe('₹15,00,000.00')
    expect(formatPaise('30000000')).toBe('₹3,00,000.00')
  })

  it('shows a dash for missing values and passes unparseable text through', () => {
    expect(formatInr(null)).toBe('—')
    expect(formatInr('')).toBe('—')
    expect(formatInr('n/a')).toBe('n/a')
    expect(formatPaise(undefined)).toBe('—')
    expect(formatDate(null)).toBe('—')
  })

  it('formats dates without a time zone surprise', () => {
    expect(formatDate('2026-10-25')).toBe('25 Oct 2026')
    expect(formatDateTime('2026-10-25T09:05:00')).toBe('25 Oct 2026, 09:05')
  })
})

describe('labels', () => {
  it('words the record statuses and carries a tone', () => {
    expect(statusLabel('CHANGES_REQUESTED')).toEqual({ label: 'Changes requested', tone: 'warning' })
    expect(statusLabel('ACCEPTED').tone).toBe('success')
    expect(verificationLabel('DISCREPANCY').tone).toBe('danger')
  })

  it('falls back to readable text for codes it does not know', () => {
    expect(statusLabel('SOMETHING_NEW')).toEqual({ label: 'Something new', tone: 'neutral' })
    expect(humanize('DRAFT_CREATED')).toBe('Draft created')
    expect(interventionLabel('blocking_observation')).toBe('Blocking observation unresolved')
    expect(findingLabel('PROOF_OVERDUE')).toBe('Deposit proof overdue')
    expect(statusLabel(null).label).toBe('—')
  })
})
