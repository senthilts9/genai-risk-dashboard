# Meridian — Risk & Quant Console

*Built by Senthil Saravanamuthu — Risk, Quantitative & Front Office Developer*

*© 2026 Senthil Saravanamuthu. All rights reserved. This project is NOT
public domain and is shared publicly for demonstration/portfolio purposes
only — see [`LICENSE`](LICENSE).*

A live monitoring console for a GenAI application that combines **model
performance monitoring** with **quant-style risk measures** into one unified
risk score. Every prompt sent through the console calls a real OpenAI model,
logs telemetry, and re-scores risk against a rolling window of recent
invocations.

## Stack

- **Backend**: FastAPI (Python), SQLite for storage, `openai` SDK for the
  live model calls.
- **Frontend**: React + Vite, `recharts` for time series, a custom SVG
  instrument dial for the composite score.
- **Deploy**: Docker Compose, designed to run on a single AWS free-tier
  EC2 instance (see `deploy/aws-ec2-deploy.md`).

## Risk methodology (what's actually being measured)

Every invocation logs: latency, input/output tokens, cost, response length,
and two heuristic content flags (refusal language, hedging/uncertainty
language). These feed a rolling window (default: last 50 invocations per
session) that produces four risk components, combined into a unified score:

| Component | What it measures | Technique |
|---|---|---|
| **Operational risk** | Cost/latency tail risk | Historical-simulation VaR(95) on the rolling window; a new observation's risk contribution scales with how far it breaches the VaR threshold |
| **Anomaly risk** | Statistical outliers | Z-score of the new observation vs. the rolling mean/std of latency and response length |
| **Drift risk** | Behavioral/distribution shift | Split-window comparison (older half vs. recent half) of mean response length and latency — a proxy for drift when ground-truth accuracy labels aren't available |
| **Content safety risk** | Refusal/uncertainty language | Keyword heuristics (documented limitation below) |

`unified_score = 0.30·operational + 0.25·anomaly + 0.25·drift + 0.20·content_safety`,
clipped to [0, 100] and banded LOW (<25) / MEDIUM (<50) / HIGH (<75) / CRITICAL (≥75).
Weights live as named constants in `backend/app/quant_risk.py` — change them
to match your own risk appetite; nothing is hardcoded into a black box.

**Honest limitation**: the content-safety flags are keyword heuristics, not
a hallucination or toxicity classifier. In production, swap
`flag_text()` in `quant_risk.py` for a judge-model call or a proper
classifier — the rest of the pipeline (storage, windowing, unified score)
doesn't need to change.

## Quant Lab (portfolio, derivatives, fixed income, volatility)

Five more tabs sit alongside the GenAI risk console, covering the models in
`FRM_2026_Part_1_QuickSheet` that are actually computable from price data:

| Tab | What it does | Key models |
|---|---|---|
| **Portfolio Risk** | Live/mock market data → return, vol, risk-adjusted performance | CAPM beta, Sharpe, Sortino, Treynor, Jensen's alpha, Information Ratio, historical VaR/ES, parametric (delta-normal) VaR/ES, Monte Carlo VaR/ES, max drawdown, skew/kurtosis |
| **Volatility Models** | Fits conditional volatility to the portfolio's return series | EWMA (RiskMetrics, λ=0.94), GARCH(1,1) via MLE |
| **Derivatives** | Prices one option three ways and cross-checks them | Black-Scholes-Merton (+ Greeks), Cox-Ross-Rubinstein binomial tree (European & American), Monte Carlo (antithetic variates) |
| **Fixed Income** | Bond price/duration/convexity/DV01 from the cash-flow schedule | Macaulay & modified duration, convexity, DV01 (validated against a finite-difference bump-and-reprice) |
| **Model Library** | Static reference: what each model is for, when to use it, and its limitations | Covers all of the above plus historical vs. parametric vs. Monte Carlo VaR, CAPM/APT/Fama-French |

**Market data**: `market_quant.py` pulls prices via `yfinance` (free, no API
key). If the network is unavailable or a ticker fails to resolve, it falls
back to a synthetic geometric Brownian motion series per ticker so the app
never breaks — every response includes an `is_mock_data` flag so the UI can
show a "SIMULATED DATA" badge when that happens. Swap in Alpha Vantage,
Polygon, or another provider by editing only `fetch_price_history()`.

Every number in these tabs is cross-checkable: Black-Scholes vs. binomial vs.
Monte Carlo option prices should land within a few cents of each other, and
DV01 from the closed-form duration formula matches the finite-difference
bump-and-reprice almost exactly — both are asserted in the module's own
sanity tests.

### Portfolio management, scenarios, and the Risk Copilot

- **Saved/named portfolios** — save the current ticker/weight set under a
  name, reload or delete it later (`portfolios` table in the same SQLite DB).
- **Position drill-down** — every portfolio run also returns a risk-budgeting
  decomposition per position: Marginal Contribution to Risk and % of total
  portfolio risk (`market_quant.position_contributions`), so you can see
  which holding is actually driving volatility, not just which is biggest by
  weight.
- **Yield-curve scenario slider** (Fixed Income tab) — drag a parallel yield
  shift from -300 to +300 bps and the estimated price change updates live,
  computed client-side from the already-fitted duration/convexity via the
  standard Taylor approximation (ΔP ≈ -D·P·Δy + ½·C·P·Δy²) — no extra API
  call per drag.
- **Risk Copilot tab** — a chat interface (`/api/copilot`, backed by
  `gpt-4o-mini` by default) that answers questions in plain English,
  grounded in whatever you last computed in the Portfolio tab (passed as
  JSON context in the system prompt) rather than generic textbook answers.
- **View counter** — the masthead shows total page views + unique visitors.
  Each browser gets a random UUID stored in `localStorage` on first visit
  (this is a real deployed web app, not a Claude artifact preview, so
  `localStorage` is fine here) and every load pings `/api/analytics/visit`,
  which is tallied in the same SQLite DB and read back via
  `/api/analytics/stats`.

## Running locally

```bash
export OPENAI_API_KEY=sk-proj-...
docker compose up --build
```

Open http://localhost — the frontend proxies `/api/*` to the backend
container.

To run without Docker:

```bash
# backend
cd backend
pip install -r requirements.txt
export OPENAI_API_KEY=sk-proj-...
uvicorn app.main:app --reload

# frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## API surface

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/invoke` | Call the model, log telemetry, return the fresh risk snapshot |
| GET | `/api/history?session_id=&limit=` | Recent invocation records + risk history for charting |
| GET | `/api/risk/current?session_id=` | Latest risk snapshot only |
| GET | `/api/health` | Liveness probe |
| POST | `/api/quant/portfolio` | Portfolio return/risk/performance metrics |
| POST | `/api/quant/portfolio/monte-carlo-var` | Monte Carlo VaR/ES via full repricing |
| POST | `/api/quant/volatility` | EWMA + GARCH(1,1) conditional volatility |
| POST | `/api/quant/option/black-scholes` | Black-Scholes price + Greeks |
| POST | `/api/quant/option/binomial` | CRR binomial tree (European/American) |
| POST | `/api/quant/option/monte-carlo` | Monte Carlo option price + CI |
| POST | `/api/quant/bond` | Duration, convexity, DV01 |
| POST | `/api/quant/portfolio/save` | Save a named portfolio |
| GET | `/api/quant/portfolio/list` | List saved portfolios |
| GET | `/api/quant/portfolio/load` | Load a saved portfolio |
| DELETE | `/api/quant/portfolio/{name}` | Delete a saved portfolio |
| POST | `/api/copilot` | Ask the risk copilot a question (context-aware) |
| POST | `/api/analytics/visit` | Record a page visit |
| GET | `/api/analytics/stats` | Total visits + unique visitors |

## Pushing this to GitHub

```bash
chmod +x scripts/*.sh
./scripts/push_to_github.sh git@github.com:<you>/<repo>.git
```

Creates `.gitignore`, commits everything, and pushes to a repo you've
already created empty on GitHub.

## Deploying to AWS (free tier)

First launch and open up an EC2 instance per
[`deploy/aws-ec2-deploy.md`](deploy/aws-ec2-deploy.md) (`t2.micro`/`t3.micro`,
security group open on 22 + 80). Then, one command deploys the whole stack:

```bash
export OPENAI_API_KEY=sk-proj-...
./scripts/deploy_ec2.sh <ec2-public-ip> <path-to-key.pem>
```

This syncs the code, installs Docker if needed, writes your key into a
chmod-600 `.env` on the box (never committed to git), and runs
`docker compose up -d --build`. Visit `http://<ec2-public-ip>`.

### Auto-deploy on every push

`.github/workflows/deploy.yml` redeploys to the same EC2 box automatically
whenever you push to `main`. Add these repo secrets first
(Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `EC2_HOST` | instance public IP/DNS |
| `EC2_SSH_KEY` | contents of your `.pem` key |
| `EC2_USER` | ssh user (defaults to `ubuntu`) |
| `OPENAI_API_KEY` | your OpenAI key |

After that, `git push` is the whole deploy loop.

**Prefer a free tier that doesn't expire after 12 months?** See
[`deploy/oracle-cloud-deploy.md`](deploy/oracle-cloud-deploy.md) — Oracle
Cloud's Always Free tier gives more compute than AWS's and never starts
billing you, at the cost of occasional capacity/idle-reclaim quirks. The
same `deploy_ec2.sh` script and GitHub Actions workflow work unchanged on
either.


## Project layout

```
genai-risk-dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI routes (GenAI risk + Quant Lab)
│   │   ├── quant_risk.py    # GenAI app risk engine (VaR, z-scores, drift, unified score)
│   │   ├── market_quant.py  # Quant Lab: portfolio, volatility, derivatives, bonds
│   │   ├── llm_client.py    # OpenAI API wrapper + cost table
│   │   ├── storage.py       # SQLite persistence
│   │   └── models.py        # Pydantic schemas
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # tab shell
│   │   ├── api.js
│   │   └── components/
│   │       ├── RiskDial.jsx       # composite score gauge
│   │       ├── MetricsChart.jsx   # risk component time series
│   │       ├── AlertsPanel.jsx    # threshold-breach feed
│   │       ├── InvokePanel.jsx    # live prompt console
│   │       ├── PortfolioLab.jsx   # CAPM/Sharpe/VaR/ES etc.
│   │       ├── VolatilityLab.jsx  # EWMA vs GARCH(1,1)
│   │       ├── DerivativesLab.jsx # Black-Scholes/binomial/Monte Carlo
│   │       ├── BondLab.jsx        # duration/convexity/DV01
│   │       └── ModelLibrary.jsx   # static model reference
│   ├── package.json
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
└── deploy/aws-ec2-deploy.md
```
