import React from 'react'
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts'

export default function MetricsChart({ riskHistory }) {
  const data = riskHistory.map((snap, i) => ({
    idx: i + 1,
    unified: snap.components.unified_score,
    operational: snap.components.operational_risk,
    anomaly: snap.components.anomaly_risk,
    drift: snap.components.drift_risk,
  }))

  if (data.length === 0) {
    return <div className="empty-state">No invocations yet — run a prompt to start populating the risk timeline.</div>
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid stroke="#24303B" strokeDasharray="2 4" />
        <XAxis dataKey="idx" stroke="#7C8896" tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }} />
        <YAxis domain={[0, 100]} stroke="#7C8896" tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }} />
        <Tooltip
          contentStyle={{ background: '#131A22', border: '1px solid #1F2A35', fontFamily: 'IBM Plex Mono', fontSize: 12 }}
          labelStyle={{ color: '#7C8896' }}
        />
        <Legend wrapperStyle={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }} />
        <Line type="monotone" dataKey="unified" name="Unified" stroke="#E7EDF3" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="operational" name="Operational" stroke="#F5A623" strokeWidth={1.5} dot={false} />
        <Line type="monotone" dataKey="anomaly" name="Anomaly" stroke="#3DDC84" strokeWidth={1.5} dot={false} />
        <Line type="monotone" dataKey="drift" name="Drift" stroke="#E5484D" strokeWidth={1.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}
