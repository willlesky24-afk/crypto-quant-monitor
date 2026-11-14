import type { ReactNode } from 'react'

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  )
}

export function NumberInput({
  value,
  onChange,
  step = 1,
  min,
  max,
}: {
  value: number
  onChange: (v: number) => void
  step?: number
  min?: number
  max?: number
}) {
  return (
    <input
      className="input mono"
      type="number"
      inputMode="decimal"
      value={Number.isFinite(value) ? value : ''}
      step={step}
      min={min}
      max={max}
      onChange={(e) => onChange(e.target.value === '' ? Number.NaN : Number(e.target.value))}
    />
  )
}

export function Choice<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
  label: string
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} aria-pressed={value === o.value} onClick={() => onChange(o.value)} type="button">
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Stat({ title, value, note }: { title: string; value: string; note?: string }) {
  return (
    <div className="stat">
      <div className="panel-title">{title}</div>
      <div className="figure">{value}</div>
      {note && <p className="note">{note}</p>}
    </div>
  )
}
