import React, { useState, useEffect } from 'react'
import { quantApi } from '../api'

function Stat({ label, value, tone }) {
  const color = tone === 'pos' ? 'var(--safe)' : tone === 'neg' ? 'var(--crit)' : tone === 'warn' ? 'var(--warn)' : 'var(--text)'
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className="value" style={{ color }}>{value}</div>
    </div>
  )
}

const fmtPct = (v) => (v === null || v === undefined) ? '—' : `${(v * 100).toFixed(2)}%`
const fmtNum = (v) => (v === null || v === undefined) ? '—' : v.toFixed(3)

export default function PortfolioLab({ onMetricsComputed }) {
  const [tickers, setTickers] = useState([
    { symbol: 'AAPL', weight: 30 }, { symbol: 'MSFT', weight: 25 },
    { symbol: 'SPY', weight: 25 }, { symbol: 'TLT', weight: 20 },
  ])
  const [newTicker, setNewTicker] = useState('')
  const [newWeight, setNewWeight] = useState('')
  const [benchmark, setBenchmark] = useState('SPY')
  const [period, setPeriod] = useState('1y')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [contributions, setContributions] = useState([])
  const [isMock, setIsMock] = useState(false)
  const [mcVar, setMcVar] = useState(null)
  const [savedPortfolios, setSavedPortfolios] = useState([])
  const [saveName, setSaveName] = useState('')

  useEffect(() => { refreshSaved() }, [])

  async function refreshSaved() {
    try {
      const res = await quantApi.listPortfolios('default')
      setSavedPortfolios(res.portfolios)
    } catch { /* non-fatal */ }
  }

  async function savePortfolio() {
    if (!saveName.trim()) return
    const weights = {}
    tickers.forEach(t => { weights[t.symbol] = t.weight })
    await quantApi.savePortfolio({ session_id: 'default', name: saveName.trim(), tickers: tickers.map(t => t.symbol), weights, benchmark, period })
    setSaveName('')
    refreshSaved()
  }

  async function loadPortfolio(name) {
    const res = await quantApi.loadPortfolio(name, 'default')
    setTickers(res.tickers.map(sym => ({ symbol: sym, weight: (res.weights[sym] ?? 0) })))
    setBenchmark(res.benchmark)
    setPeriod(res.period)
  }

  async function removeSaved(name) {
    await quantApi.deletePortfolio(name, 'default')
    refreshSaved()
  }

  function addTicker() {
    if (!newTicker.trim() || !newWeight) return
    setTickers([...tickers, { symbol: newTicker.trim().toUpperCase(), weight: parseFloat(newWeight) }])
    setNewTicker(''); setNewWeight('')
  }
  function removeTicker(sym) {
    setTickers(tickers.filter(t => t.symbol !== sym))
  }

  function buildRequest(extra = {}) {
    const weights = {}
    tickers.forEach(t => { weights[t.symbol] = t.weight })
    return { tickers: tickers.map(t => t.symbol), weights, benchmark, period, ...extra }
  }

  async function run() {
    if (tickers.length === 0 || loading) return
    setLoading(true); setError(null); setMcVar(null)
    try {
      const res = await quantApi.portfolio(buildRequest())
      setMetrics(res.metrics)
      setContributions(res.position_contributions)
      setIsMock(res.is_mock_data)
      if (onMetricsComputed) {
        onMetricsComputed({ type: 'portfolio', tickers: tickers.map(t => t.symbol), metrics: res.metrics, position_contributions: res.position_contributions })
      }
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }

  async function runMonteCarlo() {
    if (!metrics || loading) return
    setLoading(true); setError(null)
    try {
      const res = await quantApi.monteCarloVar(buildRequest({ n_sims: 5000, horizon_days: 1, distribution: 'normal' }))
      setMcVar(res.result)
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }

  return (
    <div>
      <div className="panel">
        <p className="section-title">Portfolio {isMock && <span className="mock-badge">SIMULATED DATA</span>}</p>
        <div style={{ marginBottom: 10 }}>
          {tickers.map(t => (
            <span className="chip" key={t.symbol}>
              {t.symbol} {t.weight}%
              <button onClick={() => removeTicker(t.symbol)}>✕</button>
            </span>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="field">
            <label>Ticker</label>
            <input value={newTicker} onChange={e => setNewTicker(e.target.value)} style={{ width: 90 }} />
          </div>
          <div className="field">
            <label>Weight %</label>
            <input value={newWeight} onChange={e => setNewWeight(e.target.value)} style={{ width: 80 }} />
          </div>
          <div className="field">
            <label>Benchmark</label>
            <input value={benchmark} onChange={e => setBenchmark(e.target.value.toUpperCase())} style={{ width: 90 }} />
          </div>
          <div className="field">
            <label>Period</label>
            <select value={period} onChange={e => setPeriod(e.target.value)}>
              {['3mo', '6mo', '1y', '2y'].map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <button className="run-btn" onClick={addTicker} type="button" style={{ background: '#24303B', color: 'var(--text)' }}>+ Add</button>
          <button className="run-btn" onClick={run} disabled={loading}>{loading ? 'Running…' : 'Run Analysis'}</button>
        </div>
        {error && <div style={{ color: 'var(--crit)', fontSize: 12.5, marginTop: 8 }}>{error}</div>}
      </div>

      <div className="panel" style={{ marginTop: 14 }}>
        <p className="section-title">Saved portfolios</p>
        <div style={{ marginBottom: 8 }}>
          {savedPortfolios.length === 0 && <span style={{ color: 'var(--muted)', fontSize: 12.5 }}>No saved portfolios yet.</span>}
          {savedPortfolios.map(p => (
            <span className="chip" key={p.name}>
              <span style={{ cursor: 'pointer' }} onClick={() => loadPortfolio(p.name)}>{p.name}</span>
              <button onClick={() => removeSaved(p.name)}>✕</button>
            </span>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input className="field" style={{ padding: '7px 9px', background: '#0E141B', border: '1px solid var(--panel-border)', color: 'var(--text)', borderRadius: 4, fontFamily: 'var(--font-data)', fontSize: 12.5 }}
            placeholder="name this portfolio…" value={saveName} onChange={e => setSaveName(e.target.value)} />
          <button className="run-btn" style={{ background: '#24303B', color: 'var(--text)' }} onClick={savePortfolio}>Save current</button>
        </div>
      </div>

      {metrics && (
        <>
          <div className="stat-strip" style={{ marginTop: 14, gridTemplateColumns: 'repeat(4, 1fr)' }}>
            <Stat label="Ann. Return" value={fmtPct(metrics.ann_return)} tone={metrics.ann_return >= 0 ? 'pos' : 'neg'} />
            <Stat label="Ann. Volatility" value={fmtPct(metrics.ann_volatility)} />
            <Stat label="Sharpe Ratio" value={fmtNum(metrics.sharpe_ratio)} />
            <Stat label="Sortino Ratio" value={fmtNum(metrics.sortino_ratio)} />
            <Stat label="CAPM Beta" value={fmtNum(metrics.capm_beta)} />
            <Stat label="Treynor Measure" value={fmtNum(metrics.treynor_measure)} />
            <Stat label="Jensen's Alpha" value={fmtPct(metrics.jensen_alpha)} tone={metrics.jensen_alpha >= 0 ? 'pos' : 'neg'} />
            <Stat label="Information Ratio" value={fmtNum(metrics.information_ratio)} />
            <Stat label="Max Drawdown" value={fmtPct(metrics.max_drawdown)} tone="neg" />
            <Stat label="VaR 95% (historical)" value={fmtPct(metrics.var_historical)} tone="warn" />
            <Stat label="ES 95% (historical)" value={fmtPct(metrics.es_historical)} tone="neg" />
            <Stat label="VaR 95% (parametric)" value={fmtPct(metrics.var_parametric)} tone="warn" />
            <Stat label="ES 95% (parametric)" value={fmtPct(metrics.es_parametric)} tone="neg" />
            <Stat label="Skewness" value={fmtNum(metrics.skewness)} />
            <Stat label="Excess Kurtosis" value={fmtNum(metrics.excess_kurtosis)} />
          </div>

          <div className="panel" style={{ marginTop: 14 }}>
            <p className="section-title">Monte Carlo VaR — full repricing under simulated correlated scenarios</p>
            <button className="run-btn" onClick={runMonteCarlo} disabled={loading}>
              {loading ? 'Simulating…' : 'Run 5,000-path Monte Carlo VaR'}
            </button>
            {mcVar && (
              <div className="stat-strip" style={{ marginTop: 12, gridTemplateColumns: 'repeat(4, 1fr)' }}>
                <Stat label="MC VaR 95%" value={fmtPct(mcVar.var_monte_carlo)} tone="warn" />
                <Stat label="MC ES 95%" value={fmtPct(mcVar.es_monte_carlo)} tone="neg" />
                <Stat label="Simulations" value={mcVar.n_sims} />
                <Stat label="Horizon (days)" value={mcVar.horizon_days} />
              </div>
            )}
          </div>

          <div className="panel" style={{ marginTop: 14 }}>
            <p className="section-title">Position drill-down — who's actually driving portfolio risk</p>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5, fontFamily: 'var(--font-data)' }}>
              <thead>
                <tr style={{ color: 'var(--muted)', textAlign: 'left', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  <th style={{ padding: '4px 8px' }}>Ticker</th>
                  <th style={{ padding: '4px 8px' }}>Weight</th>
                  <th style={{ padding: '4px 8px' }}>Ann. Return</th>
                  <th style={{ padding: '4px 8px' }}>Ann. Vol</th>
                  <th style={{ padding: '4px 8px' }}>% of Portfolio Risk</th>
                </tr>
              </thead>
              <tbody>
                {contributions.map(c => (
                  <tr key={c.ticker} style={{ borderTop: '1px solid var(--panel-border)' }}>
                    <td style={{ padding: '6px 8px', fontWeight: 600 }}>{c.ticker}</td>
                    <td style={{ padding: '6px 8px' }}>{(c.weight * 100).toFixed(1)}%</td>
                    <td style={{ padding: '6px 8px', color: c.ann_return >= 0 ? 'var(--safe)' : 'var(--crit)' }}>{fmtPct(c.ann_return)}</td>
                    <td style={{ padding: '6px 8px' }}>{fmtPct(c.ann_volatility)}</td>
                    <td style={{ padding: '6px 8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ flex: 1, background: '#0E141B', borderRadius: 3, height: 6, maxWidth: 90 }}>
                          <div style={{ width: `${Math.min(100, c.pct_of_portfolio_risk)}%`, height: '100%', background: c.pct_of_portfolio_risk > 35 ? 'var(--crit)' : c.pct_of_portfolio_risk > 20 ? 'var(--warn)' : 'var(--safe)', borderRadius: 3 }} />
                        </div>
                        <span>{c.pct_of_portfolio_risk.toFixed(1)}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
