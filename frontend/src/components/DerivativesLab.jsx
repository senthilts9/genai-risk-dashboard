import React, { useState } from 'react'
import { quantApi } from '../api'

function Stat({ label, value, tone }) {
  const color = tone === 'pos' ? 'var(--safe)' : tone === 'neg' ? 'var(--crit)' : tone === 'warn' ? 'var(--warn)' : 'var(--text)'
  return <div className="stat"><div className="label">{label}</div><div className="value" style={{ color }}>{value}</div></div>
}

export default function DerivativesLab() {
  const [form, setForm] = useState({
    spot: 190, strike: 195, time_to_maturity: 0.25, risk_free_rate: 0.045,
    volatility: 0.28, dividend_yield: 0.0, option_type: 'call',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [bs, setBs] = useState(null)
  const [tree, setTree] = useState(null)
  const [mc, setMc] = useState(null)
  const [american, setAmerican] = useState(false)
  const [steps, setSteps] = useState(200)

  function upd(key, val) { setForm({ ...form, [key]: val }) }

  async function runAll() {
    setLoading(true); setError(null)
    try {
      const [bsRes, treeRes, mcRes] = await Promise.all([
        quantApi.blackScholes(form),
        quantApi.binomial({ ...form, n_steps: Number(steps), american }),
        quantApi.monteCarloOption({ ...form, n_sims: 20000 }),
      ])
      setBs(bsRes); setTree(treeRes); setMc(mcRes)
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }

  const priceKey = form.option_type === 'call' ? 'call_price' : 'put_price'

  return (
    <div>
      <div className="panel">
        <p className="section-title">Option parameters</p>
        <div className="field-row">
          <div className="field"><label>Spot S₀</label><input type="number" value={form.spot} onChange={e => upd('spot', +e.target.value)} /></div>
          <div className="field"><label>Strike X</label><input type="number" value={form.strike} onChange={e => upd('strike', +e.target.value)} /></div>
          <div className="field"><label>T (years)</label><input type="number" step="0.05" value={form.time_to_maturity} onChange={e => upd('time_to_maturity', +e.target.value)} /></div>
          <div className="field"><label>Rate r</label><input type="number" step="0.001" value={form.risk_free_rate} onChange={e => upd('risk_free_rate', +e.target.value)} /></div>
          <div className="field"><label>Volatility σ</label><input type="number" step="0.01" value={form.volatility} onChange={e => upd('volatility', +e.target.value)} /></div>
          <div className="field"><label>Dividend yield q</label><input type="number" step="0.001" value={form.dividend_yield} onChange={e => upd('dividend_yield', +e.target.value)} /></div>
          <div className="field">
            <label>Type</label>
            <select value={form.option_type} onChange={e => upd('option_type', e.target.value)}>
              <option value="call">call</option><option value="put">put</option>
            </select>
          </div>
          <div className="field">
            <label>Tree steps</label>
            <input type="number" value={steps} onChange={e => setSteps(e.target.value)} />
          </div>
          <div className="field">
            <label>Exercise style</label>
            <select value={american ? 'american' : 'european'} onChange={e => setAmerican(e.target.value === 'american')}>
              <option value="european">european</option><option value="american">american</option>
            </select>
          </div>
        </div>
        <button className="run-btn" onClick={runAll} disabled={loading}>{loading ? 'Pricing…' : 'Price with all 3 models'}</button>
        {error && <div style={{ color: 'var(--crit)', fontSize: 12.5, marginTop: 8 }}>{error}</div>}
      </div>

      {bs && (
        <div className="panel" style={{ marginTop: 14 }}>
          <p className="section-title">Cross-model price check — should agree closely for a vanilla European option</p>
          <div className="stat-strip">
            <Stat label="Black-Scholes (closed-form)" value={`$${bs[priceKey].toFixed(4)}`} tone="pos" />
            <Stat label={`Binomial Tree (${tree.exercise_style})`} value={`$${tree.price.toFixed(4)}`} />
            <Stat label="Monte Carlo (European)" value={`$${mc.price.toFixed(4)}`} />
            <Stat label="MC 95% CI" value={`[${mc.ci_95[0]}, ${mc.ci_95[1]}]`} />
          </div>
        </div>
      )}

      {bs && (
        <div className="panel" style={{ marginTop: 14 }}>
          <p className="section-title">Black-Scholes Greeks</p>
          <div className="stat-strip">
            <Stat label="Call Delta" value={bs.call_delta} />
            <Stat label="Put Delta" value={bs.put_delta} />
            <Stat label="Gamma" value={bs.gamma} />
            <Stat label="Vega (per 1% vol)" value={bs.vega} />
            <Stat label="Call Theta / day" value={bs.call_theta_per_day} tone="neg" />
            <Stat label="Put Theta / day" value={bs.put_theta_per_day} tone="neg" />
            <Stat label="Call Rho" value={bs.call_rho} />
            <Stat label="Put Rho" value={bs.put_rho} />
          </div>
        </div>
      )}
    </div>
  )
}
