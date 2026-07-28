"""
GenAI Application Risk Dashboard -- backend API.

Endpoints:
  POST /api/invoke        -> call the LLM, log telemetry, return live risk snapshot
  GET  /api/history       -> recent invocation records + risk history for a session
  GET  /api/risk/current  -> latest risk snapshot for a session
  GET  /api/health        -> liveness probe
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os

from .models import (InvokeRequest, InvokeResponse, HistoryResponse, InvocationRecord,
                      PortfolioRequest, MonteCarloVarRequest, OptionRequest,
                      BinomialRequest, MonteCarloOptionRequest, BondRequest,
                      SavePortfolioRequest, CopilotRequest, VisitRequest)
from . import storage, llm_client, quant_risk, market_quant

app = FastAPI(title="GenAI Application Risk Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

WINDOW_SIZE = int(os.environ.get("RISK_WINDOW_SIZE", "50"))
DAILY_INVOKE_LIMIT = int(os.environ.get("DAILY_INVOKE_LIMIT", "60"))
DAILY_COPILOT_LIMIT = int(os.environ.get("DAILY_COPILOT_LIMIT", "60"))


@app.on_event("startup")
def _startup():
    storage.init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.post("/api/analytics/visit")
def record_visit(req: VisitRequest):
    storage.record_visit(req.visitor_id, req.user_agent or "")
    return {"status": "recorded"}


@app.get("/api/analytics/stats")
def visit_stats():
    return storage.get_visit_stats()


@app.post("/api/invoke", response_model=InvokeResponse)
def invoke(req: InvokeRequest):
    if storage.count_usage_today("genai_invoke") >= DAILY_INVOKE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="This is a public demo with a capped daily budget -- the limit has been reached for today. Please check back tomorrow, or spin up your own copy with your own API key (see the README).",
        )
    try:
        text, in_tok, out_tok, latency_ms = llm_client.call_model(
            req.prompt, req.model, req.messages
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}")

    storage.record_usage_event("genai_invoke")
    cost = llm_client.estimate_cost(req.model, in_tok, out_tok)
    refusal, uncertainty = quant_risk.flag_text(text)

    record = InvocationRecord(
        session_id=req.session_id,
        timestamp=datetime.utcnow(),
        model=req.model,
        prompt_chars=len(req.prompt),
        response_chars=len(text),
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=round(latency_ms, 2),
        cost_usd=round(cost, 6),
        refusal_flag=refusal,
        uncertainty_flag=uncertainty,
        response_preview=text[:280],
    )
    record.id = storage.add_record(record)

    history = storage.get_recent(req.session_id, limit=WINDOW_SIZE)
    risk = quant_risk.compute_risk(req.session_id, history, record)

    return InvokeResponse(record=record, risk=risk, response_text=text)


@app.get("/api/history", response_model=HistoryResponse)
def history(session_id: str = "default", limit: int = 50):
    records = storage.get_recent(session_id, limit=limit)
    risk_history = []
    # Recompute a risk snapshot at each point so the frontend can chart the
    # unified score over time (cheap: O(n^2) worst case but n is capped at `limit`).
    for i in range(len(records)):
        window = records[max(0, i - WINDOW_SIZE + 1): i + 1]
        risk_history.append(quant_risk.compute_risk(session_id, window, records[i]))
    return HistoryResponse(records=records, risk_history=risk_history)


@app.get("/api/risk/current")
def current_risk(session_id: str = "default"):
    records = storage.get_recent(session_id, limit=WINDOW_SIZE)
    if not records:
        raise HTTPException(status_code=404, detail="No invocations yet for this session.")
    return quant_risk.compute_risk(session_id, records, records[-1])


# ============================================================
# Quant Lab -- portfolio risk, volatility models, derivatives, fixed income
# ============================================================

def _load_prices(req: PortfolioRequest):
    all_tickers = list(dict.fromkeys(req.tickers + [req.benchmark]))
    prices, is_mock = market_quant.fetch_price_history(all_tickers, period=req.period)
    missing = [t for t in req.tickers if t not in prices.columns]
    if missing:
        raise HTTPException(status_code=422, detail=f"No price data for: {missing}")
    return prices, is_mock


@app.post("/api/quant/portfolio")
def quant_portfolio(req: PortfolioRequest):
    prices, is_mock = _load_prices(req)
    benchmark = prices[req.benchmark] if req.benchmark in prices.columns else None
    metrics = market_quant.compute_portfolio_metrics(
        prices[req.tickers], req.weights, benchmark=benchmark,
        rf_annual=req.rf_annual, var_confidence=req.var_confidence,
    )
    contributions = market_quant.position_contributions(prices[req.tickers], req.weights)
    return {"metrics": metrics, "position_contributions": contributions, "is_mock_data": is_mock}


@app.post("/api/quant/portfolio/save")
def save_portfolio(req: SavePortfolioRequest):
    storage.save_portfolio(req.session_id, req.name, req.tickers, req.weights, req.benchmark, req.period)
    return {"status": "saved", "name": req.name}


@app.get("/api/quant/portfolio/list")
def list_portfolios(session_id: str = "default"):
    return {"portfolios": storage.list_portfolios(session_id)}


@app.get("/api/quant/portfolio/load")
def load_portfolio(name: str, session_id: str = "default"):
    result = storage.load_portfolio(session_id, name)
    if not result:
        raise HTTPException(status_code=404, detail=f"No saved portfolio named '{name}'.")
    return result


@app.delete("/api/quant/portfolio/{name}")
def delete_portfolio(name: str, session_id: str = "default"):
    storage.delete_portfolio(session_id, name)
    return {"status": "deleted", "name": name}


@app.post("/api/copilot")
def copilot(req: CopilotRequest):
    if storage.count_usage_today("copilot") >= DAILY_COPILOT_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="This is a public demo with a capped daily budget -- the copilot limit has been reached for today. Please check back tomorrow.",
        )
    try:
        answer = llm_client.ask_copilot(req.question, context=req.context, model=req.model)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Copilot call failed: {e}")
    storage.record_usage_event("copilot")
    return {"answer": answer}


@app.post("/api/quant/portfolio/monte-carlo-var")
def quant_monte_carlo_var(req: MonteCarloVarRequest):
    prices, is_mock = _load_prices(req)
    result = market_quant.monte_carlo_var(
        prices[req.tickers], req.weights, n_sims=req.n_sims,
        horizon_days=req.horizon_days, var_confidence=req.var_confidence,
        dist=req.distribution,
    )
    return {"result": result, "is_mock_data": is_mock}


@app.post("/api/quant/volatility")
def quant_volatility(req: PortfolioRequest):
    prices, is_mock = _load_prices(req)
    result = market_quant.volatility_models(prices[req.tickers], req.weights)
    return {"result": result, "is_mock_data": is_mock}


@app.post("/api/quant/option/black-scholes")
def quant_black_scholes(req: OptionRequest):
    return market_quant.black_scholes(
        S=req.spot, X=req.strike, T=req.time_to_maturity,
        r=req.risk_free_rate, sigma=req.volatility, q=req.dividend_yield,
    )


@app.post("/api/quant/option/binomial")
def quant_binomial(req: BinomialRequest):
    return market_quant.binomial_tree(
        S=req.spot, X=req.strike, T=req.time_to_maturity, r=req.risk_free_rate,
        sigma=req.volatility, n_steps=req.n_steps, option_type=req.option_type,
        american=req.american, q=req.dividend_yield,
    )


@app.post("/api/quant/option/monte-carlo")
def quant_mc_option(req: MonteCarloOptionRequest):
    return market_quant.monte_carlo_option(
        S=req.spot, X=req.strike, T=req.time_to_maturity, r=req.risk_free_rate,
        sigma=req.volatility, option_type=req.option_type, n_sims=req.n_sims,
        q=req.dividend_yield,
    )


@app.post("/api/quant/bond")
def quant_bond(req: BondRequest):
    return market_quant.bond_analytics(
        face_value=req.face_value, coupon_rate=req.coupon_rate, ytm=req.ytm,
        years_to_maturity=req.years_to_maturity, freq=req.freq,
    )
