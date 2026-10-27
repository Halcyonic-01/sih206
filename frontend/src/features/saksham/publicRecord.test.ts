import { describe, expect, it } from 'vitest'
import { publicRecord } from './client'

const base = { serial: 'S-1', issue_date: '2026-10-27', institution_name: 'Inst', kind: 'NOC', status: 'ISSUED' }

describe('publicRecord', () => {
  it('accepts the five public fields, with or without a signature result', () => {
    expect(publicRecord(base).serial).toBe('S-1')
    const signed = { ...base, signature: { checked: true, valid: true, matches_record: true, kid: 'ab12cd34', key_kind: 'CONFIGURED' } }
    expect(publicRecord(signed).signature?.valid).toBe(true)
  })
  it('rejects unknown extra fields and a malformed signature', () => {
    expect(() => publicRecord({ ...base, internal_note: 'x' })).toThrow()
    expect(() => publicRecord({ ...base, signature: { valid: 'yes' } })).toThrow()
    expect(() => publicRecord({ ...base, status: 'OTHER' })).toThrow()
  })
})
