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
  const [scannedAt, setScannedAt] = useState('')

  const scan = () => {
    setBusy(true)
    setError(null)
    api
      .radar(interval)
      .then((d) => {
        setData(d)
        setScannedAt(new Date().toISOString().slice(11, 16) + ' UTC')
      })
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
            <div className="panel stats readout">
              <div className="stat">
                <div className="panel-title">Lectura</div>
                <div className="figure">{data.alerts.length === 0 ? 'Sin avisos' : `${data.alerts.length} aviso${data.alerts.length > 1 ? 's' : ''}`}</div>
                <p className="note">{data.alerts.length === 0 ? 'Nada fuera de lo normal en este momento.' : 'Cada aviso muestra qué pasó en casos parecidos.'}</p>
              </div>
              <div className="stat">
                <div className="panel-title">Mediciones</div>
                <div className="figure">{data.tests}</div>
                <p className="note">Compresión, fuerza relativa, correlación y explosividad.</p>
              </div>
              <div className="stat">
                <div className="panel-title">Listón</div>
                <div className="figure">{data.alpha == null ? 'N/D' : `${(data.alpha * 100).toFixed(2)} %`}</div>
                <p className="note">Solo se avisa lo más extremo; sube con cada medición.</p>
              </div>
              <div className="stat">
                <div className="panel-title">Escaneado</div>
                <div className="figure">{scannedAt}</div>
                <p className="note">Velas de {data.interval}.</p>
              </div>
            </div>
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
              <details className="failures">
                <summary>
                  {Object.keys(data.failed).length === 1
                    ? '1 mercado sin datos en este escaneo'
                    : `${Object.keys(data.failed).length} mercados sin datos en este escaneo`}
                  : {Object.keys(data.failed).join(', ')}
                </summary>
                <dl className="facts">
                  {Object.entries(data.failed).map(([market, reason]) => (
                    <div key={market}>
                      <dt>{market}</dt>
                      <dd>El proveedor no respondió. Detalle técnico: {reason}</dd>
                    </div>
                  ))}
                </dl>
              </details>
            )}
          </>
        )}
      </section>
    </>
  )
}
