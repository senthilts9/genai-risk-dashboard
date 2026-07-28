import React, { useEffect, useState, useCallback } from 'react'
import RiskDial from './components/RiskDial.jsx'
import MetricsChart from './components/MetricsChart.jsx'
import AlertsPanel from './components/AlertsPanel.jsx'
import InvokePanel from './components/InvokePanel.jsx'
import PortfolioLab from './components/PortfolioLab.jsx'
import VolatilityLab from './components/VolatilityLab.jsx'
import DerivativesLab from './components/DerivativesLab.jsx'
import BondLab from './components/BondLab.jsx'
import ModelLibrary from './components/ModelLibrary.jsx'
import RiskCopilot from './components/RiskCopilot.jsx'
import { getHistory, recordVisit, getVisitStats } from './api'

const SESSION_ID = 'default'

const TABS = [
  { key: 'genai', label: 'GenAI App Risk' },
  { key: 'portfolio', label: 'Portfolio Risk' },
  { key: 'volatility', label: 'Volatility Models' },
  { key: 'derivatives', label: 'Derivatives' },
  { key: 'bond', label: 'Fixed Income' },
  { key: 'copilot', label: 'Risk Copilot' },
  { key: 'library', label: 'Model Library' },
]

function GenAIRiskView() {
  const [records, setRecords] = useState([])
  const [riskHistory, setRiskHistory] = useState([])
  const [loadErr, setLoadErr] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const data = await getHistory(SESSION_ID, 50)
      setRecords(data.records)
      setRiskHistory(data.risk_history)
      setLoadErr(null)
    } catch (e) {
      setLoadErr(e.message)
    }
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 15000)
    return () => clearInterval(t)
  }, [refresh])

  const latest = riskHistory[riskHistory.length - 1]
  const comp = latest?.components

  return (
    <>
      <div className="stat-strip">
        <div className="stat">
          <div className="label">VaR(95) Latency</div>
          <div className="value">{latest ? `${latest.var95_latency_ms.toFixed(0)} ms` : '—'}</div>
        </div>
        <div className="stat">
          <div className="label">VaR(95) Cost</div>
          <div className="value">{latest ? `$${latest.var95_cost_usd.toFixed(4)}` : '—'}</div>
        </div>
        <div className="stat">
          <div className="label">Sample Window</div>
          <div className="value">{latest ? latest.sample_size : 0}</div>
        </div>
        <div className="stat">
          <div className="label">Content Safety Risk</div>
          <div className="value">{comp ? comp.content_safety_risk.toFixed(1) : '—'}</div>
        </div>
      </div>

      <div className="grid">
        <div className="panel">
          <p className="section-title">Unified risk score — component breakdown over time</p>
          <MetricsChart riskHistory={riskHistory} />
        </div>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <p className="section-title" style={{ alignSelf: 'flex-start' }}>Live composite dial</p>
          <RiskDial score={comp?.unified_score ?? 0} band={comp?.band ?? 'LOW'} />
        </div>
      </div>

      <div className="grid">
        <div className="panel">
          <InvokePanel sessionId={SESSION_ID} onResult={refresh} />
        </div>
        <div className="panel">
          <p className="section-title">Alerts</p>
          <AlertsPanel records={records} riskHistory={riskHistory} />
        </div>
      </div>

      {loadErr && <p style={{ color: 'var(--crit)', fontSize: 12, marginTop: 16 }}>{loadErr}</p>}
    </>
  )
}

export default function App() {
  const [tab, setTab] = useState('genai')
  const [dashboardContext, setDashboardContext] = useState(null)
  const [visitStats, setVisitStats] = useState(null)

  useEffect(() => {
    let visitorId = localStorage.getItem('meridian_visitor_id')
    if (!visitorId) {
      visitorId = crypto.randomUUID()
      localStorage.setItem('meridian_visitor_id', visitorId)
    }
    recordVisit(visitorId)
      .then(() => getVisitStats())
      .then(setVisitStats)
      .catch(() => { /* analytics failures shouldn't break the app */ })
  }, [])

  return (
    <div className="app-shell">
      <div className="masthead">
        <div>
          <span className="eyebrow">Meridian · Risk &amp; Quant Console for GenAI Applications</span>
          <h1>Meridian</h1>
        </div>
        <div style={{ textAlign: 'right' }}>
          <span className="eyebrow">session: {SESSION_ID}</span>
          {visitStats && (
            <div className="eyebrow" style={{ marginTop: 4 }}>
              {visitStats.total_visits} views · {visitStats.unique_visitors} unique visitors
            </div>
          )}
        </div>
      </div>

      <div className="tab-bar">
        {TABS.map(t => (
          <div key={t.key} className={`tab-item ${tab === t.key ? 'active' : ''}`} onClick={() => setTab(t.key)}>
            {t.label}
          </div>
        ))}
      </div>

      {tab === 'genai' && <GenAIRiskView />}
      {tab === 'portfolio' && <PortfolioLab onMetricsComputed={setDashboardContext} />}
      {tab === 'volatility' && <VolatilityLab />}
      {tab === 'derivatives' && <DerivativesLab />}
      {tab === 'bond' && <BondLab />}
      {tab === 'copilot' && <RiskCopilot context={dashboardContext} />}
      {tab === 'library' && <ModelLibrary />}

      <div style={{ textAlign: 'center', marginTop: 36, paddingTop: 16, borderTop: '1px solid var(--panel-border)' }}>
        <span className="eyebrow" style={{ fontSize: 10.5 }}>
          Meridian — built by Senthil Saravanamuthu · Risk, Quantitative &amp; Front Office Developer
        </span>
        <div className="eyebrow" style={{ fontSize: 10, marginTop: 4, opacity: 0.8 }}>
          © {new Date().getFullYear()} Senthil Saravanamuthu. All rights reserved. Not public domain — demonstration purposes only.
        </div>
      </div>
    </div>
  )
}
