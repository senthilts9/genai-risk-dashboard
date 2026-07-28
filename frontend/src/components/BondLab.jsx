import React, { useState } from 'react'
import { quantApi } from '../api'

function Stat({ label, value, tone }) {
  const color = tone === 'pos' ? 'var(--safe)' : tone === 'neg' ? 'var(--crit)' : tone === 'warn' ? 'var(--warn)' : 'var(--text)'
  return <div className="stat"><div className="label">{label}</div><div className="value" style={{ color }}>{value}</div></div>
}

export default function BondLab() {
  const [form, setForm] = useState({ face_value: 1000, coupon_rate: 0.05, ytm: 0.042, years_to_maturity: 7, freq: 2 })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [shiftBps, setShiftBps] = useState(0)

  function upd(key, val) { setForm({ ...form, [key]: val }) }

  async function run() {
    setLoading(true); setError(null)
    try {
      const res = await quantApi.bond(form)
      setResult(res)
      setShiftBps(0)
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }

  // Live scenario: dP ≈ -D*P*dy + 0.5*C*P*dy^2  (Taylor approx from the fitted duration/convexity — no extra API call needed as the slider moves)
  const dy = shiftBps / 10000
  const scenario = result ? {
    dP: -result.modified_duration * result.clean_price * dy + 0.5 * result.convexity * result.clean_price * dy * dy,
  } : null
  const newPrice = result && scenario ? result.clean_price + scenario.dP : null

  return (
    <div>
      <div className="panel">
        <p className="section-title">Bond parameters</p>
        <div className="field-row">
          <div className="field"><label>Face value</label><input type="number" value={form.face_value} onChange={e => upd('face_value', +e.target.value)} /></div>
          <div className="field"><label>Coupon rate</label><input type="number" step="0.001" value={form.coupon_rate} onChange={e => upd('coupon_rate', +e.target.value)} /></div>
          <div className="field"><label>YTM</label><input type="number" step="0.001" value={form.ytm} onChange={e => upd('ytm', +e.target.value)} /></div>
          <div className="field"><label>Years to maturity</label><input type="number" step="0.5" value={form.years_to_maturity} onChange={e => upd('years_to_maturity', +e.target.value)} /></div>
          <div className="field">
            <label>Payments / year</label>
            <select value={form.freq} onChange={e => upd('freq', +e.target.value)}>
              <option value={1}>1 (annual)</option><option value={2}>2 (semiannual)</option><option value={4}>4 (quarterly)</option>
            </select>
          </div>
        </div>
        <button className="run-btn" onClick={run} disabled={loading}>{loading ? 'Calculating…' : 'Calculate'}</button>
        {error && <div style={{ color: 'var(--crit)', fontSize: 12.5, marginTop: 8 }}>{error}</div>}
      </div>

      {result && (
        <>
          <div className="stat-strip" style={{ marginTop: 14 }}>
            <Stat label="Clean Price" value={`$${result.clean_price.toFixed(2)}`} />
            <Stat label="Macaulay Duration" value={`${result.macaulay_duration.toFixed(3)} yrs`} />
            <Stat label="Modified Duration" value={`${result.modified_duration.toFixed(3)} yrs`} />
            <Stat label="Convexity" value={result.convexity.toFixed(3)} />
            <Stat label="DV01 (analytical)" value={`$${result.dv01_analytical.toFixed(4)}`} />
            <Stat label="DV01 (bump-and-reprice)" value={`$${result.dv01_finite_difference.toFixed(4)}`} tone="pos" />
          </div>

          <div className="panel" style={{ marginTop: 14 }}>
            <p className="section-title">Scenario: parallel yield curve shift (live, duration + convexity Taylor approximation)</p>
            <input
              type="range" min="-300" max="300" step="5" value={shiftBps}
              onChange={e => setShiftBps(Number(e.target.value))}
              style={{ width: '100%' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-data)' }}>
              <span>-300 bps</span><span>0</span><span>+300 bps</span>
            </div>
            <div className="stat-strip" style={{ marginTop: 12 }}>
              <Stat label="Yield Shift" value={`${shiftBps >= 0 ? '+' : ''}${shiftBps} bps`} tone={shiftBps === 0 ? undefined : shiftBps > 0 ? 'neg' : 'pos'} />
              <Stat label="Est. Price Change" value={`${scenario.dP >= 0 ? '+' : ''}$${scenario.dP.toFixed(2)}`} tone={scenario.dP >= 0 ? 'pos' : 'neg'} />
              <Stat label="Est. New Price" value={`$${newPrice.toFixed(2)}`} />
              <Stat label="% Change" value={`${((scenario.dP / result.clean_price) * 100).toFixed(2)}%`} tone={scenario.dP >= 0 ? 'pos' : 'neg'} />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
