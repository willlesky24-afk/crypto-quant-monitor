import { useEffect, useState } from 'react'
import { api, type RiskPlan } from '../api'
import { Choice, Field, NumberInput, Stat } from '../components/Fields'
import { formatPct, formatPrice } from '../lib/format'

const money = (v: number) =>
  `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export function Riesgo({ symbol, interval }: { symbol: string; interval: string }) {
  const marginMarket = symbol.endsWith('=X')
  const [capital, setCapital] = useState(1000)
  const [riskPct, setRiskPct] = useState(1)
  const [side, setSide] = useState<'LONG' | 'SHORT'>('LONG')
  const [atrMultiple, setAtrMultiple] = useState(2)
  const [plan, setPlan] = useState<RiskPlan | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [breaches, setBreaches] = useState<string[]>([])
  const [reason, setReason] = useState('')
  const [ack, setAck] = useState(false)
  const [saveNote, setSaveNote] = useState<string | null>(null)

  const refreshBreaches = () =>
    api
      .diario()
      .then((d) => setBreaches(d.breaches))
      .catch(() => setBreaches([]))
  useEffect(() => {
    refreshBreaches()
  }, [])

  const save = () => {
    if (!plan) return
    setSaveNote(null)
    api
      .guardarPlan({
        symbol,
        side,
        entry: plan.entry_price,
        stop: plan.stop_price,
        units: plan.units,
        risk_usd: plan.max_loss,
        costs_usd: plan.costs,
        reason,
        acknowledged: ack,
      })
      .then(() => {
        setSaveNote('Guardado en tu diario como operación abierta.')
        setReason('')
        setAck(false)
        refreshBreaches()
      })
      .catch((e: Error) => setSaveNote(e.message))
  }

  useEffect(() => {
    if (!marginMarket) setSide('LONG')
  }, [marginMarket])

  useEffect(() => {
    const id = window.setTimeout(() => {
      setError(null)
      api
        .riesgo({ symbol, interval, capital, risk_pct: riskPct, side, atr_multiple: atrMultiple })
        .then(setPlan)
        .catch((e: Error) => {
          setPlan(null)
          setError(e.message)
        })
    }, 350)
    return () => window.clearTimeout(id)
  }, [symbol, interval, capital, riskPct, side, atrMultiple])

  return (
    <>
      <header className="screen-head">
        <h1>¿Cuánto puedo operar sin arriesgar de más?</h1>
        <p className="soft">
          Elige cuánto aceptas perder y calculamos el tamaño en {symbol}. Es información de tamaño, no una
          recomendación de entrar. Cuenta en USD, sin apalancamiento.
        </p>
      </header>

      {breaches.length > 0 && (
        <div className="breach" role="alert">
          <b>Estás fuera de tus reglas</b>
          {breaches.map((b) => (
            <p key={b}>{b}</p>
          ))}
        </div>
      )}

      <div className="grid">
        <section className="panel span-4 form" aria-label="Datos">
          <Field label="Capital de tu cuenta (USD)">
            <NumberInput value={capital} onChange={setCapital} step={100} min={0} />
          </Field>
          <Field label="Parte del capital que aceptas perder (%)" hint="Muchos traders usan entre 0.5 y 2 %.">
            <NumberInput value={riskPct} onChange={setRiskPct} step={0.25} min={0} max={100} />
          </Field>
          <Field label="Distancia del stop (en ATR)" hint="El ATR es el movimiento típico por vela.">
            <NumberInput value={atrMultiple} onChange={setAtrMultiple} step={0.25} min={0} />
          </Field>
          <Field label="Tu idea">
            {marginMarket ? (
              <Choice
                label="Lado"
                value={side}
                onChange={setSide}
                options={[
                  { value: 'LONG', label: 'Comprar' },
                  { value: 'SHORT', label: 'Vender (corto)' },
                ]}
              />
            ) : (
              <span className="field-hint">Solo compra: en cripto al contado no se vende en corto.</span>
            )}
          </Field>
        </section>

        <section className="panel span-8 result" aria-live="polite">
          {error && (
            <div className="error" role="alert">
              No se puede calcular: {error}
            </div>
          )}
          {!plan && !error && <div className="empty soft">Calculando…</div>}
          {plan && (
            <>
              <div className="panel-title">Pérdida si toca el stop</div>
              <div className="hero-figure">{money(plan.max_loss)}</div>
              <div className="scale" aria-hidden="true">
                <div className="fill" style={{ left: 0, width: `${Math.min(100, (plan.max_loss / capital) * 100 * 20)}%` }} />
              </div>
              <div className="scale-legend">
                <span>{formatPct((plan.max_loss / capital) * 100)} de tu capital</span>
                <span>5 %</span>
              </div>
              <div className="stats three">
                <Stat title="Tamaño" value={plan.units.toLocaleString('en-US', { maximumFractionDigits: 4 })} note="Unidades del activo." />
                <Stat title="Valor de la posición" value={money(plan.notional)} note={`De un capital de ${money(capital)}.`} />
                <Stat title="Costos incluidos" value={money(plan.costs)} note={plan.spread_included ? 'Spread y comisión.' : 'Comisión; el proveedor no da spread.'} />
              </div>
              <dl className="facts">
                <dt>Entrada</dt>
                <dd className="mono">{formatPrice(plan.entry_price)}</dd>
                <dt>Stop</dt>
                <dd className="mono">
                  {formatPrice(plan.stop_price)}
                  <span className="soft"> · {formatPct(plan.stop_distance_pct)} {side === 'SHORT' ? 'sobre' : 'bajo'} la entrada</span>
                </dd>
                <dt>Comisión por lado</dt>
                <dd className="mono">{formatPct(plan.fee_pct, 3)}</dd>
              </dl>
              {plan.limited_by_capital && (
                <p className="callout">
                  Tu capital no alcanza para arriesgar ese porcentaje sin apalancamiento. El tamaño se limitó a tu
                  capital y arriesgas menos.
                </p>
              )}
              <p className="footnote">El stop no es una garantía: con un salto de precio la pérdida puede ser mayor.</p>
              <div className="save-plan">
                <Field label="Motivo de la operación" hint="Lo revisarás después: escribe por qué entras.">
                  <textarea className="input" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
                </Field>
                {breaches.length > 0 && (
                  <label className="check">
                    <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /> Entiendo que estoy
                    fuera de mis reglas (quedará registrado)
                  </label>
                )}
                <button
                  className="btn"
                  type="button"
                  onClick={save}
                  disabled={reason.trim().length === 0 || (breaches.length > 0 && !ack)}
                >
                  Guardar en mi diario
                </button>
                {saveNote && <p className="note">{saveNote}</p>}
              </div>
            </>
          )}
        </section>
      </div>
    </>
  )
}
