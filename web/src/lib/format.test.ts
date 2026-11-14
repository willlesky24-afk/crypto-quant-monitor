import { describe, expect, it } from 'vitest'
import { formatPct, formatPrice } from './format'

// Expected strings mirror tests/unit/test_daily_summary.py::test_format_price.
describe('formatPrice', () => {
  it('uses two decimals from 100 up and five below', () => {
    expect(formatPrice(103)).toBe('103.00')
    expect(formatPrice(1.08123)).toBe('1.08123')
    expect(formatPrice(67682.01)).toBe('67,682.01')
  })
  it('shows a missing value as N/D, never zero', () => {
    expect(formatPrice(null)).toBe('N/D')
    expect(formatPrice(Number.NaN)).toBe('N/D')
  })
})

describe('formatPct', () => {
  it('signs gains only when asked', () => {
    expect(formatPct(3, 2, true)).toBe('+3.00 %')
    expect(formatPct(-3.659, 2, true)).toBe('−3.66 %')
    expect(formatPct(undefined)).toBe('N/D')
  })
})
