import { useCallback, useEffect, useState } from 'react'
import { api, type Hoy as HoyData } from '../api'
import { CandleChart } from '../components/CandleChart'
import { Panel, Scale } from '../components/Panels'
import { formatPct, formatPrice } from '../lib/format'

export function Hoy({ symbol, interval }: { symbol: string; interval: string }) {
  const [data, setData] = useState<HoyData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setError(null)
    setData(null)
    api
      .hoy(symbol, interval)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      // The intro waits for this signal; an error also ends it so the user sees it.
      .finally(() => window.dispatchEvent(new Event('cqm-ready')))
  }, [symbol, interval])

  useEffect(load, [load])

  if (error)
    return (
      <div className="panel error" role="alert">
        No se pudo cargar el mercado: {error}
        <div>
          <button className="btn" onClick={load}>
            Reintentar
          </button>
        </div>
      </div>
    )
  if (!data) return <div className="panel empty soft">Cargando {symbol}…</div>

  const change = data.change_24h_pct
  const zone = data.zone
  const funding = data.funding
  const closed = new Date(data.last_close_time).toISOString().slice(0, 16).replace('T', ' ')

  return (
    <>
      <header className="market">
        <div>
          <h1>{data.symbol}</h1>
          <div className="price">{formatPrice(data.price)}</div>
        </div>
        <div>
          <div className={`change ${change == null ? '' : change < 0 ? 'down' : 'up'}`}>
            {formatPct(change, 2, true)} <span className="soft">24 h</span>
          </div>
          <div className="source">
            {data.source} · {data.interval} · vela cerrada {closed} UTC
          </div>
        </div>
      </header>

      <div className="grid">
        <Panel title="Precio" className="span-8">
          <CandleChart candles={data.candles} />
        </Panel>

        <div className="span-4 meters">
          <Panel title="Volatilidad" status={data.volatility.status} tone={data.volatility.tone}>
            <div className="figure">
              {data.volatility.percentile == null ? 'N/D' : Math.round(data.volatility.percentile)}
              <span className="soft" style={{ fontSize: 'var(--fs-s)' }}> / 100</span>
            </div>
            <Scale fill={data.volatility.percentile} legend={['0', '100']} />
            <p className="note">
              Percentil frente a su propia historia. ATR {formatPct(data.volatility.atr_pct)} del precio.
            </p>
          </Panel>

          <Panel title="Costo de operar" status={data.cost.status} tone={data.cost.tone}>
            <div className="figure">{formatPct(data.cost.spread_pct, 3)}</div>
            {data.cost.spread_pct != null && <Scale fill={data.cost.percentile} legend={['0', '100']} />}
            <p className="note">
              {data.cost.spread_pct == null
                ? 'Este proveedor no da spread.'
                : 'Percentil del spread frente al movimiento típico.'}
            </p>
          </Panel>

          <Panel title="Zona de valor" status={zone.status}>
            <div className="figure range">
              <span>{formatPrice(zone.val)}</span>
              <span className="soft">a</span>
              <span>{formatPrice(zone.vah)}</span>
            </div>
            <Scale span={zone.span} mark={zone.mark} />
            <p className="note">
              Precio {formatPrice(data.price)}. Rango donde se negoció el 70 % del volumen reciente.
            </p>
          </Panel>

          {funding ? (
            <Panel
              title="Apalancamiento"
              status={funding.error ? 'Sin dato' : (funding.size_percentile ?? 0) >= 80 ? 'Alto' : 'Normal'}
              tone={!funding.error && (funding.size_percentile ?? 0) >= 80 ? 'warn' : ''}
            >
              <div className="figure">{funding.error ? 'N/D' : formatPct(funding.rate_pct, 4, true)}</div>
              <p className="note">
                {funding.error
                  ? funding.error
                  : `Funding de ${funding.provider}; mayor que el ${Math.round(funding.size_percentile ?? 0)} % de ${funding.records} registros.`}
              </p>
            </Panel>
          ) : (
            <Panel title="Régimen">
              <div className="figure" style={{ fontSize: 'var(--fs-l)' }}>
                {data.regime}
              </div>
            </Panel>
          )}
        </div>

      </div>
      <div className="grid lower">
        <section className="reading span-8" aria-labelledby="en-palabras">
          <h2 id="en-palabras">En palabras</h2>
          {data.summary.map((line) => (
            <p key={line}>{withMinus(line)}</p>
          ))}
          <p className="state">
            <span className="state-label">Estado</span>
            <span>{data.conditions.text}</span>
          </p>
          <p className="footnote">Descripción del mercado, no una recomendación de operar.</p>
        </section>
        <aside className="sources span-4" aria-labelledby="fuentes">
          <h2 id="fuentes">Fuentes y método</h2>
          <dl>
            <dt>Precio y velas</dt>
            <dd>
              {data.source} · {data.interval} · solo velas cerradas
            </dd>
            <dt>Volatilidad y costo</dt>
            <dd>Percentil frente a las últimas 300 velas del mismo mercado</dd>
            <dt>Zona de valor</dt>
            <dd>Perfil de volumen de las últimas 300 velas (70 % del volumen)</dd>
            {funding && !funding.error && (
              <>
                <dt>Apalancamiento</dt>
                <dd>Funding de {funding.provider}, últimos {funding.records} registros</dd>
              </>
            )}
          </dl>
        </aside>
      </div>
    </>
  )
}

// The engine writes ASCII hyphens; the interface shows the real minus sign.
function withMinus(text: string): string {
  return text.replace(/(^|[\s(])-(\d)/g, '$1−$2')
}
