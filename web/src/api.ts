// Types mirror src/market_service.py::today_payload. Numbers may be null:
// a missing value is shown as N/D, never replaced by zero.
export type Level = { status: string; tone: '' | 'warn' | 'good' }
export type Candle = { time: number; open: number; high: number; low: number; close: number; volume?: number | null }

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

export type Trade = {
  id: number
  symbol: string
  side: 'LONG' | 'SHORT'
  entry: number
  stop: number
  units: number
  risk_usd: number
  costs_usd: number
  reason: string
  outside_rules: boolean
  opened_at: string
  exit: number | null
  closed_at: string | null
  moved_stop: boolean | null
  size_respected: boolean | null
  pnl_usd: number | null
  r: number | null
  followed_plan: boolean | null
  status: 'abierta' | 'cerrada'
}
export type Summary = {
  closed: number
  mean_r: number | null
  plan_pct: number | null
  costs_usd: number | null
  pnl_usd: number | null
  worst_streak: number | null
  r_in_plan: number | null
  r_off_plan: number | null
}
export type Rules = Partial<Record<'capital' | 'max_daily_loss_pct' | 'max_weekly_loss_pct' | 'max_open_risk_pct' | 'pause_after_losses', number>>
export type Journal = { trades: Trade[]; semana: Summary; mes: Summary; total: Summary; rules: Rules; breaches: string[] }
export type PlanBody = {
  symbol: string
  side: string
  entry: number
  stop: number
  units: number
  risk_usd: number
  costs_usd: number
  reason: string
  acknowledged?: boolean
}

export type CopilotAnswer = { text: string; used_ai: boolean; ai_error: string | null }

export type Rule = { entry: string; side: string; sl_atr: number; tp_atr: number; max_bars: number }

export type RadarAlert = { market: string; measure: string; text: string }
export type Radar = {
  interval: string
  tests: number
  alpha: number | null
  alerts: RadarAlert[]
  failed: Record<string, string>
}

export type Session = { authenticated: boolean; configured: boolean }

async function call<T>(path: string, body?: unknown, method?: string): Promise<T> {
  const r = await fetch(path, {
    method: method ?? (body === undefined ? 'GET' : 'POST'),
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await r.json().catch(() => ({}))
  if (r.status === 401 && path !== '/api/v1/sesion') window.dispatchEvent(new Event('cqm-logout'))
  if (!r.ok) {
    const raw = data.detail
    const detail = Array.isArray(raw)
      ? raw.map((d: { msg: string }) => d.msg).join('; ')
      : raw && typeof raw === 'object' && Array.isArray(raw.breaches)
        ? raw.breaches.join(' ')
        : raw
    throw Object.assign(new Error(detail ?? `Error ${r.status}`), { status: r.status, data: raw })
  }
  return data as T
}

export const api = {
  sesion: () => call<Session>('/api/v1/sesion'),
  entrar: (password: string) => call<Session>('/api/v1/sesion', { password }),
  salir: () => call<Session>('/api/v1/sesion', undefined, 'DELETE'),
  hoy: (symbol: string, interval: string) =>
    call<Hoy>(`/api/v1/hoy?symbol=${encodeURIComponent(symbol)}&interval=${interval}`),
  mercados: () => call<Markets>('/api/v1/mercados'),
  riesgo: (body: Record<string, unknown>) => call<RiskPlan>('/api/v1/riesgo', body),
  metodos: () => call<{ methods: Method[]; entries: string[] }>('/api/v1/metodos'),
  verificar: (body: Record<string, unknown>) => call<Verdict>('/api/v1/verificar', body),
  interpretar: (text: string) => call<Rule | { no_cabe: string }>('/api/v1/interpretar', { text }),
  explicar: (result: Verdict) => call<{ text: string; used_ai: boolean }>('/api/v1/explicar', { result }),
  diario: () => call<Journal>('/api/v1/diario'),
  guardarPlan: (body: PlanBody) => call<Trade>('/api/v1/diario', body),
  cerrar: (id: number, body: { exit: number; moved_stop: boolean; size_respected: boolean }) =>
    call<Trade>(`/api/v1/diario/${id}/cerrar`, body),
  reglas: (body: Record<string, number | null>) => call<Rules>('/api/v1/diario/reglas', body, 'PUT'),
  reservado: (body: Record<string, unknown>) => call<Verdict>('/api/v1/verificar/reservado', body),
  copiloto: (body: { symbol: string; interval: string; question: string; history: { role: string; text: string }[] }) =>
    call<CopilotAnswer>('/api/v1/copiloto', body),
  radar: (interval: string) => call<Radar>(`/api/v1/radar?interval=${interval}`),
}
