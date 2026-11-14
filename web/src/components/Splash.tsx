import { useEffect, useState } from 'react'

// Intro shown on each page load: bars rise, shrink to the centre, and a BTC coin
// spins until the first data arrives. Skipped entirely with reduced motion.
const BARS = [38, 62, 48, 80, 56, 92, 70, 100, 64, 84]
const MIN_MS = 2600

export function Splash({ ready }: { ready: boolean }) {
  const reduce =
    typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const [minDone, setMinDone] = useState(false)
  const [gone, setGone] = useState(false)

  useEffect(() => {
    const id = window.setTimeout(() => setMinDone(true), MIN_MS)
    return () => window.clearTimeout(id)
  }, [])

  const leaving = ready && minDone
  useEffect(() => {
    if (!leaving) return
    const id = window.setTimeout(() => setGone(true), 500)
    return () => window.clearTimeout(id)
  }, [leaving])

  if (gone || reduce) return null
  return (
    <div className={`splash${leaving ? ' leaving' : ''}`} role="status" aria-label="Cargando Quant Monitor">
      <div className="splash-bars" aria-hidden="true">
        {BARS.map((h, i) => (
          <span key={i} style={{ height: `${h}%`, animationDelay: `${i * 60}ms` }} />
        ))}
      </div>
      <div className="coin" aria-hidden="true">
        <div className="coin-face">₿</div>
      </div>
      <div className="splash-name">
        Quant Monitor
        <small>{ready ? 'Listo' : 'Leyendo el mercado…'}</small>
      </div>
    </div>
  )
}
