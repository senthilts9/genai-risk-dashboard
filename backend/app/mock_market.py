"""
Mock market data + sample fund portfolios, styled like a real investment
management data feed (ISIN/CUSIP/ticker conventions, portfolio holdings
blotter) but entirely simulated -- NOT a connection to any live/production
market data provider. Every response is tagged `is_mock: True` so the
frontend can never accidentally present this as real.

Security identifiers below use real, publicly-known ISIN/CUSIP codes for
well-known securities (these are public reference data, not sensitive) so
the format is authentic -- but prices, quotes, and portfolio holdings are
entirely simulated and refresh on every call via a seeded random walk.
Treat identifiers as illustrative; verify against an authoritative source
(e.g. OpenFIGI, Bloomberg) before any real use.
"""
import hashlib
import math
import time
from datetime import datetime, timezone

# ---------------------------------------------------------------
# Reference data: security master (ticker -> identifiers + metadata)
# ---------------------------------------------------------------
SECURITIES = {
    "AAPL":  {"name": "Apple Inc",                     "isin": "US0378331005", "cusip": "037833100", "asset_class": "Equity",     "sector": "Technology",        "currency": "USD", "exchange": "NASDAQ", "base_price": 228.50},
    "MSFT":  {"name": "Microsoft Corp",                 "isin": "US5949181045", "cusip": "594918104", "asset_class": "Equity",     "sector": "Technology",        "currency": "USD", "exchange": "NASDAQ", "base_price": 445.20},
    "GOOGL": {"name": "Alphabet Inc Class A",            "isin": "US02079K3059", "cusip": "02079K305", "asset_class": "Equity",     "sector": "Communication Svcs", "currency": "USD", "exchange": "NASDAQ", "base_price": 178.30},
    "AMZN":  {"name": "Amazon.com Inc",                  "isin": "US0231351067", "cusip": "023135106", "asset_class": "Equity",     "sector": "Consumer Disc.",    "currency": "USD", "exchange": "NASDAQ", "base_price": 205.10},
    "JPM":   {"name": "JPMorgan Chase & Co",             "isin": "US46625H1005", "cusip": "46625H100", "asset_class": "Equity",     "sector": "Financials",        "currency": "USD", "exchange": "NYSE",   "base_price": 236.80},
    "SPY":   {"name": "SPDR S&P 500 ETF Trust",          "isin": "US78462F1030", "cusip": "78462F103", "asset_class": "Equity ETF", "sector": "Broad Market",      "currency": "USD", "exchange": "NYSE Arca", "base_price": 585.40},
    "QQQ":   {"name": "Invesco QQQ Trust",               "isin": "US46090E1038", "cusip": "46090E103", "asset_class": "Equity ETF", "sector": "Large-Cap Growth",  "currency": "USD", "exchange": "NASDAQ", "base_price": 505.60},
    "TLT":   {"name": "iShares 20+ Year Treasury Bond ETF", "isin": "US4642874329", "cusip": "464287432", "asset_class": "Fixed Income ETF", "sector": "Govt Bonds",  "currency": "USD", "exchange": "NASDAQ", "base_price": 92.15},
    "LQD":   {"name": "iShares iBoxx IG Corp Bond ETF",  "isin": "US4642872265", "cusip": "464287226", "asset_class": "Fixed Income ETF", "sector": "IG Corp Bonds", "currency": "USD", "exchange": "NYSE Arca", "base_price": 108.90},
    "GLD":   {"name": "SPDR Gold Shares",                "isin": "US78463V1070", "cusip": "78463V107", "asset_class": "Commodity ETF", "sector": "Precious Metals", "currency": "USD", "exchange": "NYSE Arca", "base_price": 246.30},
    "VNQ":   {"name": "Vanguard Real Estate ETF",        "isin": "US9229085538", "cusip": "922908553", "asset_class": "REIT ETF",   "sector": "Real Estate",       "currency": "USD", "exchange": "NYSE Arca", "base_price": 92.70},
    "EFA":   {"name": "iShares MSCI EAFE ETF",           "isin": "US4642874265", "cusip": "464287426", "asset_class": "Equity ETF", "sector": "Intl Developed",    "currency": "USD", "exchange": "NYSE Arca", "base_price": 82.40},
}

# ---------------------------------------------------------------
# Sample fund portfolios (as an asset manager's book might look)
# ---------------------------------------------------------------
PORTFOLIOS = [
    {
        "portfolio_id": "GEQ-001",
        "name": "Global Equity Growth Fund",
        "fund_code": "MRDGEQ",
        "isin": "IE00BMOCK001",
        "mandate": "Global equity, growth-tilted",
        "currency": "USD",
        "holdings": [
            {"ticker": "AAPL", "quantity": 12000},
            {"ticker": "MSFT", "quantity": 9000},
            {"ticker": "GOOGL", "quantity": 15000},
            {"ticker": "AMZN", "quantity": 11000},
            {"ticker": "QQQ", "quantity": 6000},
        ],
    },
    {
        "portfolio_id": "BAL-002",
        "name": "Balanced Multi-Asset Fund",
        "fund_code": "MRDBAL",
        "isin": "IE00BMOCK002",
        "mandate": "60/40 multi-asset balanced",
        "currency": "USD",
        "holdings": [
            {"ticker": "SPY", "quantity": 8000},
            {"ticker": "TLT", "quantity": 14000},
            {"ticker": "LQD", "quantity": 9000},
            {"ticker": "GLD", "quantity": 3000},
            {"ticker": "VNQ", "quantity": 4000},
        ],
    },
    {
        "portfolio_id": "FI-003",
        "name": "Core Fixed Income Fund",
        "fund_code": "MRDFI",
        "isin": "IE00BMOCK003",
        "mandate": "Investment-grade fixed income",
        "currency": "USD",
        "holdings": [
            {"ticker": "TLT", "quantity": 22000},
            {"ticker": "LQD", "quantity": 26000},
        ],
    },
    {
        "portfolio_id": "INT-004",
        "name": "International Diversified Fund",
        "fund_code": "MRDINT",
        "isin": "IE00BMOCK004",
        "mandate": "Global ex-US diversified",
        "currency": "USD",
        "holdings": [
            {"ticker": "EFA", "quantity": 18000},
            {"ticker": "JPM", "quantity": 5000},
            {"ticker": "GLD", "quantity": 2500},
            {"ticker": "SPY", "quantity": 4000},
        ],
    },
]


def _seeded_walk(ticker: str, base_price: float) -> float:
    """
    Deterministic-but-time-varying 'live' price: a slow sine drift (so it
    trends smoothly rather than jittering randomly on every poll) plus a
    small per-ticker phase offset so different securities don't move in
    lockstep. Re-evaluated fresh on every call using wall-clock time --
    this is what makes repeated polls look like a ticking feed without
    needing any persistent state or websocket.
    """
    seed = int(hashlib.sha256(ticker.encode()).hexdigest(), 16) % 1000
    phase = seed / 1000 * 2 * math.pi
    t = time.time() / 20  # full cycle roughly every ~2 minutes
    drift = math.sin(t + phase) * 0.006          # up to ~0.6% slow drift
    micro_noise = math.sin(t * 37 + phase) * 0.0008  # tiny high-freq jitter
    return base_price * (1 + drift + micro_noise)


def get_quote(ticker: str) -> dict:
    sec = SECURITIES.get(ticker.upper())
    if not sec:
        return None
    price = _seeded_walk(ticker.upper(), sec["base_price"])
    change_pct = (price / sec["base_price"] - 1) * 100
    spread = price * 0.0004
    return {
        "ticker": ticker.upper(),
        "name": sec["name"],
        "isin": sec["isin"],
        "cusip": sec["cusip"],
        "asset_class": sec["asset_class"],
        "sector": sec["sector"],
        "currency": sec["currency"],
        "exchange": sec["exchange"],
        "last": round(price, 2),
        "bid": round(price - spread, 2),
        "ask": round(price + spread, 2),
        "change_pct": round(change_pct, 3),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "is_mock": True,
    }


def get_quotes(tickers: list) -> list:
    return [q for t in tickers if (q := get_quote(t)) is not None]


def list_securities() -> list:
    return [{"ticker": t, **{k: v for k, v in s.items() if k != "base_price"}} for t, s in SECURITIES.items()]


def list_portfolios() -> list:
    out = []
    for p in PORTFOLIOS:
        quotes = {h["ticker"]: get_quote(h["ticker"]) for h in p["holdings"]}
        aum = sum(quotes[h["ticker"]]["last"] * h["quantity"] for h in p["holdings"])
        out.append({
            "portfolio_id": p["portfolio_id"], "name": p["name"], "fund_code": p["fund_code"],
            "isin": p["isin"], "mandate": p["mandate"], "currency": p["currency"],
            "n_holdings": len(p["holdings"]), "aum": round(aum, 2), "is_mock": True,
        })
    return out


def get_portfolio_holdings(portfolio_id: str) -> dict:
    p = next((x for x in PORTFOLIOS if x["portfolio_id"] == portfolio_id), None)
    if not p:
        return None
    rows = []
    aum = 0.0
    for h in p["holdings"]:
        q = get_quote(h["ticker"])
        mv = q["last"] * h["quantity"]
        aum += mv
        rows.append({**q, "quantity": h["quantity"], "market_value": round(mv, 2)})
    for r in rows:
        r["weight_pct"] = round((r["market_value"] / aum) * 100, 2) if aum > 0 else 0.0
    rows.sort(key=lambda r: -r["weight_pct"])
    return {
        "portfolio_id": p["portfolio_id"], "name": p["name"], "fund_code": p["fund_code"],
        "isin": p["isin"], "mandate": p["mandate"], "currency": p["currency"],
        "aum": round(aum, 2), "holdings": rows, "is_mock": True,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
