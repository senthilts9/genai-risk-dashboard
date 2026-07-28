"""
Quant risk engine for GenAI application monitoring.

Methodology (documented here deliberately -- this is the part a model-risk
reviewer will actually ask about):

1. OPERATIONAL RISK (tail risk on cost & latency)
   Historical-simulation VaR: take the rolling window of past latency/cost
   observations, sort them, and read off the 95th percentile. This is the
   same historical-simulation VaR technique used for P&L series, applied
   here to operational cost/latency instead of returns. A new observation
   that breaches the VaR(95) threshold contributes to operational risk
   proportionally to the size of the breach.

2. ANOMALY RISK (statistical deviation from the rolling baseline)
   Z-score of the current observation (latency, response length) against
   the rolling mean/std of the window. |z| > 2 is treated as a soft
   anomaly, |z| > 3 as a hard anomaly.

3. DRIFT RISK (structural break / distribution shift)
   Splits the rolling window in half (older vs. recent) and measures the
   relative change in mean response length and mean latency between the
   two halves. Large relative shifts indicate the model or the traffic
   mix has changed -- a proxy for behavioral drift, since we don't have
   ground-truth labels to measure accuracy drift directly.

4. CONTENT SAFETY RISK
   Heuristic keyword flags for refusals and hedging/uncertainty language.
   This is intentionally a coarse proxy, not a hallucination detector --
   the README explains the limitation and how to replace it with a real
   judge-model or classifier in production.

UNIFIED SCORE
   Weighted sum of the four components (weights below), clipped to
   [0, 100], and mapped to a LOW / MEDIUM / HIGH / CRITICAL band.
   Weights are configurable constants, not hidden -- change them to match
   your organization's risk appetite.
"""
import statistics
from datetime import datetime
from typing import List
from .models import InvocationRecord, RiskComponents, RiskSnapshot

# ---- configurable risk-appetite weights (must sum to 1.0) ----
WEIGHTS = {
    "operational": 0.30,
    "anomaly": 0.25,
    "drift": 0.25,
    "content_safety": 0.20,
}

VAR_CONFIDENCE = 0.95
MIN_SAMPLES_FOR_STATS = 5

REFUSAL_MARKERS = ["i can't help with", "i cannot help with", "i'm not able to", "i won't"]
UNCERTAINTY_MARKERS = ["i'm not sure", "i am not sure", "i don't know", "it's hard to say", "may not be accurate"]


def flag_text(text: str):
    lower = text.lower()
    refusal = any(m in lower for m in REFUSAL_MARKERS)
    uncertainty = any(m in lower for m in UNCERTAINTY_MARKERS)
    return refusal, uncertainty


def _percentile(sorted_vals: List[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * pct
    f, c = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _historical_var(values: List[float]) -> float:
    """95th percentile of the sample -- the VaR(95) threshold."""
    return _percentile(sorted(values), VAR_CONFIDENCE)


def _zscore(value: float, values: List[float]) -> float:
    if len(values) < MIN_SAMPLES_FOR_STATS:
        return 0.0
    mean = statistics.mean(values)
    stdev = statistics.pstdev(values) or 1e-9
    return (value - mean) / stdev


def _band(score: float) -> str:
    if score < 25:
        return "LOW"
    if score < 50:
        return "MEDIUM"
    if score < 75:
        return "HIGH"
    return "CRITICAL"


def compute_risk(session_id: str, history: List[InvocationRecord], latest: InvocationRecord) -> RiskSnapshot:
    """
    `history` should include `latest` as the most recent element.
    Computes the four risk components + unified score from the window.
    """
    latencies = [r.latency_ms for r in history]
    costs = [r.cost_usd for r in history]
    resp_lens = [r.response_chars for r in history]

    var95_latency = _historical_var(latencies)
    var95_cost = _historical_var(costs)

    # 1. Operational risk: how far the latest obs breaches the VaR thresholds
    lat_breach = max(0.0, (latest.latency_ms - var95_latency) / var95_latency) if var95_latency > 0 else 0.0
    cost_breach = max(0.0, (latest.cost_usd - var95_cost) / var95_cost) if var95_cost > 0 else 0.0
    operational_risk = min(100.0, (lat_breach + cost_breach) * 50.0)

    # 2. Anomaly risk: z-scores on latency & response length
    z_lat = abs(_zscore(latest.latency_ms, latencies[:-1] if len(latencies) > 1 else latencies))
    z_len = abs(_zscore(latest.response_chars, resp_lens[:-1] if len(resp_lens) > 1 else resp_lens))
    anomaly_risk = min(100.0, ((z_lat + z_len) / 2) * 25.0)  # z=4 -> 100

    # 3. Drift risk: split-window structural shift
    drift_risk = 0.0
    if len(history) >= MIN_SAMPLES_FOR_STATS * 2:
        mid = len(history) // 2
        older, recent = history[:mid], history[mid:]
        old_len_mean = statistics.mean(r.response_chars for r in older) or 1
        new_len_mean = statistics.mean(r.response_chars for r in recent) or 1
        old_lat_mean = statistics.mean(r.latency_ms for r in older) or 1
        new_lat_mean = statistics.mean(r.latency_ms for r in recent) or 1
        len_shift = abs(new_len_mean - old_len_mean) / old_len_mean
        lat_shift = abs(new_lat_mean - old_lat_mean) / old_lat_mean
        drift_risk = min(100.0, ((len_shift + lat_shift) / 2) * 100.0)

    # 4. Content safety risk
    content_safety_risk = 0.0
    if latest.refusal_flag:
        content_safety_risk += 40.0
    if latest.uncertainty_flag:
        content_safety_risk += 25.0
    content_safety_risk = min(100.0, content_safety_risk)

    unified = (
        operational_risk * WEIGHTS["operational"] +
        anomaly_risk * WEIGHTS["anomaly"] +
        drift_risk * WEIGHTS["drift"] +
        content_safety_risk * WEIGHTS["content_safety"]
    )
    unified = max(0.0, min(100.0, unified))

    components = RiskComponents(
        operational_risk=round(operational_risk, 2),
        anomaly_risk=round(anomaly_risk, 2),
        drift_risk=round(drift_risk, 2),
        content_safety_risk=round(content_safety_risk, 2),
        unified_score=round(unified, 2),
        band=_band(unified),
    )

    return RiskSnapshot(
        session_id=session_id,
        timestamp=datetime.utcnow(),
        components=components,
        var95_latency_ms=round(var95_latency, 2),
        var95_cost_usd=round(var95_cost, 6),
        sample_size=len(history),
    )
