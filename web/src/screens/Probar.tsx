import { useEffect, useState } from 'react'
import { api, type Method, type Verdict } from '../api'
import { Choice, Field, NumberInput, Stat } from '../components/Fields'
import { Scale } from '../components/Panels'
import { formatPrice } from '../lib/format'

const ENTRY_LABELS: Record<string, string> = {
  trend_ema: 'Tendencia (precio y medias 50/200 alineados)',
  momentum_rsi: 'Momentum RSI',
  volume_direction: 'Volumen alto con vela a favor',
  profile_value_area: 'Precio fuera de la zona de valor',
  donchian_20: 'Ruptura del canal de 20 velas',
  tsmom_180: 'Dirección de las últimas 180 velas',
  bollinger_20_2: 'Reversión desde bandas de Bollinger',
  reversion_rsi: 'Reversión RSI',
}

const VERDICT_TITLE: Record<Verdict['code'], string> = {
  POCAS_OPERACIONES: 'Pocas operaciones',
  PIERDE: 'Pierde después de costos',
  NO_SE_DISTINGUE: 'No se distingue del azar',
  MERECE_ESTUDIO: 'Merece más estudio',
}

const r = (v: number | null | undefined) =>
  v == null ? 'N/D' : `${v < 0 ? '−' : '+'}${Math.abs(v).toFixed(3)}`

export function Probar({ symbol, interval }: { symbol: string; interval: string }) {
  const marginMarket = symbol.endsWith('=X')
  const [methods, setMethods] = useState<Method[]>([])
  const [entries, setEntries] = useState<string[]>([])
  const [entry, setEntry] = useState('trend_ema')
  const [side, setSide] = useState('LONG')
  const [sl, setSl] = useState(2)
  const [tp, setTp] = useState(6)
  const [bars, setBars] = useState(120)
  const [capital, setCapital] = useState(1000)
  const [riskPct, setRiskPct] = useState(1)
  const [holdout, setHoldout] = useState<Verdict | null>(null)
  const [holdoutBusy, setHoldoutBusy] = useState(false)
  const [idea, setIdea] = useState('')
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<Verdict | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [explanation, setExplanation] = useState<{ text: string; used_ai: boolean } | null>(null)

  useEffect(() => {
    api.metodos().then((m) => {
      setMethods(m.methods)
      setEntries(m.entries)
    })
  }, [])

  useEffect(() => {
    if (!marginMarket) setSide('LONG')
  }, [marginMarket])

  const loadMethod = (m: Method) => {
    setEntry(m.entry)
    setSide('LONG')
    setSl(m.sl_atr)
    setTp(m.tp_atr)
    setBars(m.max_bars)
    setNote(`Regla cargada: ${m.name}. Revisa los valores antes de verificar.`)
  }

  const interpret = () => {
    setNote('Interpretando…')
    api
      .interpretar(idea)
      .then((rule) => {
        if ('no_cabe' in rule) return setNote(`Esa idea no cabe en las reglas: ${rule.no_cabe}`)
        if (!marginMarket && rule.side !== 'LONG') return setNote('En cripto spot solo se puede probar en largo.')
        setEntry(rule.entry)
        setSide(rule.side)
        setSl(rule.sl_atr)
        setTp(rule.tp_atr)
        setBars(rule.max_bars)
        setNote('La IA propuso esta regla. Revísala antes de verificar.')
      })
      .catch((e: Error) => setNote(`No se pudo interpretar: ${e.message}`))
  }

  const verify = () => {
    setBusy(true)
    setError(null)
    setResult(null)
    setExplanation(null)
    setHoldout(null)
    api
      .verificar({ symbol, interval, entry, side, sl_atr: sl, tp_atr: tp, max_bars: bars, capital, risk_pct: riskPct })
      .then((v) => {
        setResult(v)
        window.setTimeout(() => document.querySelector('.verdict')?.scrollIntoView({ behavior: 'smooth' }), 50)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setBusy(false))
  }

  const confirm = () => {
    setHoldoutBusy(true)
    setError(null)
    api
      .reservado({ symbol, interval, entry, side, sl_atr: sl, tp_atr: tp, max_bars: bars, capital, risk_pct: riskPct })
      .then(setHoldout)
      .catch((e: Error) => setError(e.message))
      .finally(() => setHoldoutBusy(false))
  }

  const explain = () => {
    if (!result) return
    setExplanation({ text: 'Pidiendo la explicación…', used_ai: true })
    api
      .explicar(result)
      .then(setExplanation)
      .catch((e: Error) => setExplanation({ text: `La IA no está disponible: ${e.message}`, used_ai: false }))
  }

  return (
    <>
      <header className="screen-head">
        <h1>¿Tu regla resiste los datos?</h1>
        <p className="soft">
          Prueba una regla en {symbol} {interval} con costos reales y contra entradas al azar. Reservamos el último 20 % de los
          datos y cada intento sube el listón.
        </p>
      </header>

      <div className="grid">
        <section className="span-7">
          <h2 className="section-title">Elige un método</h2>
          <ul className="methods">
            {methods.map((m) => (
              <li key={m.entry}>
                <button className="method" aria-pressed={entry === m.entry} onClick={() => loadMethod(m)} type="button">
                  <span className="method-name">{m.name}</span>
                  <span className="note">
                    {m.idea} Sufre cuando {m.suffers}
                  </span>
                </button>
              </li>
            ))}
          </ul>

          <h2 className="section-title">O descríbela con tus palabras</h2>
          <div className="idea">
            <textarea
              className="input"
              rows={3}
              placeholder="Quiero entrar cuando rompa el máximo de 20 velas, con stop amplio"
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
            />
            <button className="btn ghost" onClick={interpret} disabled={idea.trim().length < 3} type="button">
              Interpretar con IA
            </button>
          </div>
          {note && <p className="note">{note}</p>}
        </section>

        <section className="panel span-5 form" aria-label="Regla">
          <Field label="Regla de entrada">
            <select className="select" value={entry} onChange={(e) => setEntry(e.target.value)}>
              {entries.map((e) => (
                <option key={e} value={e}>
                  {ENTRY_LABELS[e] ?? e}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Lado">
            {marginMarket ? (
              <Choice
                label="Lado"
                value={side}
                onChange={setSide}
                options={[
                  { value: 'AMBOS', label: 'Ambos' },
                  { value: 'LONG', label: 'Compras' },
                  { value: 'SHORT', label: 'Ventas' },
                ]}
              />
            ) : (
              <span className="field-hint">Solo compras: en cripto al contado no se vende en corto.</span>
            )}
          </Field>
          <div className="row3">
            <Field label="Stop (ATR)">
              <NumberInput value={sl} onChange={setSl} step={0.5} min={0.5} />
            </Field>
            <Field label="Objetivo (ATR)">
              <NumberInput value={tp} onChange={setTp} step={0.5} min={0.5} />
            </Field>
            <Field label="Máx. velas">
              <NumberInput value={bars} onChange={setBars} step={10} min={1} />
            </Field>
          </div>
          <div className="row3">
            <Field label="Capital de ejemplo">
              <NumberInput value={capital} onChange={setCapital} step={100} min={10} />
            </Field>
            <Field label="Riesgo por operación (%)">
              <NumberInput value={riskPct} onChange={setRiskPct} step={0.25} min={0.1} max={100} />
            </Field>
          </div>
          <button className="btn" onClick={verify} disabled={busy} type="button">
            {busy ? 'Probando contra el azar…' : 'Verificar regla'}
          </button>
          {busy && <p className="note">El resultado aparecerá debajo. Se comparan cientos de entradas al azar: puede tardar 1 a 3 minutos en 1h.</p>}
          {result && !busy && (
            <p className="note">
              Último resultado: <b>{VERDICT_TITLE[result.code]}</b> con {result.trades} operaciones. Está debajo.
            </p>
          )}
        </section>
      </div>

      <section className="verdict" aria-live="polite">
        {error && (
          <div className="panel error" role="alert">
            No se puede probar: {error}
          </div>
        )}
        {result && (
          <>
            <h2 className="verdict-title">{VERDICT_TITLE[result.code]}</h2>
            <p>{result.text}</p>
            <p className="story">{result.story}</p>
            <div className="panel stats">
              <Stat title="Operaciones" value={String(result.trades)} note="Mínimo para concluir: 100." />
              <Stat title="R neta media" value={r(result.mean_r)} note="Ganancia media por unidad de riesgo." />
              <Stat
                title="Azar igual o mejor"
                value={result.p_random == null ? 'N/D' : `${(Number(result.p_random) * 100).toFixed(1)} %`}
                note={`De ${result.random_runs ?? 'N/D'} corridas al azar con tus mismas salidas.`}
              />
              <Stat title="Intento" value={String(result.attempts)} note="Cada intento exige más." />
            </div>
            {result.ci && result.mean_r != null && (() => {
              // Symmetric range around zero, so the centre major tick is exactly 0 R.
              const [lo, hi] = result.ci
              const m = Math.max(Math.abs(lo), Math.abs(hi), Math.abs(result.mean_r)) * 1.25
              const pos = (v: number) => 50 + (v / m) * 50
              return (
                <div className="ci-scale">
                  <div className="panel-title">Dónde cae la R media (marca central = 0)</div>
                  <Scale span={[pos(lo), pos(hi)]} mark={pos(result.mean_r)} legend={[`−${m.toFixed(2)} R`, `+${m.toFixed(2)} R`]} />
                  <p className="note">
                    {lo <= 0 && hi >= 0
                      ? 'El tramo bronce cruza el cero: con estos datos no se puede descartar que la ventaja sea nula.'
                      : hi < 0
                        ? 'Todo el tramo queda bajo cero: pierde con margen.'
                        : 'Todo el tramo queda sobre cero.'}
                    {result.code === 'NO_SE_DISTINGUE' && result.p_random != null && Number(result.p_random) < 0.05 &&
                      ' Superó a casi todas las entradas al azar, pero eso no basta: el intervalo también debe quedar sobre cero.'}
                  </p>
                </div>
              )
            })()}
            <dl className="facts">
              <dt>Intervalo de la R media</dt>
              <dd className="mono">{result.ci ? `${r(result.ci[0])} a ${r(result.ci[1])}` : 'N/D'}</dd>
              <dt>Ventaja mínima detectable</dt>
              <dd>
                {result.mde_r == null
                  ? 'N/D'
                  : `Con estos datos solo se distinguiría del azar una ventaja mayor a ±${Number(result.mde_r).toFixed(2)} R por operación.`}
              </dd>
              <dt>Datos</dt>
              <dd>{result.data_source}</dd>
              {typeof result.final_capital === 'number' && (
                <>
                  <dt>Capital final en el pasado</dt>
                  <dd className="mono">${formatPrice(result.final_capital as number)}</dd>
                </>
              )}
            </dl>
            {result.holdout_available === true && !holdout && (
              <div className="callout">
                <p>
                  Puedes confirmarla <b>una sola vez</b> con el 20 % de datos reservados, que la regla nunca vio. Después
                  no se puede repetir.
                </p>
                <button className="btn" type="button" onClick={confirm} disabled={holdoutBusy}>
                  {holdoutBusy ? 'Probando con datos reservados…' : 'Confirmar con datos reservados'}
                </button>
              </div>
            )}
            {holdout && (
              <div className="panel holdout">
                <div className="panel-title">Confirmación con datos reservados (única)</div>
                <h3 className="verdict-title">{VERDICT_TITLE[holdout.code]}</h3>
                <p>{holdout.text}</p>
                <p className="note">
                  {holdout.trades} operaciones · R media {r(holdout.mean_r)} · {String(holdout.story ?? '')}
                </p>
              </div>
            )}
            <button className="btn ghost" onClick={explain} type="button">
              Explicar con IA
            </button>
            {explanation && (
              <div className="explanation">
                {!explanation.used_ai && (
                  <span className="tag">La IA no pasó el control de cifras: se muestran los datos del motor</span>
                )}
                <p>{explanation.text}</p>
              </div>
            )}
            <p className="footnote">Resultado histórico, no una recomendación de operar.</p>
          </>
        )}
      </section>
    </>
  )
}
