"""
Wraps the compiled `meridian_cpp_engine` pybind11 extension. If it hasn't
been built (e.g. `pip install pybind11 && python setup.py build_ext
--inplace` wasn't run), falls back to the pure-Python/numpy tick simulator
in tick_simulator.py -- same graceful-degradation pattern used for DuckDB
in tick_simulator.py itself, so the API never hard-fails on a missing
optional/compiled dependency.
"""
from . import mock_market, tick_simulator

TRADING_SECONDS = 6.5 * 3600

try:
    import meridian_cpp_engine
    CPP_AVAILABLE = True
except ImportError:
    CPP_AVAILABLE = False


def run_cpp_simulation(n_ticks: int = 1_000_000, bar_seconds: int = 60, seed: int = 7) -> dict:
    """
    Runs the C++ tick simulation if the compiled extension is available.
    Falls back to the Python/numpy + DuckDB pipeline otherwise, clearly
    labeling which engine actually ran so the UI never overclaims.
    """
    securities = mock_market.SECURITIES
    tickers = list(securities.keys())
    base_prices = [securities[t]["base_price"] for t in tickers]

    if CPP_AVAILABLE:
        result = meridian_cpp_engine.run_simulation(
            n_tickers=len(tickers), base_prices=base_prices, n_ticks=n_ticks,
            trading_seconds=TRADING_SECONDS, bar_seconds=bar_seconds, seed=seed,
        )
        sample_bars = []
        for b in result["bars"][:20]:
            sample_bars.append({
                "ticker": tickers[b["ticker_id"]], "bar": b["bar_id"],
                "open": round(b["open"], 2), "high": round(b["high"], 2),
                "low": round(b["low"], 2), "close": round(b["close"], 2),
                "volume": b["volume"], "n_trades": b["n_trades"],
            })
        return {
            "engine": "cpp (pybind11, meridian_cpp_engine)",
            "n_ticks": result["n_ticks"], "n_bars": result["n_bars"],
            "generation_seconds": round(result["generation_seconds"], 5),
            "aggregation_seconds": round(result["aggregation_seconds"], 5),
            "ticks_per_sec_total": round(result["ticks_per_sec_total"]),
            "sample_bars": sample_bars, "is_mock": True,
        }
    else:
        # Fallback: reuse the existing Python/numpy + DuckDB pipeline
        gen = tick_simulator.generate_ticks(tickers, dict(zip(tickers, base_prices)), n_ticks=n_ticks, seed=seed)
        agg = tick_simulator.aggregate_to_bars(gen["df"], bar_seconds=bar_seconds)
        total_s = gen["generation_seconds"] + agg["aggregation_seconds"]
        return {
            "engine": f"python-fallback ({agg['engine']}) -- meridian_cpp_engine not built, "
                      f"see backend/setup.py",
            "n_ticks": gen["n_ticks"], "n_bars": agg["n_bars"],
            "generation_seconds": gen["generation_seconds"],
            "aggregation_seconds": agg["aggregation_seconds"],
            "ticks_per_sec_total": round(gen["n_ticks"] / total_s) if total_s > 0 else None,
            "sample_bars": agg["bars"].head(20).to_dict(orient="records"),
            "is_mock": True,
        }
