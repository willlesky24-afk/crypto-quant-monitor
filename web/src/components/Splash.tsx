import { useEffect, useState } from 'react'
import { Mark } from './Mark'

// Start mark (DEC-V02 Enmienda 1): the scale draws itself and the index
// settles, 800 ms at most, once per browser session. It never waits for data:
// the screens show their own skeletons while they load.
const DURATION_MS = 800
const SEEN_KEY = 'cqm-mark-seen'

function alreadySeen(): boolean {
  try {
    return sessionStorage.getItem(SEEN_KEY) === '1'
  } catch {
    return false // storage blocked: show the mark, it is short
  }
}

export function Splash() {
  const reduce =
    typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const [gone, setGone] = useState(() => reduce || alreadySeen())

  useEffect(() => {
    if (gone) return
    try {
      sessionStorage.setItem(SEEN_KEY, '1')
    } catch {
      // storage blocked: the mark simply shows again next time
    }
    const id = window.setTimeout(() => setGone(true), DURATION_MS)
    return () => window.clearTimeout(id)
  }, [gone])

  if (gone) return null
  return (
    <div className="splash" role="status" aria-label="Abriendo Quant Monitor">
      <Mark size={72} animate />
      <div className="splash-name">Quant Monitor</div>
    </div>
  )
}
