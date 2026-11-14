import { useEffect, useState } from 'react'
import { api, type Markets } from './api'
import { Hoy } from './screens/Hoy'
import { Probar } from './screens/Probar'
import { Radar } from './screens/Radar'
import { Riesgo } from './screens/Riesgo'
import { Splash } from './components/Splash'

const SCREENS = [
  { id: 'hoy', label: 'Hoy' },
  { id: 'riesgo', label: 'Mi riesgo' },
  { id: 'probar', label: 'Probar mi idea' },
  { id: 'radar', label: 'Radar' },
] as const
type ScreenId = (typeof SCREENS)[number]['id']

export default function App() {
  const [screen, setScreen] = useState<ScreenId>('hoy')
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [interval, setInterval] = useState('1h')
  const [markets, setMarkets] = useState<Markets | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    api
      .mercados()
      .then(setMarkets)
      .catch(() => setMarkets(null))
  }, [])

  useEffect(() => {
    const done = () => setReady(true)
    window.addEventListener('cqm-ready', done)
    const cap = window.setTimeout(done, 15000) // never trap the user behind the intro
    return () => {
      window.removeEventListener('cqm-ready', done)
      window.clearTimeout(cap)
    }
  }, [])

  return (
    <>
    <Splash ready={ready} />
    <div className="shell">
      <nav className="nav" aria-label="Secciones">
        <div className="brand">
          Quant Monitor
          <small>Antes de arriesgar tu dinero, compruébalo.</small>
        </div>
        <ul>
          {SCREENS.map((s) => (
            <li key={s.id}>
              <button aria-current={screen === s.id ? 'page' : undefined} onClick={() => setScreen(s.id)}>
                {s.label}
              </button>
            </li>
          ))}
        </ul>
        <div className="foot">Sin recomendaciones de inversión.</div>
      </nav>

      <main className="main">
        <div className="topbar">
          <div className="crumb">
            Mercado / <b>{SCREENS.find((s) => s.id === screen)?.label}</b>
          </div>
          <div className="controls">
            {screen !== 'radar' && (
            <select
              className="select"
              aria-label="Mercado"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
            >
              <optgroup label="Cripto">
                {(markets?.crypto ?? [{ symbol: 'BTCUSDT', label: 'BTC / USDT' }]).map((m) => (
                  <option key={m.symbol} value={m.symbol}>
                    {m.label}
                  </option>
                ))}
              </optgroup>
              {markets && markets.other.length > 0 && (
                <optgroup label="Forex, metales e índices">
                  {markets.other.map((m) => (
                    <option key={m.symbol} value={m.symbol}>
                      {m.label}
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
            )}
            <div className="segmented" role="group" aria-label="Temporalidad">
              {(markets?.intervals ?? ['15m', '1h', '4h', '1d']).map((iv) => (
                <button key={iv} aria-pressed={interval === iv} onClick={() => setInterval(iv)}>
                  {iv}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="screen" key={screen}>
        {screen === 'hoy' && <Hoy symbol={symbol} interval={interval} />}
        {screen === 'riesgo' && <Riesgo symbol={symbol} interval={interval} />}
        {screen === 'probar' && <Probar symbol={symbol} interval={interval} />}
        {screen === 'radar' && <Radar interval={interval} />}
        </div>
        <footer className="page-foot">
          Datos de Binance, OANDA y OKX. Gráficos:{' '}
          <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">
            TradingView Lightweight Charts
          </a>
          .
        </footer>
      </main>
    </div>
    </>
  )
}
