import { useCallback, useEffect, useState } from 'react'
import { api, type Journal, type Rules, type Summary, type Trade } from '../api'
import { Field, NumberInput, Stat } from '../components/Fields'
import { formatPrice } from '../lib/format'

const RULES: { key: keyof Rules; label: string; hint: string; step: number }[] = [
  { key: 'capital', label: 'Capital de referencia (USD)', hint: 'Base para los límites en %.', step: 100 },
  { key: 'max_daily_loss_pct', label: 'Pérdida máxima del día (%)', hint: 'Al llegar, para por hoy.', step: 0.5 },
  { key: 'max_weekly_loss_pct', label: 'Pérdida máxima de la semana (%)', hint: 'Desde el lunes (UTC).', step: 0.5 },
  { key: 'max_open_risk_pct', label: 'Riesgo abierto máximo (%)', hint: 'Suma del riesgo de lo abierto.', step: 0.5 },
  { key: 'pause_after_losses', label: 'Pausa tras pérdidas seguidas', hint: 'Número de pérdidas.', step: 1 },
]

const rText = (v: number | null) => (v == null ? 'N/D' : `${v < 0 ? '−' : '+'}${Math.abs(v).toFixed(2)} R`)
const usd = (v: number | null) =>
  v == null ? 'N/D' : `${v < 0 ? '−' : ''}$${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const pct = (v: number | null) => (v == null ? 'N/D' : `${v.toFixed(0)} %`)

function SummaryStats({ title, s }: { title: string; s: Summary }) {
  return (
    <section className="panel" aria-label={title}>
      <div className="panel-title">{title}</div>
      {s.closed === 0 ? (
        <p className="soft">Sin operaciones cerradas.</p>
      ) : (
        <div className="stats three">
          <Stat title="Cerradas" value={String(s.closed)} note={s.worst_streak === 1 ? 'Peor racha: 1 pérdida.' : `Peor racha: ${s.worst_streak ?? 'N/D'} pérdidas.`} />
          <Stat title="R medio" value={rText(s.mean_r)} note={`Resultado: ${usd(s.pnl_usd)}.`} />
          <Stat title="Cumplieron el plan" value={pct(s.plan_pct)} note={`Costos pagados: ${usd(s.costs_usd)}.`} />
        </div>
      )}
      {s.closed > 0 && (
        <p className="note">
          Dentro del plan: {rText(s.r_in_plan)} por operación. Fuera del plan: {rText(s.r_off_plan)}.
        </p>
      )}
    </section>
  )
}

function CloseForm({ trade, onDone }: { trade: Trade; onDone: () => void }) {
  const [exit, setExit] = useState(Number.NaN)
  const [moved, setMoved] = useState(false)
  const [size, setSize] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const submit = () =>
    api
      .cerrar(trade.id, { exit, moved_stop: moved, size_respected: size })
      .then(onDone)
      .catch((e: Error) => setError(e.message))
  return (
    <div className="close-form">
      <Field label="Precio de salida">
        <NumberInput value={exit} onChange={setExit} step={0.01} min={0} />
      </Field>
      <label className="check">
        <input type="checkbox" checked={moved} onChange={(e) => setMoved(e.target.checked)} /> Moví el stop en contra
      </label>
      <label className="check">
        <input type="checkbox" checked={size} onChange={(e) => setSize(e.target.checked)} /> Respeté el tamaño calculado
      </label>
      <button className="btn" type="button" disabled={!(exit > 0)} onClick={submit}>
        Cerrar operación
      </button>
      {error && <p className="error-line">{error}</p>}
    </div>
  )
}

export function Diario() {
  const [data, setData] = useState<Journal | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState<Rules>({})
  const [saved, setSaved] = useState<string | null>(null)

  const load = useCallback(
    () =>
      api
        .diario()
        .then((d) => {
          setData(d)
          setDraft(d.rules)
        })
        .catch((e: Error) => setError(e.message)),
    [],
  )
  useEffect(() => {
    load()
  }, [load])

  const saveRules = () => {
    const body: Record<string, number | null> = {}
    for (const r of RULES) {
      const v = draft[r.key]
      body[r.key] = v != null && Number.isFinite(v) && v > 0 ? v : null
    }
    api
      .reglas(body)
      .then(() => {
        setSaved('Reglas guardadas.')
        load()
      })
      .catch((e: Error) => setSaved(e.message))
  }

  if (error) return <div className="panel error">No se pudo leer el diario: {error}</div>
  if (!data) return <div className="panel empty soft">Leyendo el diario…</div>

  const open = data.trades.filter((t) => t.status === 'abierta')
  const closed = data.trades.filter((t) => t.status === 'cerrada')

  return (
    <>
      <header className="screen-head">
        <h1>¿Estoy siguiendo mi plan?</h1>
        <p className="soft">
          Guarda cada plan desde Mi riesgo y ciérralo aquí. Las cifras salen solo de lo que registras; nada sale de tu
          computadora.
        </p>
      </header>

      {data.breaches.length > 0 && (
        <div className="breach" role="alert">
          <b>Fuera de tus reglas</b>
          {data.breaches.map((b) => (
            <p key={b}>{b}</p>
          ))}
        </div>
      )}

      <div className="grid">
        <div className="span-8 stack">
          <SummaryStats title="Esta semana" s={data.semana} />
          <SummaryStats title="Últimos 30 días" s={data.mes} />

          <section className="panel" aria-label="Abiertas">
            <div className="panel-title">Abiertas ({open.length})</div>
            {open.length === 0 && <p className="soft">Ninguna abierta.</p>}
            {open.map((t) => (
              <details key={t.id} className="trade">
                <summary>
                  <span className="mono">{t.symbol}</span> {t.side === 'LONG' ? 'compra' : 'venta'} a{' '}
                  <span className="mono">{formatPrice(t.entry)}</span> · stop{' '}
                  <span className="mono">{formatPrice(t.stop)}</span> · riesgo {usd(t.risk_usd)}
                  {t.outside_rules && <span className="tag warn">fuera de reglas</span>}
                </summary>
                <p className="note">Motivo: {t.reason}</p>
                <CloseForm trade={t} onDone={load} />
              </details>
            ))}
          </section>

          <section className="panel" aria-label="Cerradas">
            <div className="panel-title">Cerradas ({closed.length})</div>
            {closed.length === 0 ? (
              <p className="soft">Aún no cierras operaciones.</p>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Mercado</th>
                      <th>Entrada → salida</th>
                      <th>R</th>
                      <th>Plan</th>
                      <th>Motivo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {closed.map((t) => (
                      <tr key={t.id}>
                        <td className="mono">{t.symbol}</td>
                        <td className="mono">
                          {formatPrice(t.entry)} → {formatPrice(t.exit as number)}
                        </td>
                        <td className={`mono ${(t.r ?? 0) < 0 ? 'down' : 'up'}`}>{rText(t.r)}</td>
                        <td>{t.followed_plan ? 'Sí' : 'No'}</td>
                        <td className="soft">{t.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>

        <section className="panel span-4 form" aria-label="Mis reglas">
          <div className="panel-title">Mis reglas</div>
          <p className="note">Las defines tú. Vacío significa que esa regla no existe.</p>
          {RULES.map((r) => (
            <Field key={r.key} label={r.label} hint={r.hint}>
              <NumberInput
                value={draft[r.key] ?? Number.NaN}
                onChange={(v) => setDraft({ ...draft, [r.key]: v })}
                step={r.step}
                min={0}
              />
            </Field>
          ))}
          <button className="btn" type="button" onClick={saveRules}>
            Guardar reglas
          </button>
          {saved && <p className="note">{saved}</p>}
        </section>
      </div>
    </>
  )
}
