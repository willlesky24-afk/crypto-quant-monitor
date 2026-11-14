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
  return (
    <>
      <div className="scale" aria-hidden="true">
        {fill != null && <div className="fill" style={{ left: 0, width: `${clamp(fill)}%` }} />}
        {span && (
          <div
            className="fill"
            style={{ left: `${clamp(span[0])}%`, width: `${clamp(span[1]) - clamp(span[0])}%` }}
          />
        )}
        {mark != null && <div className="mark" style={{ left: `${clamp(mark)}%` }} />}
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
