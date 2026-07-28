import React from 'react'

const BANDS = [
  { from: 0, to: 25, color: 'var(--safe)', label: 'LOW' },
  { from: 25, to: 50, color: '#8FCB4E', label: 'MEDIUM' },
  { from: 50, to: 75, color: 'var(--warn)', label: 'HIGH' },
  { from: 75, to: 100, color: 'var(--crit)', label: 'CRITICAL' },
]

// Gauge sweeps 180deg, from angle 180 (left, score=0) to angle 0 (right, score=100)
function polar(cx, cy, r, scoreAngleDeg) {
  const rad = (Math.PI / 180) * scoreAngleDeg
  return { x: cx + r * Math.cos(rad), y: cy - r * Math.sin(rad) }
}

function arcPath(cx, cy, r, fromScore, toScore) {
  const a0 = 180 - (fromScore / 100) * 180
  const a1 = 180 - (toScore / 100) * 180
  const p0 = polar(cx, cy, r, a0)
  const p1 = polar(cx, cy, r, a1)
  return `M ${p0.x} ${p0.y} A ${r} ${r} 0 0 1 ${p1.x} ${p1.y}`
}

export default function RiskDial({ score = 0, band = 'LOW' }) {
  const cx = 110, cy = 108, r = 90
  const needleAngle = 180 - (Math.min(100, Math.max(0, score)) / 100) * 180
  const needleTip = polar(cx, cy, r - 14, needleAngle)
  const bandColor = BANDS.find(b => band === b.label)?.color || 'var(--safe)'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <svg width="220" height="130" viewBox="0 0 220 130">
        {BANDS.map((b) => (
          <path
            key={b.label}
            d={arcPath(cx, cy, r, b.from, b.to)}
            stroke={b.color}
            strokeWidth="14"
            fill="none"
            opacity="0.85"
          />
        ))}
        {/* threshold ticks at 25/50/75 */}
        {[25, 50, 75].map((t) => {
          const angle = 180 - (t / 100) * 180
          const p1 = polar(cx, cy, r - 9, angle)
          const p2 = polar(cx, cy, r + 9, angle)
          return <line key={t} x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y} stroke="#0B0F14" strokeWidth="2" />
        })}
        {/* needle */}
        <line x1={cx} y1={cy} x2={needleTip.x} y2={needleTip.y} stroke="#E7EDF3" strokeWidth="2.5" />
        <circle cx={cx} cy={cy} r="5" fill="#E7EDF3" />
      </svg>
      <div style={{ marginTop: -8, textAlign: 'center' }}>
        <div style={{ fontFamily: 'var(--font-data)', fontSize: 34, fontWeight: 600, color: bandColor, lineHeight: 1 }}>
          {score.toFixed(1)}
        </div>
        <span className="band-pill" style={{ color: bandColor }}>{band}</span>
      </div>
    </div>
  )
}
