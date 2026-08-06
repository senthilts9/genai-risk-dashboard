// tick_engine.cpp
//
// High-throughput tick generation + OHLCV aggregation, mirroring the same
// methodology as backend/app/tick_simulator.py (Poisson arrivals, GBM
// microprice, lognormal-ish volume) but implemented as a tight C++ loop
// instead of vectorized numpy -- this is Session 3's performance module,
// exposed to Python via pybind11 (see the PYBIND11_MODULE block below).
//
// Build modes:
//   g++ -O3 -DBUILD_BENCHMARK_MAIN tick_engine.cpp -o bench && ./bench
//     -> standalone benchmark binary, no Python/pybind11 dependency
//   python setup.py build_ext --inplace
//     -> builds the importable `meridian_cpp_engine` Python extension
//        (requires `pip install pybind11` first; see setup.py)
//
#include <vector>
#include <string>
#include <random>
#include <cmath>
#include <chrono>
#include <unordered_map>
#include <algorithm>

struct Tick {
    int ticker_id;
    double t_seconds;
    double price;
    double volume;
};

struct Bar {
    int ticker_id;
    long bar_id;
    double open, high, low, close;
    double volume;
    long n_trades;
};

// Fast approximate standard normal via the Irwin-Hall method (sum of 12
// uniforms, minus 6). This trades a small amount of distributional accuracy
// (slightly lighter tails than a true Gaussian) for avoiding log()/sin()/
// cos() calls in the hot loop -- the right tradeoff here since the exact
// micro-shape of the innovation distribution isn't the point of a
// throughput benchmark. A production pricing engine would use a proper
// Box-Muller or ziggurat generator instead.
inline double fast_normal(std::mt19937_64 &rng, std::uniform_real_distribution<double> &unif) {
    double s = 0.0;
    for (int i = 0; i < 12; i++) s += unif(rng);
    return s - 6.0;
}

std::vector<Tick> generate_ticks_cpp(int n_tickers, const std::vector<double>& base_prices,
                                      long n_ticks, double trading_seconds, unsigned seed) {
    std::mt19937_64 rng(seed);
    std::uniform_real_distribution<double> unif(0.0, 1.0);
    std::uniform_int_distribution<int> ticker_pick(0, n_tickers - 1);

    std::vector<Tick> ticks;
    ticks.reserve(n_ticks);

    const double sigma_tick = 0.0006;
    double t_cursor = 0.0;
    const double avg_gap = trading_seconds / (double)n_ticks;
    double log_walk = 0.0;

    for (long i = 0; i < n_ticks; i++) {
        double gap = -std::log(unif(rng) + 1e-12) * avg_gap;
        t_cursor += gap;
        int tid = ticker_pick(rng);

        double z = fast_normal(rng, unif);
        log_walk += sigma_tick * z;
        if (log_walk > 0.05) log_walk = 0.05;
        if (log_walk < -0.05) log_walk = -0.05;
        double price = base_prices[tid] * std::exp(log_walk);

        double vol_z = fast_normal(rng, unif);
        double volume = std::round(std::exp(4.0 + (1.1 / 3.4641016) * vol_z));
        if (volume < 1) volume = 1;

        ticks.push_back({tid, t_cursor, price, volume});
    }
    return ticks;
}

std::vector<Bar> aggregate_bars_cpp(const std::vector<Tick>& ticks, double bar_seconds) {
    std::unordered_map<long long, Bar> bars;
    const long long BIG = 1000000000LL;
    bars.reserve(ticks.size() / 200 + 16);

    for (const auto& tk : ticks) {
        long bar_id = (long)(tk.t_seconds / bar_seconds);
        long long key = (long long)tk.ticker_id * BIG + bar_id;
        auto it = bars.find(key);
        if (it == bars.end()) {
            Bar b{tk.ticker_id, bar_id, tk.price, tk.price, tk.price, tk.price, tk.volume, 1};
            bars.emplace(key, b);
        } else {
            Bar &b = it->second;
            if (tk.price > b.high) b.high = tk.price;
            if (tk.price < b.low) b.low = tk.price;
            b.close = tk.price;  // ticks arrive in increasing t order
            b.volume += tk.volume;
            b.n_trades += 1;
        }
    }
    std::vector<Bar> out;
    out.reserve(bars.size());
    for (auto &kv : bars) out.push_back(kv.second);
    return out;
}

#ifdef BUILD_BENCHMARK_MAIN
#include <iostream>
int main() {
    int n_tickers = 12;
    std::vector<double> base_prices = {228.5, 445.2, 178.3, 205.1, 236.8, 585.4, 505.6, 92.15, 108.9, 246.3, 92.7, 82.4};
    long n_ticks = 1000000;
    double trading_seconds = 6.5 * 3600;

    auto t0 = std::chrono::high_resolution_clock::now();
    auto ticks = generate_ticks_cpp(n_tickers, base_prices, n_ticks, trading_seconds, 7);
    auto t1 = std::chrono::high_resolution_clock::now();
    double gen_s = std::chrono::duration<double>(t1 - t0).count();

    auto bars = aggregate_bars_cpp(ticks, 60.0);
    auto t2 = std::chrono::high_resolution_clock::now();
    double agg_s = std::chrono::duration<double>(t2 - t1).count();

    std::cout << "Generated " << ticks.size() << " ticks in " << gen_s << "s ("
              << (long)((double)n_ticks / gen_s) << " ticks/sec)\n";
    std::cout << "Aggregated to " << bars.size() << " bars in " << agg_s << "s ("
              << (long)((double)n_ticks / agg_s) << " ticks/sec)\n";
    double total_s = gen_s + agg_s;
    std::cout << "Total: " << total_s << "s (" << (long)((double)n_ticks / total_s) << " ticks/sec end-to-end)\n";
    return 0;
}
#endif

#ifndef BUILD_BENCHMARK_MAIN
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
namespace py = pybind11;

py::dict run_simulation(int n_tickers, std::vector<double> base_prices, long n_ticks,
                         double trading_seconds, double bar_seconds, unsigned seed) {
    auto t0 = std::chrono::high_resolution_clock::now();
    auto ticks = generate_ticks_cpp(n_tickers, base_prices, n_ticks, trading_seconds, seed);
    auto t1 = std::chrono::high_resolution_clock::now();
    double gen_s = std::chrono::duration<double>(t1 - t0).count();

    auto bars = aggregate_bars_cpp(ticks, bar_seconds);
    auto t2 = std::chrono::high_resolution_clock::now();
    double agg_s = std::chrono::duration<double>(t2 - t1).count();

    py::list bar_list;
    for (auto &b : bars) {
        py::dict d;
        d["ticker_id"] = b.ticker_id; d["bar_id"] = b.bar_id;
        d["open"] = b.open; d["high"] = b.high; d["low"] = b.low; d["close"] = b.close;
        d["volume"] = b.volume; d["n_trades"] = b.n_trades;
        bar_list.append(d);
    }

    py::dict result;
    result["n_ticks"] = (long)ticks.size();
    result["n_bars"] = (long)bars.size();
    result["generation_seconds"] = gen_s;
    result["aggregation_seconds"] = agg_s;
    result["ticks_per_sec_generation"] = (double)n_ticks / gen_s;
    result["ticks_per_sec_total"] = (double)n_ticks / (gen_s + agg_s);
    result["bars"] = bar_list;
    return result;
}

PYBIND11_MODULE(meridian_cpp_engine, m) {
    m.doc() = "Meridian C++ tick generation + OHLCV aggregation engine";
    m.def("run_simulation", &run_simulation,
          py::arg("n_tickers"), py::arg("base_prices"), py::arg("n_ticks"),
          py::arg("trading_seconds"), py::arg("bar_seconds"), py::arg("seed") = 7,
          "Generate n_ticks simulated ticks and aggregate to OHLCV bars, in C++.");
}
#endif
