import { describe, expect, it } from 'vitest';
import { money, paise, publicRecord } from './client';

describe('exact paise and unknown money', () => {
  it('preserves the original money formatting and parsing behavior', () => {
    expect(money(null)).toBe('Unavailable');
    expect(money(0)).toBe('₹0.00');
    expect(money(50000025)).toBe('₹5,00,000.25');
    expect(money(1.5)).toBe('Unavailable');
    expect(paise('123.45')).toBe(12345);
    expect(money('9007199254740993')).toBe('₹9,00,71,99,25,47,409.93');
  });

  it.each([
    ['0.01', 1], ['1', 100], ['1.2', 120], ['0001.02', 102],
    ['90071992547409.91', Number.MAX_SAFE_INTEGER],
  ])('parses %s without floating-point rounding', (input, expected) => {
    expect(paise(input)).toBe(expected);
    expect(Number.isSafeInteger(paise(input))).toBe(true);
  });

  it.each([
    '', ' ', ' 1', '1 ', '.01', '1.', '1.234', '1e3', '-1', '+1',
    '0', '0.00', 'NaN', 'Infinity', '1,000', '9007199254740992',
    '90071992547409.92',
  ])('rejects malformed, nonpositive or unsafe input %j', input => {
    expect(() => paise(input)).toThrow();
  });

  it.each([undefined, -1, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1, '', '1.5', '-1'])
    ('keeps unavailable or invalid money %j unavailable', value => {
      expect(money(value)).toBe('Unavailable');
    });
});

describe('minimal public record boundary', () => {
  const record = {
    serial: 'SYNTH-X', issue_date: '2026-10-24', institution_name: 'Synthetic A',
    kind: 'NOC', status: 'ISSUED',
  };

  it('accepts only the separate public record allowlist', () => {
    expect(publicRecord(record)).toEqual(record);
    expect(() => publicRecord({ ...record, monitoring_active: true })).toThrow();
    expect(() => publicRecord({ ...record, status: 'VALID' })).toThrow();
  });
});
