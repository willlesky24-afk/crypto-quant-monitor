import type { ReactNode } from 'react'

export function Panel({
  title,
  status,
  tone = '',
  className = '',
  children,
}: {
  title: string
  status?: string
  tone?: string
  className?: string
  children: ReactNode
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-head">
        <h2 className="panel-title" style={{ margin: 0 }}>
          {title}
        </h2>
        {status && <span className={`tag ${tone}`}>{status}</span>}
      </div>
      {children}
    </section>
  )
}

// Positions are 0-100 along the track; values outside are clamped to the edge.
const clamp = (v: number) => Math.max(0, Math.min(100, v))

// The signature motif (DEC-V02 Enmienda 1): a graduated scale with a fine
// triangular index, the same on every meter. "fill" places the index at a
// value; "span" draws a bronze segment (a range) and "mark" the current value.
export function Scale({
  fill,
  span,
  mark,
  legend,
}: {
  fill?: number | null
  span?: [number, number] | null
  mark?: number | null
  legend?: [string, string]
}) {
  const index = mark ?? fill
  return (
    <>
      <div className="gauge" aria-hidden="true">
        <div className="gauge-ticks" />
        <div className="gauge-track" />
        {span && (
          <div className="gauge-span" style={{ left: `${clamp(span[0])}%`, width: `${clamp(span[1]) - clamp(span[0])}%` }} />
        )}
        {index != null && <div className="gauge-index" style={{ left: `${clamp(index)}%` }} />}
      </div>
      {legend && (
        <div className="scale-legend">
          <span>{legend[0]}</span>
          <span>{legend[1]}</span>
        </div>
      )}
    </>
  )
}
