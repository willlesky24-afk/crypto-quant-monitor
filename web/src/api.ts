// Types mirror src/market_service.py::today_payload. Numbers may be null:
// a missing value is shown as N/D, never replaced by zero.
export type Level = { status: string; tone: '' | 'warn' | 'good' }
export type Candle = { time: number; open: number; high: number; low: number; close: number }

export type Hoy = {
  symbol: string
  interval: string
  source: string
  last_close_time: string
  price: number
  change_24h_pct: number | null
  regime: string
  volatility: Level & { percentile: number | null; atr_pct: number }
  cost: Level & { spread_pct: number | null; percentile: number | null }
  zone: { val: number; vah: number; poc: number; status: string; span: [number, number] | null; mark: number | null }
  funding: null | { error?: string; provider?: string; rate_pct?: number; size_percentile?: number; records?: number }
  summary: string[]
  conditions: { level: 'VERDE' | 'AMARILLO' | 'ROJO' | 'NO_DISPONIBLE'; text: string }
  candles: Candle[]
}

export type Market = { symbol: string; label: string }
export type Markets = { crypto: Market[]; other: Market[]; other_error: string | null; intervals: string[] }

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path)
  const body = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(body.detail ?? `Error ${r.status}`)
  return body as T
}

export const api = {
  hoy: (symbol: string, interval: string) =>
    get<Hoy>(`/api/v1/hoy?symbol=${encodeURIComponent(symbol)}&interval=${interval}`),
  mercados: () => get<Markets>('/api/v1/mercados'),
}
