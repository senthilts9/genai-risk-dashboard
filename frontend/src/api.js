const BASE = import.meta.env.VITE_API_BASE || '/api'

async function handle(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed: ${res.status}`)
  }
  return res.json()
}

export async function invoke(prompt, model, sessionId, messages = null) {
  const body = { prompt, model, session_id: sessionId }
  if (messages && messages.length > 0) body.messages = messages
  const res = await fetch(`${BASE}/invoke`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return handle(res)
}

export async function getHistory(sessionId, limit = 50) {
  const res = await fetch(`${BASE}/history?session_id=${encodeURIComponent(sessionId)}&limit=${limit}`)
  return handle(res)
}

export async function getCurrentRisk(sessionId) {
  const res = await fetch(`${BASE}/risk/current?session_id=${encodeURIComponent(sessionId)}`)
  if (res.status === 404) return null
  return handle(res)
}

// ---------------- Quant Lab ----------------

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return handle(res)
}

export const quantApi = {
  portfolio: (body) => post('/quant/portfolio', body),
  monteCarloVar: (body) => post('/quant/portfolio/monte-carlo-var', body),
  volatility: (body) => post('/quant/volatility', body),
  mlVolatility: (body) => post('/quant/ml-volatility', body),
  blackScholes: (body) => post('/quant/option/black-scholes', body),
  binomial: (body) => post('/quant/option/binomial', body),
  monteCarloOption: (body) => post('/quant/option/monte-carlo', body),
  bond: (body) => post('/quant/bond', body),
  savePortfolio: (body) => post('/quant/portfolio/save', body),
  listPortfolios: async (sessionId = 'default') => handle(await fetch(`${BASE}/quant/portfolio/list?session_id=${encodeURIComponent(sessionId)}`)),
  loadPortfolio: async (name, sessionId = 'default') => handle(await fetch(`${BASE}/quant/portfolio/load?name=${encodeURIComponent(name)}&session_id=${encodeURIComponent(sessionId)}`)),
  deletePortfolio: async (name, sessionId = 'default') => handle(await fetch(`${BASE}/quant/portfolio/${encodeURIComponent(name)}?session_id=${encodeURIComponent(sessionId)}`, { method: 'DELETE' })),
}

export async function askCopilot(question, context, model = 'gpt-4o-mini') {
  return post('/copilot', { question, context, model })
}

// ---------------- Analytics ----------------

export async function recordVisit(visitorId) {
  return post('/analytics/visit', { visitor_id: visitorId, user_agent: navigator.userAgent })
}

export async function getVisitStats() {
  const res = await fetch(`${BASE}/analytics/stats`)
  return handle(res)
}

// ---------------- Mock Market Data (fund/security browser, not live/prod) ----------------

export const marketApi = {
  securities: async () => handle(await fetch(`${BASE}/market/securities`)),
  quotes: async (tickers) => handle(await fetch(`${BASE}/market/quotes?tickers=${encodeURIComponent(tickers.join(','))}`)),
  portfolios: async () => handle(await fetch(`${BASE}/market/portfolios`)),
  holdings: async (portfolioId) => handle(await fetch(`${BASE}/market/portfolios/${encodeURIComponent(portfolioId)}/holdings`)),
  tickSimulation: async (nTicks = 1000000, barSeconds = 60) =>
    handle(await fetch(`${BASE}/market/tick-simulation?n_ticks=${nTicks}&bar_seconds=${barSeconds}`, { method: 'POST' })),
  tickSimulationCpp: async (nTicks = 1000000, barSeconds = 60) =>
    handle(await fetch(`${BASE}/market/tick-simulation-cpp?n_ticks=${nTicks}&bar_seconds=${barSeconds}`, { method: 'POST' })),
  cppEngineStatus: async () => handle(await fetch(`${BASE}/market/cpp-engine-status`)),
  tickSimulationKdb: async (nTicks = 1000000, barSeconds = 60) =>
    handle(await fetch(`${BASE}/market/tick-simulation-kdb?n_ticks=${nTicks}&bar_seconds=${barSeconds}`, { method: 'POST' })),
  kdbEngineStatus: async () => handle(await fetch(`${BASE}/market/kdb-engine-status`)),
}
