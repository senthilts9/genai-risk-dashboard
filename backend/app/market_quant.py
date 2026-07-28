"""
Quant Lab models: market data access + the full set of models referenced in
the FRM Part I quick-sheet that are actually computable from price data.

Sections:
  1. Market data          -- yfinance with a synthetic-GBM fallback so the
                              app still works with no internet / rate limits
  2. Portfolio risk & performance
                           -- CAPM beta, Sharpe/Treynor/Sortino/Jensen/IR,
                              historical + parametric (delta-normal) VaR/ES,
                              max drawdown, skew/kurtosis
  3. Volatility models     -- EWMA (RiskMetrics) and GARCH(1,1) (MLE-fit)
  4. Derivatives pricing   -- Black-Scholes-Merton (+ Greeks), CRR binomial
                              tree (European & American), Monte Carlo pricer
                              (+ Monte Carlo VaR via full repricing)
  5. Fixed income          -- clean/dirty price, Macaulay/modified duration,
                              convexity, DV01

Each function is a direct implementation of the formula it's named after --
see README.md / the in-app Model Library tab for when to use which one.
"""
import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import minimize
from datetime import datetime, timedelta

TRADING_DAYS = 252


# ============================================================
# 1. MARKET DATA
# ============================================================

def fetch_price_history(tickers, period="1y"):
    """
    Returns a DataFrame of adjusted close prices, columns = tickers.
    Falls back to a synthetic geometric Brownian motion series per ticker
    if yfinance can't reach the network (offline dev, rate limit, etc.) so
    the rest of the app always has something to compute on -- clearly
    flagged via the returned `is_mock` boolean.
    """
    try:
        import yfinance as yf
        data = yf.download(tickers, period=period, progress=False, auto_adjust=True)
        if isinstance(data.columns, pd.MultiIndex):
            prices = data["Close"]
        else:
            prices = data[["Close"]]
            prices.columns = tickers if isinstance(tickers, list) else [tickers]
        prices = prices.dropna(how="all")
        if prices.empty or prices.isna().all().all():
            raise ValueError("empty response")
        return prices.ffill().dropna(), False
    except Exception:
        return _mock_price_history(tickers, period), True


def _mock_price_history(tickers, period="1y"):
    """Synthetic GBM price paths, seeded per-ticker so results are stable."""
    tickers = tickers if isinstance(tickers, list) else [tickers]
    n_days = {"1mo": 21, "3mo": 63, "6mo": 126, "1y": 252, "2y": 504}.get(period, 252)
    dates = pd.bdate_range(end=datetime.utcnow(), periods=n_days)
    out = {}
    for i, t in enumerate(tickers):
        rng = np.random.default_rng(abs(hash(t)) % (2**32))
        mu, sigma = 0.08, 0.20 + 0.05 * (i % 3)  # vary vol a bit per ticker
        dt = 1 / TRADING_DAYS
        shocks = rng.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt), n_days)
        prices = 100 * np.exp(np.cumsum(shocks))
        out[t] = prices
    return pd.DataFrame(out, index=dates)


# ============================================================
# 2. PORTFOLIO RISK & PERFORMANCE
# ============================================================

def portfolio_returns(prices: pd.DataFrame, weights: dict) -> pd.Series:
    rets = prices.pct_change().dropna()
    w = np.array([weights.get(c, 0.0) for c in rets.columns])
    if w.sum() > 0:
        w = w / w.sum()
    return (rets * w).sum(axis=1)


def compute_portfolio_metrics(prices: pd.DataFrame, weights: dict,
                               benchmark: pd.Series = None, rf_annual: float = 0.04,
                               var_confidence: float = 0.95) -> dict:
    port_ret = portfolio_returns(prices, weights)
    rf_daily = rf_annual / TRADING_DAYS

    ann_return = port_ret.mean() * TRADING_DAYS
    ann_vol = port_ret.std() * np.sqrt(TRADING_DAYS)

    excess = port_ret - rf_daily
    sharpe = (excess.mean() / port_ret.std()) * np.sqrt(TRADING_DAYS) if port_ret.std() > 0 else 0.0

    downside = port_ret[port_ret < rf_daily]
    downside_dev = downside.std() * np.sqrt(TRADING_DAYS) if len(downside) > 1 else 1e-9
    sortino = (ann_return - rf_annual) / downside_dev if downside_dev > 0 else 0.0

    beta, treynor, jensen_alpha, info_ratio = None, None, None, None
    if benchmark is not None:
        bench_ret = benchmark.pct_change().dropna()
        aligned = pd.concat([port_ret, bench_ret], axis=1, join="inner").dropna()
        aligned.columns = ["p", "b"]
        if len(aligned) > 5 and aligned["b"].var() > 0:
            cov = np.cov(aligned["p"], aligned["b"])[0, 1]
            beta = cov / aligned["b"].var()
            bench_ann_return = aligned["b"].mean() * TRADING_DAYS
            treynor = (ann_return - rf_annual) / beta if beta != 0 else None
            jensen_alpha = ann_return - (rf_annual + beta * (bench_ann_return - rf_annual))
            tracking_error = (aligned["p"] - aligned["b"]).std() * np.sqrt(TRADING_DAYS)
            info_ratio = (ann_return - bench_ann_return) / tracking_error if tracking_error > 0 else None

    # Historical VaR / ES (nonparametric -- ranked empirical losses)
    losses = -port_ret.dropna().values
    var_hist = np.percentile(losses, var_confidence * 100)
    tail_losses = losses[losses >= var_hist]
    es_hist = tail_losses.mean() if len(tail_losses) > 0 else var_hist

    # Delta-normal (parametric) VaR / ES -- assumes normally distributed returns
    z = norm.ppf(var_confidence)
    mu, sigma = port_ret.mean(), port_ret.std()
    var_param = -(mu - z * sigma)
    es_param = -(mu - sigma * (norm.pdf(z) / (1 - var_confidence)))

    # Max drawdown
    cum = (1 + port_ret).cumprod()
    running_max = cum.cummax()
    drawdown = (cum - running_max) / running_max
    max_drawdown = drawdown.min()

    skew = port_ret.skew()
    kurt = port_ret.kurt()  # pandas returns *excess* kurtosis already

    return {
        "ann_return": round(float(ann_return), 4),
        "ann_volatility": round(float(ann_vol), 4),
        "sharpe_ratio": round(float(sharpe), 4),
        "sortino_ratio": round(float(sortino), 4),
        "capm_beta": round(float(beta), 4) if beta is not None else None,
        "treynor_measure": round(float(treynor), 4) if treynor is not None else None,
        "jensen_alpha": round(float(jensen_alpha), 4) if jensen_alpha is not None else None,
        "information_ratio": round(float(info_ratio), 4) if info_ratio is not None else None,
        "var_historical": round(float(var_hist), 4),
        "es_historical": round(float(es_hist), 4),
        "var_parametric": round(float(var_param), 4),
        "es_parametric": round(float(es_param), 4),
        "max_drawdown": round(float(max_drawdown), 4),
        "skewness": round(float(skew), 4),
        "excess_kurtosis": round(float(kurt), 4),
        "confidence": var_confidence,
        "daily_returns": [round(float(r), 6) for r in port_ret.values],
    }


def position_contributions(prices: pd.DataFrame, weights: dict) -> list:
    """
    Drill-down from portfolio -> position. For each holding, computes its
    standalone annualized return/vol plus its Marginal Contribution to Risk
    (MCTR) and Component Contribution to Risk (CCTR):

        MCTR_i = (Cov @ w)_i / sigma_p          (per-unit-weight risk sensitivity)
        CCTR_i = w_i * MCTR_i                     (this position's slice of portfolio vol)
        %CCTR_i = CCTR_i / sigma_p                (sums to 100% across positions)

    This is the standard risk-budgeting decomposition -- it's how a desk
    answers "which position is actually driving my portfolio risk," which
    is not the same question as "which position is biggest by weight."
    """
    rets = prices.pct_change().dropna()
    tickers = list(rets.columns)
    w = np.array([weights.get(t, 0.0) for t in tickers])
    w = w / w.sum() if w.sum() > 0 else w

    cov = rets.cov().values * TRADING_DAYS  # annualized covariance
    port_var = w @ cov @ w
    port_vol = np.sqrt(max(port_var, 1e-12))

    mctr = (cov @ w) / port_vol
    cctr = w * mctr
    pct_cctr = cctr / port_vol

    out = []
    for i, t in enumerate(tickers):
        ann_ret = rets[t].mean() * TRADING_DAYS
        ann_vol = rets[t].std() * np.sqrt(TRADING_DAYS)
        out.append({
            "ticker": t,
            "weight": round(float(w[i]), 4),
            "ann_return": round(float(ann_ret), 4),
            "ann_volatility": round(float(ann_vol), 4),
            "marginal_contribution_to_risk": round(float(mctr[i]), 4),
            "component_contribution_to_risk": round(float(cctr[i]), 4),
            "pct_of_portfolio_risk": round(float(pct_cctr[i]) * 100, 2),
        })
    out.sort(key=lambda x: -x["pct_of_portfolio_risk"])
    return out


def monte_carlo_var(prices: pd.DataFrame, weights: dict, n_sims: int = 5000,
                     horizon_days: int = 1, var_confidence: float = 0.95,
                     dist: str = "normal", seed: int = 42) -> dict:
    """
    Monte Carlo VaR: fit mean/covariance from historical returns, simulate
    n_sims correlated scenarios via Cholesky decomposition, fully reprice
    the (linear) portfolio under each scenario, then take the tail
    percentile of simulated P&L. Unlike delta-normal VaR this can be
    extended to nonlinear/option payoffs by repricing instruments directly
    inside the simulation loop instead of using returns.
    """
    rng = np.random.default_rng(seed)
    rets = prices.pct_change().dropna()
    tickers = list(rets.columns)
    w = np.array([weights.get(t, 0.0) for t in tickers])
    w = w / w.sum() if w.sum() > 0 else w

    mu = rets.mean().values
    cov = rets.cov().values
    L = np.linalg.cholesky(cov + np.eye(len(cov)) * 1e-12)

    if dist == "t":
        dof = 5
        z = rng.standard_t(dof, size=(n_sims, len(tickers))) / np.sqrt(dof / (dof - 2))
    else:
        z = rng.standard_normal((n_sims, len(tickers)))

    sim_returns = mu * horizon_days + (z @ L.T) * np.sqrt(horizon_days)
    port_sim_returns = sim_returns @ w
    losses = -port_sim_returns

    var = np.percentile(losses, var_confidence * 100)
    es = losses[losses >= var].mean()

    return {
        "var_monte_carlo": round(float(var), 4),
        "es_monte_carlo": round(float(es), 4),
        "n_sims": n_sims,
        "horizon_days": horizon_days,
        "distribution": dist,
        "confidence": var_confidence,
    }


# ============================================================
# 3. VOLATILITY MODELS
# ============================================================

def ewma_volatility(returns: np.ndarray, lam: float = 0.94) -> np.ndarray:
    """EWMA (RiskMetrics): sigma_n^2 = lam*sigma_{n-1}^2 + (1-lam)*r_{n-1}^2"""
    var = np.zeros(len(returns))
    var[0] = returns[0] ** 2
    for i in range(1, len(returns)):
        var[i] = lam * var[i - 1] + (1 - lam) * returns[i - 1] ** 2
    return np.sqrt(var * TRADING_DAYS)  # annualized


def garch_11_fit(returns: np.ndarray):
    """
    Fits a GARCH(1,1) via MLE (Gaussian innovations):
        sigma_n^2 = omega + alpha*r_{n-1}^2 + beta*sigma_{n-1}^2
    Returns (omega, alpha, beta, long_run_variance, conditional_vol_series).
    """
    returns = returns - returns.mean()

    def neg_log_lik(params):
        omega, alpha, beta = params
        if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 1:
            return 1e10
        n = len(returns)
        var = np.zeros(n)
        var[0] = np.var(returns)
        ll = 0.0
        for t in range(1, n):
            var[t] = omega + alpha * returns[t - 1] ** 2 + beta * var[t - 1]
            if var[t] <= 0:
                return 1e10
            ll += -0.5 * (np.log(2 * np.pi) + np.log(var[t]) + returns[t] ** 2 / var[t])
        return -ll

    x0 = [np.var(returns) * 0.05, 0.08, 0.88]
    res = minimize(neg_log_lik, x0, method="Nelder-Mead",
                    options={"xatol": 1e-8, "fatol": 1e-8, "maxiter": 2000})
    omega, alpha, beta = res.x
    long_run_var = omega / (1 - alpha - beta) if (alpha + beta) < 1 else np.var(returns)

    n = len(returns)
    cond_var = np.zeros(n)
    cond_var[0] = np.var(returns)
    for t in range(1, n):
        cond_var[t] = omega + alpha * returns[t - 1] ** 2 + beta * cond_var[t - 1]

    return {
        "omega": float(omega), "alpha": float(alpha), "beta": float(beta),
        "long_run_annual_vol": float(np.sqrt(long_run_var * TRADING_DAYS)),
        "persistence": float(alpha + beta),
        "conditional_vol_annualized": (np.sqrt(cond_var * TRADING_DAYS)).tolist(),
    }


def volatility_models(prices: pd.DataFrame, weights: dict, lam: float = 0.94) -> dict:
    port_ret = portfolio_returns(prices, weights).values
    ewma = ewma_volatility(port_ret, lam)
    garch = garch_11_fit(port_ret)
    return {
        "ewma_lambda": lam,
        "ewma_vol_annualized": [round(float(v) * 100, 3) for v in ewma],
        "garch": {
            "omega": round(garch["omega"], 8),
            "alpha": round(garch["alpha"], 4),
            "beta": round(garch["beta"], 4),
            "persistence": round(garch["persistence"], 4),
            "long_run_annual_vol_pct": round(garch["long_run_annual_vol"] * 100, 3),
            "conditional_vol_annualized_pct": [round(v * 100, 3) for v in garch["conditional_vol_annualized"]],
        },
    }


# ============================================================
# 4. DERIVATIVES PRICING
# ============================================================

def black_scholes(S, X, T, r, sigma, q=0.0):
    """Black-Scholes-Merton with continuous dividend yield q. Returns price + Greeks for call & put."""
    d1 = (np.log(S / X) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    call = S * np.exp(-q * T) * norm.cdf(d1) - X * np.exp(-r * T) * norm.cdf(d2)
    put = X * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)

    call_delta = np.exp(-q * T) * norm.cdf(d1)
    put_delta = np.exp(-q * T) * (norm.cdf(d1) - 1)
    gamma = np.exp(-q * T) * norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T) / 100  # per 1% vol move
    call_theta = (-S * np.exp(-q * T) * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                  - r * X * np.exp(-r * T) * norm.cdf(d2)
                  + q * S * np.exp(-q * T) * norm.cdf(d1)) / 365
    put_theta = (-S * np.exp(-q * T) * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                 + r * X * np.exp(-r * T) * norm.cdf(-d2)
                 - q * S * np.exp(-q * T) * norm.cdf(-d1)) / 365
    call_rho = X * T * np.exp(-r * T) * norm.cdf(d2) / 100
    put_rho = -X * T * np.exp(-r * T) * norm.cdf(-d2) / 100

    return {
        "call_price": round(float(call), 4), "put_price": round(float(put), 4),
        "call_delta": round(float(call_delta), 4), "put_delta": round(float(put_delta), 4),
        "gamma": round(float(gamma), 6), "vega": round(float(vega), 4),
        "call_theta_per_day": round(float(call_theta), 4), "put_theta_per_day": round(float(put_theta), 4),
        "call_rho": round(float(call_rho), 4), "put_rho": round(float(put_rho), 4),
        "d1": round(float(d1), 4), "d2": round(float(d2), 4),
    }


def binomial_tree(S, X, T, r, sigma, n_steps=200, option_type="call", american=False, q=0.0):
    """Cox-Ross-Rubinstein binomial tree. Supports American early exercise."""
    dt = T / n_steps
    u = np.exp(sigma * np.sqrt(dt))
    d = 1 / u
    pu = (np.exp((r - q) * dt) - d) / (u - d)
    pd_ = 1 - pu
    disc = np.exp(-r * dt)

    prices = S * u ** np.arange(n_steps, -1, -1) * d ** np.arange(0, n_steps + 1)
    if option_type == "call":
        values = np.maximum(prices - X, 0.0)
    else:
        values = np.maximum(X - prices, 0.0)

    for step in range(n_steps - 1, -1, -1):
        values = disc * (pu * values[:-1] + pd_ * values[1:])
        if american:
            spot = S * u ** np.arange(step, -1, -1) * d ** np.arange(0, step + 1)
            intrinsic = np.maximum(spot - X, 0.0) if option_type == "call" else np.maximum(X - spot, 0.0)
            values = np.maximum(values, intrinsic)

    return {
        "price": round(float(values[0]), 4),
        "n_steps": n_steps, "u": round(float(u), 5), "d": round(float(d), 5),
        "risk_neutral_prob_up": round(float(pu), 5),
        "option_type": option_type, "exercise_style": "american" if american else "european",
    }


def monte_carlo_option(S, X, T, r, sigma, option_type="call", n_sims=20000, q=0.0, seed=42):
    """European option pricing via Monte Carlo with antithetic variates for variance reduction."""
    rng = np.random.default_rng(seed)
    half = n_sims // 2
    z = rng.standard_normal(half)
    z = np.concatenate([z, -z])  # antithetic variates

    ST = S * np.exp((r - q - 0.5 * sigma**2) * T + sigma * np.sqrt(T) * z)
    payoff = np.maximum(ST - X, 0.0) if option_type == "call" else np.maximum(X - ST, 0.0)
    disc_payoff = np.exp(-r * T) * payoff

    price = disc_payoff.mean()
    std_err = disc_payoff.std(ddof=1) / np.sqrt(len(disc_payoff))

    return {
        "price": round(float(price), 4),
        "standard_error": round(float(std_err), 5),
        "ci_95": [round(float(price - 1.96 * std_err), 4), round(float(price + 1.96 * std_err), 4)],
        "n_sims": n_sims, "option_type": option_type,
        "variance_reduction": "antithetic_variates",
    }


# ============================================================
# 5. FIXED INCOME
# ============================================================

def bond_analytics(face_value, coupon_rate, ytm, years_to_maturity, freq=2):
    """
    Clean price, Macaulay & modified duration, convexity, DV01 for a plain
    vanilla coupon bond, all from discounting the cash-flow schedule
    directly (not the linearized shortcuts) so duration/convexity are
    computed as true weighted averages / curvature, matching the FRM
    formulas: D = -(1/P)(dP/dy), C = (1/P)(d^2P/dy^2).
    """
    n_periods = int(round(years_to_maturity * freq))
    coupon = face_value * coupon_rate / freq
    y = ytm / freq
    t = np.arange(1, n_periods + 1)
    cash_flows = np.full(n_periods, coupon)
    cash_flows[-1] += face_value

    disc_factors = (1 + y) ** (-t)
    pv_cfs = cash_flows * disc_factors
    price = pv_cfs.sum()

    macaulay_duration = (t * pv_cfs).sum() / price / freq  # in years
    modified_duration = macaulay_duration / (1 + y)

    convexity = ((t * (t + 1)) * pv_cfs).sum() / (price * (1 + y) ** 2) / (freq ** 2)

    dv01 = modified_duration * price * 0.0001  # price change per 1bp

    # bump-and-reprice check (finite difference) for transparency/validation
    def reprice(dy):
        y2 = y + dy / freq
        return (cash_flows * (1 + y2) ** (-t)).sum()

    p_up, p_down = reprice(0.0001), reprice(-0.0001)
    dv01_fd = (p_down - p_up) / 2

    return {
        "clean_price": round(float(price), 4),
        "macaulay_duration": round(float(macaulay_duration), 4),
        "modified_duration": round(float(modified_duration), 4),
        "convexity": round(float(convexity), 4),
        "dv01_analytical": round(float(dv01), 4),
        "dv01_finite_difference": round(float(dv01_fd), 4),
        "n_periods": n_periods, "period_coupon": round(float(coupon), 4),
    }
