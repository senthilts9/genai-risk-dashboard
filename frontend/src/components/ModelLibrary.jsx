import React, { useState } from 'react'

const MODELS = [
  { name: 'Black-Scholes-Merton', cat: 'derivatives', tag: 'Closed-form', color: 'var(--safe)',
    formula: 'c = S₀N(d₁) − Xe^(-rT)N(d₂)',
    why: 'Instant, exact price + full Greek set for vanilla European options. The industry default when a closed form exists.',
    scenario: 'Pricing/hedging European calls & puts on liquid stocks, indices, FX, futures. Real-time Greek exposure for a trading desk.',
    limits: 'European exercise only (no early exercise), assumes constant volatility & risk-free rate, log-normal returns (no jumps/fat tails), continuous trading with no transaction costs.' },
  { name: 'Binomial (Cox-Ross-Rubinstein) Tree', cat: 'derivatives', tag: 'Lattice', color: 'var(--safe)',
    formula: 'U = e^(σ√Δt), D = 1/U, π_up = (e^(rΔt) − D)/(U − D)',
    why: 'Handles early exercise by checking optimal exercise at every node — something Black-Scholes structurally cannot do.',
    scenario: 'American options, employee stock options, bonds with embedded call/put features, anywhere early exercise has value.',
    limits: 'Slower than closed-form for vanilla European pricing; needs many steps (100+) to converge closely to Black-Scholes.' },
  { name: 'Monte Carlo Simulation', cat: 'derivatives', tag: 'Simulation', color: 'var(--safe)',
    formula: 'Price = e^(-rT) · (1/N)Σ payoff(pathᵢ)',
    why: 'The only practical method once payoffs depend on the full price path or multiple correlated assets.',
    scenario: 'Asian/lookback/barrier options, basket options across correlated assets, structured products.',
    limits: 'Computationally expensive; standard error shrinks only as 1/√N; Greeks require extra work (bump-and-reprice).' },
  { name: 'Historical Simulation VaR', cat: 'risk', tag: 'Non-parametric', color: 'var(--warn)',
    formula: 'VaR₉₅ = 95th percentile of ranked historical losses',
    why: 'Makes no distributional assumption — captures whatever fat tails, skew, or asymmetry actually happened.',
    scenario: 'Regulatory VaR reporting, portfolios where you distrust the normal-distribution assumption.',
    limits: 'Entirely backward-looking — an unprecedented event isn\u2019t in the sample; needs a long, clean return history.' },
  { name: 'Delta-Normal (Parametric) VaR', cat: 'risk', tag: 'Parametric', color: 'var(--warn)',
    formula: 'VaR = [μ − zσ] × portfolio value',
    why: 'Closed-form and near-instant even for very large portfolios.',
    scenario: 'Daily risk limits on large, mostly-linear portfolios where speed matters more than tail precision.',
    limits: 'Assumes normal returns — understates real-world tail risk; linear (delta) approximation misprices optionality.' },
  { name: 'Monte Carlo VaR / ES', cat: 'risk', tag: 'Simulation', color: 'var(--warn)',
    formula: 'Simulate N portfolio scenarios → rank → take tail percentile',
    why: 'Full repricing under simulated scenarios captures non-linear payoffs that delta-normal VaR misses.',
    scenario: 'Portfolios with meaningful options/derivatives exposure, stress testing, regulatory internal-models approach.',
    limits: 'Computationally heavy; results only as good as the chosen stochastic process and correlation assumptions.' },
  { name: 'EWMA (RiskMetrics)', cat: 'volatility', tag: 'Time series', color: '#8FCB4E',
    formula: 'σₙ² = λσₙ₋₁² + (1−λ)rₙ₋₁²',
    why: 'One parameter (λ, typically 0.94 daily), reacts fast to volatility shocks by exponentially discounting old data.',
    scenario: 'Daily VaR volatility inputs, fast-moving desks that need an adaptive vol estimate without fitting a full model.',
    limits: 'No mean reversion — a vol spike stays elevated until it ages out of the window.' },
  { name: 'GARCH(1,1)', cat: 'volatility', tag: 'Time series', color: '#8FCB4E',
    formula: 'σₙ² = ω + αrₙ₋₁² + βσₙ₋₁², VL = ω/(1−α−β)',
    why: 'Adds mean reversion to a long-run variance on top of EWMA\u2019s shock-reactivity (EWMA is the special case ω=0, α=1−λ, β=λ).',
    scenario: 'Multi-day/multi-week volatility forecasting, option-pricing vol calibration, stress-testing horizons.',
    limits: 'Needs MLE parameter estimation on sufficient history; assumes symmetric response to +/- shocks unless extended.' },
  { name: 'CAPM / APT / Fama-French', cat: 'factor', tag: 'Factor model', color: 'var(--muted)',
    formula: 'E(Rᵢ) = Rf + Σ bᵢⱼ · RPⱼ',
    why: 'Decomposes expected/realized return into systematic risk-factor exposure.',
    scenario: 'Performance attribution (skill vs. factor beta), cost-of-equity estimates, portfolio factor-tilt analysis.',
    limits: 'CAPM\u2019s single-factor assumption rarely holds empirically; APT doesn\u2019t specify which factors to use.' },
  { name: 'Duration & Convexity', cat: 'fixed_income', tag: 'Sensitivity', color: 'var(--muted)',
    formula: 'ΔP ≈ −D·P·Δy + ½·C·P·Δy²',
    why: 'First- and second-order Taylor approximation of the price-yield curve — cheap estimate of rate sensitivity.',
    scenario: 'Fixed-income portfolio hedging, quick DV01/rate-risk estimates, duration-matching for LDI.',
    limits: 'Breaks down for large yield moves; assumes a parallel curve shift; embedded options need OAS instead.' },
]

const CATS = [
  { key: 'all', label: 'All Models' },
  { key: 'derivatives', label: 'Derivatives Pricing' },
  { key: 'risk', label: 'Risk (VaR/ES)' },
  { key: 'volatility', label: 'Volatility / Time Series' },
  { key: 'factor', label: 'Factor Models' },
  { key: 'fixed_income', label: 'Fixed Income' },
]

export default function ModelLibrary() {
  const [cat, setCat] = useState('all')
  const filtered = cat === 'all' ? MODELS : MODELS.filter(m => m.cat === cat)

  return (
    <div>
      <div className="cat-row">
        {CATS.map(c => (
          <div key={c.key} className={`cat-pill ${cat === c.key ? 'active' : ''}`} onClick={() => setCat(c.key)}>{c.label}</div>
        ))}
      </div>
      {filtered.map(m => (
        <div className="model-card" key={m.name}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>{m.name}</h3>
            <span className="band-pill" style={{ color: m.color, fontSize: 10 }}>{m.tag}</span>
          </div>
          <div className="model-formula">{m.formula}</div>
          <div className="model-row"><div className="ml">Why use it</div><div className="mv">{m.why}</div></div>
          <div className="model-row"><div className="ml">Best scenario</div><div className="mv">{m.scenario}</div></div>
          <div className="model-row"><div className="ml">Limitations</div><div className="mv">{m.limits}</div></div>
        </div>
      ))}
    </div>
  )
}
