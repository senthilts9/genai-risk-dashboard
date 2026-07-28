import React from 'react'

function colorFor(band) {
  if (band === 'CRITICAL') return 'var(--crit)'
  if (band === 'HIGH') return 'var(--warn)'
  if (band === 'MEDIUM') return '#8FCB4E'
  return 'var(--safe)'
}

export default function AlertsPanel({ records, riskHistory }) {
  const alerts = []
  for (let i = riskHistory.length - 1; i >= 0; i--) {
    const snap = riskHistory[i]
    const rec = records[i]
    if (!rec) continue
    if (snap.components.band === 'HIGH' || snap.components.band === 'CRITICAL') {
      alerts.push({
        key: rec.id,
        time: new Date(rec.timestamp).toLocaleTimeString(),
        band: snap.components.band,
        msg: `Unified risk ${snap.components.unified_score.toFixed(1)} on "${rec.model}" (${snap.components.band.toLowerCase()} band)`,
      })
    }
    if (rec.refusal_flag) {
      alerts.push({ key: `${rec.id}-r`, time: new Date(rec.timestamp).toLocaleTimeString(), band: 'MEDIUM', msg: 'Refusal language detected in response' })
    }
    if (alerts.length >= 8) break
  }

  if (alerts.length === 0) {
    return <div className="empty-state">No threshold breaches recorded yet.</div>
  }

  return (
    <div>
      {alerts.map(a => (
        <div className="alert-row" key={a.key}>
          <div className="alert-dot" style={{ background: colorFor(a.band) }} />
          <div>
            <div style={{ color: 'var(--muted)', fontFamily: 'var(--font-data)', fontSize: 10.5 }}>{a.time}</div>
            <div>{a.msg}</div>
          </div>
        </div>
      ))}
    </div>
  )
}
