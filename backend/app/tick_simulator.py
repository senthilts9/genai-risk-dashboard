"""
Tick-data simulator: generates realistic (simulated, not live) high-frequency
tick data at scale, as the foundation for the DuckDB and KDB-X tick-store
benchmarks.

Methodology:
  - Trade arrival times: Poisson process (exponential inter-arrival times) --
    real trades cluster randomly through the session, they don't land on an
    evenly-spaced grid.
  - Microprice: geometric Brownian motion between ticks, same model used
    elsewhere in this app for mock daily prices, just applied at tick
    resolution.
  - Bid/ask: a small spread around microprice with realistic tick-size
    rounding (0.01 for equities).
  - Trade side: random buy/sell.
  - Volume: lognormal (most trades are small, a few are large -- matches the
    right-skewed shape of real order-size distributions).

Everything here is fully vectorized with numpy (no per-tick Python loop),
which is what makes generating a million rows a sub-second operation instead
of a multi-minute one.
"""
import time
import numpy as np
import pandas as pd

TRADING_SECONDS = 6.5 * 3600  # a standard NYSE session, in seconds


def generate_ticks(tickers: list, base_prices: dict, n_ticks: int = 1_000_000, seed: int = 7) -> dict:
    """
    Generates `n_ticks` simulated trades spread across `tickers` over one
    simulated trading session. Returns the DataFrame plus timing info.
    """
    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)

    n_tickers = len(tickers)
    ticker_idx = rng.integers(0, n_tickers, size=n_ticks)

    # Poisson arrivals: exponential inter-arrival gaps, cumsum -> arrival times,
    # then rescaled to fit exactly inside one trading session and sorted.
    gaps = rng.exponential(scale=1.0, size=n_ticks)
    arrival_raw = np.cumsum(gaps)
    arrival_seconds = arrival_raw / arrival_raw[-1] * TRADING_SECONDS
    arrival_seconds.sort()  # re-sort after the per-ticker shuffle below

    # Shuffle which ticker each arrival belongs to (arrivals across all
    # tickers interleave in real time, not grouped ticker-by-ticker)
    order = rng.permutation(n_ticks)
    ticker_idx = ticker_idx[order]

    base = np.array([base_prices[t] for t in tickers])[ticker_idx]

    # GBM microprice path per tick, vectorized: cumulative log-return walk,
    # reset per ticker isn't tracked individually here (this is a simulation
    # for volume/throughput benchmarking, not a precise per-security path --
    # each tick's price is base * small multiplicative random walk step)
    sigma_tick = 0.0006
    steps = rng.normal(0, sigma_tick, size=n_ticks)
    log_walk = np.cumsum(steps) - np.cumsum(steps)[0]
    # bound the walk so it doesn't drift unrealistically far over a million ticks
    log_walk = np.clip(log_walk, -0.05, 0.05)
    price = np.round(base * np.exp(log_walk), 2)

    spread = np.round(price * 0.0003 + 0.01, 2)
    side = rng.choice([-1, 1], size=n_ticks)
    volume = np.round(rng.lognormal(mean=4.0, sigma=1.1, size=n_ticks)).astype(int)
    volume = np.clip(volume, 1, None)

    df = pd.DataFrame({
        "ticker": np.array(tickers)[ticker_idx],
        "t_seconds": arrival_seconds,
        "price": price,
        "bid": price - spread / 2,
        "ask": price + spread / 2,
        "side": np.where(side == 1, "BUY", "SELL"),
        "volume": volume,
    })
    gen_time_s = time.perf_counter() - t0

    return {"df": df, "n_ticks": n_ticks, "generation_seconds": round(gen_time_s, 4)}


def aggregate_to_bars(df: pd.DataFrame, bar_seconds: int = 60) -> dict:
    """
    Aggregates raw ticks into OHLCV bars. Tries DuckDB first (the intended
    production engine for this -- vectorized columnar SQL, no separate
    server process needed); falls back to a pandas groupby if DuckDB isn't
    installed in this environment, so the endpoint never hard-fails on a
    missing optional dependency.
    """
    t0 = time.perf_counter()
    engine = "duckdb"
    try:
        import duckdb
        df = df.copy()
        df["bar"] = (df["t_seconds"] // bar_seconds).astype(int)
        bars = duckdb.sql("""
            SELECT ticker, bar,
                   FIRST(price ORDER BY t_seconds) AS open,
                   MAX(price) AS high,
                   MIN(price) AS low,
                   LAST(price ORDER BY t_seconds) AS close,
                   SUM(volume) AS volume,
                   COUNT(*) AS n_trades
            FROM df
            GROUP BY ticker, bar
            ORDER BY ticker, bar
        """).df()
    except ImportError:
        engine = "pandas (duckdb not installed -- add `duckdb` to requirements.txt for the intended engine)"
        df = df.copy()
        df["bar"] = (df["t_seconds"] // bar_seconds).astype(int)
        grouped = df.sort_values("t_seconds").groupby(["ticker", "bar"])
        bars = grouped.agg(
            open=("price", "first"), high=("price", "max"), low=("price", "min"),
            close=("price", "last"), volume=("volume", "sum"), n_trades=("price", "count"),
        ).reset_index()

    agg_time_s = time.perf_counter() - t0
    return {
        "bars": bars, "n_bars": len(bars), "engine": engine,
        "aggregation_seconds": round(agg_time_s, 4),
    }
