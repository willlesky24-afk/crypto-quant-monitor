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

export type RiskPlan = {
  entry_price: number
  stop_price: number
  spread_included: boolean
  fee_pct: number
  units: number
  notional: number
  max_loss: number
  costs: number
  stop_distance_pct: number
  limited_by_capital: boolean
}

export type Method = {
  entry: string
  name: string
  idea: string
  suffers: string
  sl_atr: number
  tp_atr: number
  max_bars: number
}

export type Verdict = {
  code: 'POCAS_OPERACIONES' | 'PIERDE' | 'NO_SE_DISTINGUE' | 'MERECE_ESTUDIO'
  text: string
  ci: [number, number] | null
  trades: number
  mean_r: number | null
  random_best: number | null
  attempts: number
  story: string
  data_source: string
  [key: string]: unknown
}

export type Rule = { entry: string; side: string; sl_atr: number; tp_atr: number; max_bars: number }

export type RadarAlert = { market: string; measure: string; text: string }
export type Radar = {
  interval: string
  tests: number
  alpha: number | null
  alerts: RadarAlert[]
  failed: Record<string, string>
}

async function call<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((d: { msg: string }) => d.msg).join('; ') : data.detail
    throw new Error(detail ?? `Error ${r.status}`)
  }
  return data as T
}

export const api = {
  hoy: (symbol: string, interval: string) =>
    call<Hoy>(`/api/v1/hoy?symbol=${encodeURIComponent(symbol)}&interval=${interval}`),
  mercados: () => call<Markets>('/api/v1/mercados'),
  riesgo: (body: Record<string, unknown>) => call<RiskPlan>('/api/v1/riesgo', body),
  metodos: () => call<{ methods: Method[]; entries: string[] }>('/api/v1/metodos'),
  verificar: (body: Record<string, unknown>) => call<Verdict>('/api/v1/verificar', body),
  interpretar: (text: string) => call<Rule | { no_cabe: string }>('/api/v1/interpretar', { text }),
  explicar: (result: Verdict) => call<{ text: string; used_ai: boolean }>('/api/v1/explicar', { result }),
  radar: (interval: string) => call<Radar>(`/api/v1/radar?interval=${interval}`),
}
