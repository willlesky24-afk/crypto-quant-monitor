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
            <Choice
              label="Lado"
              value={side}
              onChange={setSide}
              options={
                marginMarket
                  ? [
                      { value: 'LONG', label: 'Comprar' },
                      { value: 'SHORT', label: 'Vender (corto)' },
                    ]
                  : [{ value: 'LONG', label: 'Comprar' }]
              }
            />
          </Field>
        </section>

        <section className="span-8" aria-live="polite">
          {error && (
            <div className="panel error" role="alert">
              No se puede calcular: {error}
            </div>
          )}
          {!plan && !error && <div className="panel empty soft">Calculando…</div>}
          {plan && (
            <>
              <div className="panel stats">
                <Stat title="Tamaño" value={plan.units.toLocaleString('en-US', { maximumFractionDigits: 4 })} note="Unidades del activo." />
                <Stat title="Valor de la posición" value={money(plan.notional)} note={`De un capital de ${money(capital)}.`} />
                <Stat title="Pérdida si toca el stop" value={money(plan.max_loss)} note="Incluye los costos." />
                <Stat title="Costos incluidos" value={money(plan.costs)} note={plan.spread_included ? 'Spread y comisión.' : 'Comisión; el proveedor no da spread.'} />
              </div>
              <dl className="facts">
                <dt>Entrada</dt>
                <dd className="mono">{formatPrice(plan.entry_price)}</dd>
                <dt>Stop</dt>
                <dd className="mono">
                  {formatPrice(plan.stop_price)} ({formatPct(plan.stop_distance_pct)} de la entrada)
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
            </>
          )}
        </section>
      </div>
    </>
  )
}
