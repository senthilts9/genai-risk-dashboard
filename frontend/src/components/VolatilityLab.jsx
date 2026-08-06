import React, { useState } from 'react'
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts'
import { quantApi } from '../api'

export default function VolatilityLab() {
  const [tickerStr, setTickerStr] = useState('AAPL, MSFT, SPY, TLT')
  const [weightStr, setWeightStr] = useState('30, 25, 25, 20')
  const [period, setPeriod] = useState('1y')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [isMock, setIsMock] = useState(false)
  const [mlResult, setMlResult] = useState(null)
  const [mlError, setMlError] = useState(null)

  async function run() {
    setLoading(true); setError(null); setMlResult(null); setMlError(null)
    try {
      const tickers = tickerStr.split(',').map(s => s.trim().toUpperCase()).filter(Boolean)
      const weightVals = weightStr.split(',').map(s => parseFloat(s.trim()))
      const weights = {}
      tickers.forEach((t, i) => { weights[t] = weightVals[i] ?? 0 })
      const req = { tickers, weights, benchmark: 'SPY', period }
      const [res, mlRes] = await Promise.all([
        quantApi.volatility(req),
        quantApi.mlVolatility(req).catch(e => ({ error: e.message })),
      ])
      setResult(res.result)
      setIsMock(res.is_mock_data)
      if (mlRes.error) setMlError(mlRes.error)
      else setMlResult(mlRes.result)
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }

  const chartData = result ? result.ewma_vol_annualized.map((v, i) => ({
    t: i, ewma: v, garch: result.garch.conditional_vol_annualized_pct[i],
  })) : []

  return (
    <div>
      <div className="panel">
        <p className="section-title">Portfolio inputs {isMock && <span className="mock-badge">SIMULATED DATA</span>}</p>
        <div className="field-row">
          <div className="field"><label>Tickers (comma-separated)</label><input value={tickerStr} onChange={e => setTickerStr(e.target.value)} /></div>
          <div className="field"><label>Weights % (same order)</label><input value={weightStr} onChange={e => setWeightStr(e.target.value)} /></div>
          <div className="field">
            <label>Period</label>
            <select value={period} onChange={e => setPeriod(e.target.value)}>
              {['3mo', '6mo', '1y', '2y'].map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        </div>
        <button className="run-btn" onClick={run} disabled={loading}>{loading ? 'Fitting…' : 'Fit EWMA + GARCH(1,1)'}</button>
        {error && <div style={{ color: 'var(--crit)', fontSize: 12.5, marginTop: 8 }}>{error}</div>}
      </div>

      {result && (
        <>
          <div className="panel" style={{ marginTop: 14 }}>
            <p className="section-title">EWMA (λ={result.ewma_lambda}) vs GARCH(1,1) — annualized conditional volatility</p>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
                <CartesianGrid stroke="#24303B" strokeDasharray="2 4" />
                <XAxis dataKey="t" stroke="#7C8896" tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }} />
                <YAxis stroke="#7C8896" tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }} unit="%" />
                <Tooltip contentStyle={{ background: '#131A22', border: '1px solid #1F2A35', fontFamily: 'IBM Plex Mono', fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }} />
                <Line type="monotone" dataKey="ewma" name="EWMA" stroke="#3DDC84" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="garch" name="GARCH(1,1)" stroke="#F5A623" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="stat-strip" style={{ marginTop: 14 }}>
            <div className="stat"><div className="label">GARCH ω</div><div className="value">{result.garch.omega}</div></div>
            <div className="stat"><div className="label">GARCH α</div><div className="value">{result.garch.alpha}</div></div>
            <div className="stat"><div className="label">GARCH β</div><div className="value">{result.garch.beta}</div></div>
            <div className="stat"><div className="label">Persistence (α+β)</div><div className="value">{result.garch.persistence}</div></div>
          </div>

          <div className="panel" style={{ marginTop: 14 }}>
            <p className="section-title">ML Volatility Forecast — GradientBoostingRegressor, trained live on this exact data</p>
            {mlError && <div style={{ color: 'var(--warn)', fontSize: 12.5 }}>{mlError}</div>}
            {mlResult && (
              <>
                <div className="stat-strip">
                  <div className="stat">
                    <div className="label">Live Forecast (5d fwd, ann.)</div>
                    <div className="value">{(mlResult.live_forecast_annualized_vol * 100).toFixed(2)}%</div>
                  </div>
                  <div className="stat">
                    <div className="label">Test R² (n={mlResult.test_rows})</div>
                    <div className="value" style={{ color: mlResult.test_r2 > 0 ? 'var(--safe)' : 'var(--warn)' }}>{mlResult.test_r2}</div>
                  </div>
                  <div className="stat">
                    <div className="label">RMSE vs Naive Baseline</div>
                    <div className="value" style={{ color: mlResult.beats_naive_baseline ? 'var(--safe)' : 'var(--crit)' }}>
                      {mlResult.test_rmse} vs {mlResult.naive_baseline_rmse}
                    </div>
                  </div>
                  <div className="stat">
                    <div className="label">Improvement vs Naive</div>
                    <div className="value" style={{ color: mlResult.improvement_vs_naive_pct >= 0 ? 'var(--safe)' : 'var(--crit)' }}>
                      {mlResult.improvement_vs_naive_pct >= 0 ? '+' : ''}{mlResult.improvement_vs_naive_pct}%
                    </div>
                  </div>
                </div>
                {mlResult.test_r2 < 0 && (
                  <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
                    Note: negative R² here means the model underperforms simply predicting the mean on this window —
                    common on short/simulated series with limited real volatility clustering. Shown honestly rather
                    than hidden; check the RMSE-vs-naive comparison alongside R² for the fuller picture.
                  </div>
                )}
                <p className="section-title" style={{ marginTop: 14 }}>Feature importances</p>
                {Object.entries(mlResult.feature_importances).map(([feat, imp]) => (
                  <div key={feat} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                    <span style={{ width: 90, fontSize: 11.5, fontFamily: 'var(--font-data)', color: 'var(--muted)' }}>{feat}</span>
                    <div style={{ flex: 1, background: '#0E141B', borderRadius: 3, height: 8 }}>
                      <div style={{ width: `${imp * 100 * 3}%`, maxWidth: '100%', height: '100%', background: 'var(--safe)', borderRadius: 3 }} />
                    </div>
                    <span style={{ fontSize: 11, fontFamily: 'var(--font-data)', width: 40 }}>{(imp * 100).toFixed(1)}%</span>
                  </div>
                ))}
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
