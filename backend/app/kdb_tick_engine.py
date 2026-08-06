"""
KDB-X / q tick store integration via PyKX (KX's official Python interface).

HONESTY NOTE, read before trusting this in production: this module is
written against KDB-X's current documented Python API
(code.kx.com/kdb-x/learn/kdb-x-python-overview.html, verified via a live
doc search while building this) but has NOT been executed anywhere in this
project's development environment. Two things were unavailable while
building it: network access (to `pip install pykx` and download KDB-X
itself) and a KDB-X license (KX gives out free personal/Community licenses,
but the signup at kx.com is an interactive, personal step -- it can't be
automated or completed on someone else's behalf). The C++ engine in this
same codebase (cpp_tick_engine.py) WAS compiled and benchmarked for real;
this one wasn't, and that distinction matters. Test against a real KDB-X
install before relying on the numbers this produces. Until you do, the
Python-fallback path below is what actually runs.

One-time setup on your own machine:
  1. pip install pykx
  2. Get a free personal KDB-X license: https://kx.com/kdb-x-community-download/
  3. python -c "import pykx as kx"   # follow the interactive license prompts
  4. Restart the backend -- KDB_AVAILABLE flips to True automatically once
     both the import and a live q call succeed.
"""
import os
import time
import pandas as pd
from . import mock_market, tick_simulator

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "kdb", "schema.q")
_schema_loaded = False

try:
    import pykx as kx
    # Import succeeding only means the package is installed -- it does NOT
    # mean a valid license is present (unlicensed mode has no embedded q).
    # Confirm with a trivial live call before trusting it.
    kx.q("1+1")
    KDB_AVAILABLE = True
except Exception:
    KDB_AVAILABLE = False


def _ensure_schema():
    global _schema_loaded
    if _schema_loaded:
        return
    kx.q(f"\\l {SCHEMA_PATH}")
    _schema_loaded = True


def _q_timespan_literal(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"0D{h:02d}:{m:02d}:{s:02d}"


def run_kdb_simulation(n_ticks: int = 1_000_000, bar_seconds: int = 60, seed: int = 7) -> dict:
    """
    Generates ticks with the same numpy generator used elsewhere (KDB-X's
    value-add here is the STORE + QUERY side -- bulk insert and `xbar`
    aggregation -- not tick generation itself, so isolating that keeps the
    comparison against the C++/DuckDB benchmarks fair), then times a bulk
    insert into a kdb+ table and an OHLCV aggregation query.
    """
    securities = mock_market.SECURITIES
    tickers = list(securities.keys())
    base_prices = {t: s["base_price"] for t, s in securities.items()}

    gen = tick_simulator.generate_ticks(tickers, base_prices, n_ticks=n_ticks, seed=seed)
    df = gen["df"].copy()
    base_ts = pd.Timestamp("2026-01-01 09:30:00")
    df["time"] = base_ts + pd.to_timedelta(df["t_seconds"], unit="s")
    df["sym"] = df["ticker"]
    df = df[["time", "sym", "price", "volume"]]

    if not KDB_AVAILABLE:
        agg = tick_simulator.aggregate_to_bars(gen["df"], bar_seconds=bar_seconds)
        total_s = gen["generation_seconds"] + agg["aggregation_seconds"]
        return {
            "engine": "python-fallback -- pykx not installed/licensed; see "
                      "backend/app/kdb_tick_engine.py docstring for setup",
            "n_ticks": gen["n_ticks"], "n_bars": agg["n_bars"],
            "generation_seconds": gen["generation_seconds"],
            "insert_seconds": None,
            "query_seconds": agg["aggregation_seconds"],
            "ticks_per_sec_total": round(gen["n_ticks"] / total_s) if total_s > 0 else None,
            "is_mock": True, "verified_by_execution": False,
        }

    _ensure_schema()
    kx.q("clearTicks[]")

    t0 = time.perf_counter()
    kx.q("insertTicks", kx.toq(df))
    insert_s = time.perf_counter() - t0

    bar_span = kx.q(_q_timespan_literal(bar_seconds))
    t1 = time.perf_counter()
    bars = kx.q("ohlcvBars", bar_span)
    query_s = time.perf_counter() - t1

    bars_df = bars.pd().reset_index()
    total_s = gen["generation_seconds"] + insert_s + query_s

    return {
        "engine": "kdb-x (pykx, q `xbar` aggregation)",
        "n_ticks": gen["n_ticks"], "n_bars": len(bars_df),
        "generation_seconds": gen["generation_seconds"],
        "insert_seconds": round(insert_s, 5),
        "query_seconds": round(query_s, 5),
        "ticks_per_sec_total": round(gen["n_ticks"] / total_s) if total_s > 0 else None,
        "is_mock": True, "verified_by_execution": False,  # flip manually once you've tested it live
        "sample_bars": bars_df.head(20).to_dict(orient="records"),
    }
