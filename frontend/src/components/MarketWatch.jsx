import React, { useState, useEffect, useCallback, useRef } from 'react'
import { marketApi } from '../api'

const fmtMoney = (v) => `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`

export default function MarketWatch({ onLoadIntoPortfolio }) {
  const [portfolios, setPortfolios] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [holdings, setHoldings] = useState(null)
  const [prevPrices, setPrevPrices] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const pollRef = useRef(null)

  const [tickBenchmark, setTickBenchmark] = useState(null)
  const [tickLoading, setTickLoading] = useState(false)
  const [tickError, setTickError] = useState(null)

  const [cppBenchmark, setCppBenchmark] = useState(null)
  const [cppLoading, setCppLoading] = useState(false)
  const [cppError, setCppError] = useState(null)
  const [cppAvailable, setCppAvailable] = useState(null)

  const [kdbBenchmark, setKdbBenchmark] = useState(null)
  const [kdbLoading, setKdbLoading] = useState(false)
  const [kdbError, setKdbError] = useState(null)
  const [kdbAvailable, setKdbAvailable] = useState(null)

  async function runKdbSimulation() {
    setKdbLoading(true); setKdbError(null)
    try {
      const res = await marketApi.tickSimulationKdb(1_000_000, 60)
      setKdbBenchmark(res)
    } catch (e) { setKdbError(e.message) } finally { setKdbLoading(false) }
  }

  useEffect(() => {
    marketApi.cppEngineStatus().then(res => setCppAvailable(res.cpp_extension_available)).catch(() => {})
    marketApi.kdbEngineStatus().then(res => setKdbAvailable(res.kdb_available)).catch(() => {})
  }, [])

  async function runTickSimulation() {
    setTickLoading(true); setTickError(null)
    try {
      const res = await marketApi.tickSimulation(1_000_000, 60)
      setTickBenchmark(res)
    } catch (e) { setTickError(e.message) } finally { setTickLoading(false) }
  }

  async function runCppSimulation() {
    setCppLoading(true); setCppError(null)
    try {
      const res = await marketApi.tickSimulationCpp(1_000_000, 60)
      setCppBenchmark(res)
    } catch (e) { setCppError(e.message) } finally { setCppLoading(false) }
  }

  useEffect(() => {
    marketApi.portfolios().then(res => {
      setPortfolios(res.portfolios)
      if (res.portfolios.length > 0) setSelectedId(res.portfolios[0].portfolio_id)
    }).catch(e => setError(e.message))
  }, [])

  const refresh = useCallback(async (id) => {
    if (!id) return
    try {
      const res = await marketApi.holdings(id)
      setHoldings(prev => {
        if (prev) {
          const prices = {}
          prev.holdings.forEach(h => { prices[h.ticker] = h.last })
          setPrevPrices(prices)
        }
        return res
      })
      setError(null)
    } catch (e) { setError(e.message) }
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setHoldings(null)
    refresh(selectedId)
    clearInterval(pollRef.current)
    pollRef.current = setInterval(() => refresh(selectedId), 4000)
    return () => clearInterval(pollRef.current)
  }, [selectedId, refresh])

  function loadIntoPortfolio() {
    if (!holdings || !onLoadIntoPortfolio) return
    onLoadIntoPortfolio(holdings.holdings.map(h => ({ symbol: h.ticker, weight: h.weight_pct })))
  }

  return (
    <div>
      <div className="panel">
        <p className="section-title">
          Market Watch — sample fund book <span className="mock-badge">MOCK DATA — NOT LIVE / NOT PRODUCTION</span>
        </p>
        <div>
          {portfolios.map(p => (
            <span
              key={p.portfolio_id}
              className="chip"
              style={{ cursor: 'pointer', borderColor: selectedId === p.portfolio_id ? 'var(--safe)' : undefined, color: selectedId === p.portfolio_id ? 'var(--safe)' : undefined }}
              onClick={() => setSelectedId(p.portfolio_id)}
            >
              {p.fund_code} · {p.name}
            </span>
          ))}
        </div>
        {error && <div style={{ color: 'var(--crit)', fontSize: 12.5, marginTop: 8 }}>{error}</div>}
      </div>

      {holdings && (
        <>
          <div className="stat-strip">
            <div className="stat">
              <div className="label">Fund</div>
              <div className="value" style={{ fontSize: 16 }}>{holdings.name}</div>
            </div>
            <div className="stat">
              <div className="label">Fund Code / ISIN</div>
              <div className="value" style={{ fontSize: 14 }}>{holdings.fund_code}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{holdings.isin}</div>
            </div>
            <div className="stat">
              <div className="label">Mandate</div>
              <div className="value" style={{ fontSize: 13 }}>{holdings.mandate}</div>
            </div>
            <div className="stat">
              <div className="label">AUM</div>
              <div className="value">{fmtMoney(holdings.aum)}</div>
            </div>
          </div>

          <div className="panel" style={{ marginTop: 14 }}>
            <p className="section-title">
              Holdings blotter <span style={{ color: 'var(--muted)', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>· ticks every 4s</span>
            </p>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5, fontFamily: 'var(--font-data)', minWidth: 640 }}>
                <thead>
                  <tr style={{ color: 'var(--muted)', textAlign: 'left', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    <th style={{ padding: '4px 8px' }}>Security</th>
                    <th style={{ padding: '4px 8px' }}>ISIN / CUSIP</th>
                    <th style={{ padding: '4px 8px' }}>Qty</th>
                    <th style={{ padding: '4px 8px' }}>Last</th>
                    <th style={{ padding: '4px 8px' }}>Day %</th>
                    <th style={{ padding: '4px 8px' }}>Mkt Value</th>
                    <th style={{ padding: '4px 8px' }}>Weight</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.holdings.map(h => {
                    const prevPrice = prevPrices[h.ticker]
                    const flash = prevPrice !== undefined ? (h.last > prevPrice ? 'var(--safe)' : h.last < prevPrice ? 'var(--crit)' : undefined) : undefined
                    return (
                      <tr key={h.ticker} style={{ borderTop: '1px solid var(--panel-border)' }}>
                        <td style={{ padding: '6px 8px' }}>
                          <div style={{ fontWeight: 600 }}>{h.ticker}</div>
                          <div style={{ color: 'var(--muted)', fontSize: 11 }}>{h.name}</div>
                        </td>
                        <td style={{ padding: '6px 8px', fontSize: 11, color: 'var(--muted)' }}>
                          {h.isin}<br />{h.cusip}
                        </td>
                        <td style={{ padding: '6px 8px' }}>{h.quantity.toLocaleString()}</td>
                        <td style={{ padding: '6px 8px', transition: 'color 0.3s', color: flash || 'var(--text)' }}>${h.last.toFixed(2)}</td>
                        <td style={{ padding: '6px 8px', color: h.change_pct >= 0 ? 'var(--safe)' : 'var(--crit)' }}>
                          {h.change_pct >= 0 ? '+' : ''}{h.change_pct}%
                        </td>
                        <td style={{ padding: '6px 8px' }}>{fmtMoney(h.market_value)}</td>
                        <td style={{ padding: '6px 8px' }}>{h.weight_pct}%</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <button className="run-btn" style={{ marginTop: 14 }} onClick={loadIntoPortfolio}>
              Load into Portfolio Risk tab →
            </button>
          </div>
        </>
      )}

      <div className="panel" style={{ marginTop: 14 }}>
        <p className="section-title">
          Tick Data Benchmark <span style={{ color: 'var(--muted)', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>· simulated at scale — foundation for the KDB-X benchmark</span>
        </p>
        <p style={{ fontSize: 12.5, color: 'var(--muted)', marginBottom: 12 }}>
          Generates 1,000,000 simulated trade ticks (Poisson arrivals, GBM microprice, lognormal volume) across the
          12 mock securities, then aggregates to 1-minute OHLCV bars via DuckDB — a real, timed benchmark, not a
          static claim.
        </p>
        <button className="run-btn" onClick={runTickSimulation} disabled={tickLoading}>
          {tickLoading ? 'Simulating 1M ticks…' : 'Simulate 1,000,000 ticks'}
        </button>
        {tickError && <div style={{ color: 'var(--crit)', fontSize: 12.5, marginTop: 8 }}>{tickError}</div>}
        {tickBenchmark && (
          <>
            <div className="stat-strip" style={{ marginTop: 14 }}>
              <div className="stat"><div className="label">Ticks Generated</div><div className="value">{tickBenchmark.n_ticks.toLocaleString()}</div></div>
              <div className="stat"><div className="label">Generation Time</div><div className="value">{tickBenchmark.generation_seconds}s</div></div>
              <div className="stat"><div className="label">Bars Produced</div><div className="value">{tickBenchmark.n_bars.toLocaleString()}</div></div>
              <div className="stat"><div className="label">Aggregation Time</div><div className="value">{tickBenchmark.aggregation_seconds}s</div></div>
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 8, fontFamily: 'var(--font-data)' }}>
              engine: {tickBenchmark.aggregation_engine}
            </div>
          </>
        )}
      </div>

      <div className="panel" style={{ marginTop: 14 }}>
        <p className="section-title">
          C++ Engine Benchmark
          {cppAvailable === true && <span className="mock-badge" style={{ color: 'var(--safe)', borderColor: 'var(--safe)' }}>COMPILED EXTENSION ACTIVE</span>}
          {cppAvailable === false && <span className="mock-badge">PYTHON FALLBACK — EXTENSION NOT BUILT</span>}
        </p>
        <p style={{ fontSize: 12.5, color: 'var(--muted)', marginBottom: 12 }}>
          Same tick generation + OHLCV aggregation, implemented as a compiled pybind11 C++ extension
          (<span style={{ fontFamily: 'var(--font-data)' }}>backend/cpp/tick_engine.cpp</span>) instead of vectorized numpy —
          benchmarked in isolation at ~3.3M ticks/sec on portable -O3 flags, run it here against the exact same workload above.
        </p>
        <button className="run-btn" onClick={runCppSimulation} disabled={cppLoading}>
          {cppLoading ? 'Running C++ engine…' : 'Run C++ engine on 1,000,000 ticks'}
        </button>
        {cppError && <div style={{ color: 'var(--crit)', fontSize: 12.5, marginTop: 8 }}>{cppError}</div>}
        {cppBenchmark && (
          <>
            <div className="stat-strip" style={{ marginTop: 14 }}>
              <div className="stat"><div className="label">Ticks Generated</div><div className="value">{cppBenchmark.n_ticks.toLocaleString()}</div></div>
              <div className="stat"><div className="label">Generation Time</div><div className="value">{cppBenchmark.generation_seconds}s</div></div>
              <div className="stat"><div className="label">Bars Produced</div><div className="value">{cppBenchmark.n_bars.toLocaleString()}</div></div>
              <div className="stat">
                <div className="label">Throughput</div>
                <div className="value" style={{ color: 'var(--safe)' }}>{cppBenchmark.ticks_per_sec_total?.toLocaleString()}/sec</div>
              </div>
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 8, fontFamily: 'var(--font-data)' }}>
              engine: {cppBenchmark.engine}
            </div>
            {tickBenchmark && cppBenchmark.ticks_per_sec_total && (
              <div style={{ fontSize: 12.5, marginTop: 10, color: 'var(--safe)' }}>
                {(cppBenchmark.ticks_per_sec_total / (tickBenchmark.n_ticks / (tickBenchmark.generation_seconds + tickBenchmark.aggregation_seconds))).toFixed(1)}x faster than the Python/DuckDB pipeline above on this run
              </div>
            )}
          </>
        )}
      </div>

      <div className="panel" style={{ marginTop: 14 }}>
        <p className="section-title">
          KDB-X Engine Benchmark
          {kdbAvailable === true && <span className="mock-badge" style={{ color: 'var(--safe)', borderColor: 'var(--safe)' }}>PYKX DETECTED</span>}
          {kdbAvailable === false && <span className="mock-badge">SETUP REQUIRED — SEE README</span>}
        </p>
        <p style={{ fontSize: 12.5, color: 'var(--muted)', marginBottom: 8 }}>
          Same ticks, bulk-inserted into a kdb+ table and aggregated to OHLCV bars via q's idiomatic <code style={{ fontFamily: 'var(--font-data)' }}>xbar</code> time-bucketing
          (<span style={{ fontFamily: 'var(--font-data)' }}>backend/kdb/schema.q</span>). Requires a free personal KDB-X license (interactive signup at kx.com) that
          can't be provisioned automatically — until it's installed, this runs the same Python fallback as the panel above.
        </p>
        <p style={{ fontSize: 11.5, color: 'var(--warn)', marginBottom: 12 }}>
          ⚠ Unlike the C++ engine above (compiled and benchmarked for real), this integration was written against KDB-X's
          documented API but has not been executed end-to-end — verify against your own install before trusting the numbers.
        </p>
        <button className="run-btn" onClick={runKdbSimulation} disabled={kdbLoading}>
          {kdbLoading ? 'Running…' : 'Run KDB-X engine on 1,000,000 ticks'}
        </button>
        {kdbError && <div style={{ color: 'var(--crit)', fontSize: 12.5, marginTop: 8 }}>{kdbError}</div>}
        {kdbBenchmark && (
          <>
            <div className="stat-strip" style={{ marginTop: 14 }}>
              <div className="stat"><div className="label">Ticks Generated</div><div className="value">{kdbBenchmark.n_ticks.toLocaleString()}</div></div>
              <div className="stat"><div className="label">Insert Time</div><div className="value">{kdbBenchmark.insert_seconds !== null ? `${kdbBenchmark.insert_seconds}s` : '—'}</div></div>
              <div className="stat"><div className="label">Query Time (xbar)</div><div className="value">{kdbBenchmark.query_seconds}s</div></div>
              <div className="stat"><div className="label">Bars Produced</div><div className="value">{kdbBenchmark.n_bars.toLocaleString()}</div></div>
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 8, fontFamily: 'var(--font-data)' }}>
              engine: {kdbBenchmark.engine}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
