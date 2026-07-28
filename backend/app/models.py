"""
Data models for the GenAI Risk Dashboard.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChatMessage(BaseModel):
    role: str = Field(..., description="one of: user, assistant, system")
    content: str = Field(..., min_length=1)


class InvokeRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    model: str = Field(default="gpt-4o-mini")
    session_id: str = Field(default="default")
    messages: Optional[List[ChatMessage]] = Field(
        default=None,
        description="Full conversation history for multi-turn chat. "
                    "When provided, the prompt field is still required for telemetry "
                    "but the model receives the full messages list."
    )


class InvocationRecord(BaseModel):
    id: Optional[int] = None
    session_id: str
    timestamp: datetime
    model: str
    prompt_chars: int
    response_chars: int
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float
    refusal_flag: bool
    uncertainty_flag: bool
    response_preview: str


class RiskComponents(BaseModel):
    operational_risk: float       # latency/cost tail risk (historical VaR based)
    anomaly_risk: float           # statistical deviation from rolling baseline
    drift_risk: float             # structural shift between recent vs baseline window
    content_safety_risk: float    # refusal / uncertainty language heuristics
    unified_score: float          # weighted composite, 0-100
    band: str                     # LOW / MEDIUM / HIGH / CRITICAL


class RiskSnapshot(BaseModel):
    session_id: str
    timestamp: datetime
    components: RiskComponents
    var95_latency_ms: float
    var95_cost_usd: float
    sample_size: int


class InvokeResponse(BaseModel):
    record: InvocationRecord
    risk: RiskSnapshot
    response_text: str


class HistoryResponse(BaseModel):
    records: List[InvocationRecord]
    risk_history: List[RiskSnapshot]


# ---------------- Quant Lab models ----------------

class PortfolioRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=1, max_length=15)
    weights: dict = Field(..., description="ticker -> weight, need not be pre-normalized")
    benchmark: str = Field(default="SPY")
    period: str = Field(default="1y")
    rf_annual: float = Field(default=0.04)
    var_confidence: float = Field(default=0.95, ge=0.5, le=0.999)


class MonteCarloVarRequest(PortfolioRequest):
    n_sims: int = Field(default=5000, ge=100, le=50000)
    horizon_days: int = Field(default=1, ge=1, le=60)
    distribution: str = Field(default="normal")


class OptionRequest(BaseModel):
    spot: float
    strike: float
    time_to_maturity: float = Field(..., description="in years")
    risk_free_rate: float = Field(default=0.045)
    volatility: float
    dividend_yield: float = Field(default=0.0)
    option_type: str = Field(default="call")


class BinomialRequest(OptionRequest):
    n_steps: int = Field(default=200, ge=1, le=2000)
    american: bool = Field(default=False)


class MonteCarloOptionRequest(OptionRequest):
    n_sims: int = Field(default=20000, ge=1000, le=200000)


class BondRequest(BaseModel):
    face_value: float = Field(default=1000)
    coupon_rate: float
    ytm: float
    years_to_maturity: float
    freq: int = Field(default=2, description="coupon payments per year")


class SavePortfolioRequest(BaseModel):
    session_id: str = Field(default="default")
    name: str
    tickers: List[str]
    weights: dict
    benchmark: str = Field(default="SPY")
    period: str = Field(default="1y")


class CopilotRequest(BaseModel):
    question: str
    context: Optional[dict] = Field(default=None, description="latest computed risk/portfolio metrics, if any")
    model: str = Field(default="gpt-4o-mini")


class VisitRequest(BaseModel):
    visitor_id: str
    user_agent: Optional[str] = ""
