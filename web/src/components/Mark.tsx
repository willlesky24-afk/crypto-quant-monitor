// Brand mark: the signature motif (a graduated scale with a fine index), not a
// coin. The product covers four asset classes, so the mark belongs to none.
export function Mark({ size = 28, animate = false }: { size?: number; animate?: boolean }) {
  const ticks = Array.from({ length: 11 }, (_, i) => i)
  return (
    <svg
      className={`mark-svg${animate ? ' animate' : ''}`}
      width={size}
      height={size}
      viewBox="0 0 40 40"
      aria-hidden="true"
    >
      <rect x="0" y="0" width="40" height="40" rx="10" fill="#191D23" />
      {ticks.map((i) => (
        <line
          key={i}
          className="mark-tick"
          style={{ animationDelay: `${i * 30}ms` }}
          x1={8 + i * 2.4}
          x2={8 + i * 2.4}
          y1={i % 5 === 0 ? 17 : 20}
          y2="24"
          stroke={i % 5 === 0 ? '#F3F2EE' : 'rgba(243, 242, 238, 0.55)'}
          strokeWidth="1"
        />
      ))}
      <line x1="8" x2="32" y1="26" y2="26" stroke="rgba(243, 242, 238, 0.55)" strokeWidth="1" />
      <path className="mark-index" d="M25.6 29 l-3 4.5 h6 z" fill="#B8A57A" />
    </svg>
  )
}
