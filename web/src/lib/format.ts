// Same rule as format_price in src/daily_summary.py, so both interfaces
// show prices identically: two decimals at 100 and above, five below.
export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'N/D'
  if (value >= 100) {
    return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
  return value.toFixed(5)
}

export function formatPct(value: number | null | undefined, digits = 2, signed = false): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'N/D'
  // Real minus sign (U+2212): a hyphen reads as a dash next to digits.
  const text = Math.abs(value).toFixed(digits)
  const sign = value < 0 ? '−' : signed && value > 0 ? '+' : ''
  return `${sign}${text} %`
}
