import { useState } from 'react'
import { api, type Radar as RadarData } from '../api'

const MEASURE: Record<string, string> = {
  compresion: 'Compresión',
  fuerza_relativa: 'Fuerza relativa',
  correlacion: 'Correlación',
  explosividad: 'Explosividad',
}

export function Radar({ interval }: { interval: string }) {
  const [data, setData] = useState<RadarData | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const scan = () => {
    setBusy(true)
    setError(null)
    api
      .radar(interval)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setBusy(false))
  }

  return (
    <>
      <header className="screen-head">
        <h1>¿Qué está fuera de lo normal?</h1>
        <p className="soft">
          Compara criptos, forex, metales e índices con su propia historia en {interval}. Un aviso dice que algo es
          raro, no qué hacer. Mientras más mercados se revisan, más exigente es el listón.
        </p>
      </header>

      <button className="btn" onClick={scan} disabled={busy} type="button">
        {busy ? 'Revisando mercados… puede tardar un minuto' : 'Escanear mercados'}
      </button>

      <section aria-live="polite" className="radar">
        {error && (
          <div className="panel error" role="alert">
            No se pudo escanear: {error}
          </div>
        )}
        {data && (
          <>
            <p className="soft">
              {data.alpha == null
                ? 'Ningún mercado tiene historia suficiente para medir.'
                : `Se hicieron ${data.tests} mediciones; solo se avisa lo que esté en el ${(data.alpha * 100).toFixed(2)} % más extremo.`}
            </p>
            {data.alerts.length === 0 && data.alpha != null && (
              <p className="callout">Nada fuera de lo normal en este momento.</p>
            )}
            <ul className="alerts">
              {data.alerts.map((a) => (
                <li key={`${a.market}-${a.measure}`}>
                  <div className="alert-head">
                    <span className="mono">{a.market}</span>
                    <span className="tag">{MEASURE[a.measure] ?? a.measure}</span>
                  </div>
                  <p>{a.text}</p>
                </li>
              ))}
            </ul>
            {Object.keys(data.failed).length > 0 && (
              <dl className="facts failed">
                {Object.entries(data.failed).map(([market, reason]) => (
                  <div key={market}>
                    <dt>{market} no se pudo revisar</dt>
                    <dd>{reason}</dd>
                  </div>
                ))}
              </dl>
            )}
          </>
        )}
      </section>
    </>
  )
}
