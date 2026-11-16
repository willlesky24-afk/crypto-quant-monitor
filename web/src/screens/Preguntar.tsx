import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, type CopilotAnswer } from '../api'

type Turn = { role: 'user' | 'assistant'; text: string; usedAi?: boolean; aiError?: string | null }

const SUGGESTIONS = [
  '¿Cómo está el mercado ahora?',
  '¿Está caro operar en este momento?',
  '¿Qué significa que el precio esté debajo de la zona de valor?',
  '¿Qué me dice la volatilidad?',
]

export function Preguntar({ symbol, interval }: { symbol: string; interval: string }) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)

  // A new market starts a new conversation: answers about another market would mislead.
  useEffect(() => {
    setTurns([])
  }, [symbol, interval])
  useEffect(() => {
    end.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [turns])

  const ask = (text: string) => {
    const q = text.trim()
    if (q.length < 2 || busy) return
    const history = turns.map((t) => ({ role: t.role, text: t.text }))
    setTurns((prev) => [...prev, { role: 'user', text: q }])
    setQuestion('')
    setBusy(true)
    api
      .copiloto({ symbol, interval, question: q, history })
      .then((a: CopilotAnswer) =>
        setTurns((prev) => [...prev, { role: 'assistant', text: a.text, usedAi: a.used_ai, aiError: a.ai_error }]),
      )
      .catch((e: Error) =>
        setTurns((prev) => [...prev, { role: 'assistant', text: `No se pudo responder: ${e.message}`, usedAi: false }]),
      )
      .finally(() => setBusy(false))
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    ask(question)
  }

  return (
    <>
      <header className="screen-head">
        <h1>Pregúntale al mercado</h1>
        <p className="soft">
          Conversa sobre {symbol} en {interval}. La IA solo puede usar las cifras del motor; si inventa una o
          aconseja comprar o vender, se descarta y ves los datos tal cual. No da recomendaciones.
        </p>
      </header>

      <section className="chat" aria-live="polite">
        {turns.length === 0 && (
          <div className="suggest">
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" className="btn quiet" onClick={() => ask(s)}>
                {s}
              </button>
            ))}
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className={`turn ${t.role}`}>
            {t.role === 'assistant' && t.usedAi === false && (
              <span className="tag">
                {t.aiError ? `IA no disponible: ${t.aiError}` : 'La IA no pasó el control de cifras: datos del motor'}
              </span>
            )}
            <p>{t.text}</p>
          </div>
        ))}
        {busy && <p className="note">Pensando con los datos de {symbol}…</p>}
        <div ref={end} />
      </section>

      <form className="ask" onSubmit={submit}>
        <input
          className="input"
          placeholder="Escribe tu pregunta"
          value={question}
          maxLength={500}
          onChange={(e) => setQuestion(e.target.value)}
          aria-label="Tu pregunta"
        />
        <button className="btn" type="submit" disabled={busy}>
          Preguntar
        </button>
      </form>
      <p className="footnote">Descripción del mercado, no una recomendación de operar.</p>
    </>
  )
}
