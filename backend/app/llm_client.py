"""
Thin wrapper around the OpenAI API so the risk engine gets clean,
consistent telemetry (latency, token counts, cost) regardless of which
model answered the prompt.

Requires OPENAI_API_KEY to be set in the environment. Never hardcode
the key -- inject it via env var / AWS Secrets Manager / SSM Parameter Store.
"""
import os
import time
from openai import OpenAI
from typing import Tuple

# Rough public per-million-token pricing (USD) used only for the dashboard's
# cost-risk readout. Update these constants if pricing changes -- they are
# not fetched dynamically to keep the demo dependency-free.
PRICING = {
    "gpt-4o":       {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":  {"input": 0.15, "output": 0.60},
    "gpt-4.1":      {"input": 2.00, "output": 8.00},
    "o3-mini":      {"input": 1.10, "output": 4.40},
}
DEFAULT_PRICE = {"input": 2.50, "output": 10.00}

# Meridian system identity — injected on every call so the AI is always
# contextualised to the dashboard and never gives generic "I'm ChatGPT" responses.
SYSTEM_PROMPT = (
    "You are Meridian, an expert AI assistant embedded in a professional risk and "
    "quantitative finance monitoring dashboard used by asset managers and risk teams. "
    "You specialise in: GenAI application risk monitoring (VaR on latency/cost, anomaly "
    "detection, drift, content-safety flags), portfolio analytics (Sharpe, Sortino, "
    "Treynor, Jensen's alpha, beta, VaR/ES, drawdown), volatility models (EWMA/RiskMetrics, "
    "GARCH(1,1)), derivatives pricing (Black-Scholes-Merton + Greeks, CRR binomial tree, "
    "Monte Carlo with antithetic variates), and fixed-income analytics (clean price, "
    "Macaulay/modified duration, convexity, DV01). "
    "Be precise and concise (3-6 sentences unless the user asks for more). "
    "Reference specific numbers from the conversation when available. "
    "Proactively flag risk concerns, outliers, or limit breaches when relevant. "
    "If a question is outside finance/risk/AI, answer helpfully but briefly."
)

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Export it in your environment "
                "or configure it in your AWS deployment (SSM Parameter Store / "
                "Secrets Manager) before starting the server."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def call_model(prompt: str, model: str = "gpt-4o", messages=None) -> Tuple[str, int, int, float]:
    """
    Calls the model and returns (response_text, input_tokens, output_tokens, latency_ms).

    - If `messages` is provided (list of ChatMessage objects), the full thread is
      forwarded to the API with the Meridian system prompt prepended. This enables
      multi-turn interactive chat.
    - Otherwise the single `prompt` is wrapped in the Meridian system prompt.
    """
    client = get_client()
    start = time.perf_counter()

    system_msg = {"role": "system", "content": SYSTEM_PROMPT}

    if messages:
        # Filter to only user/assistant roles — never pass client-supplied system msgs
        thread = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]
        msg_list = [system_msg] + thread
    else:
        msg_list = [system_msg, {"role": "user", "content": prompt}]

    completion = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=msg_list,
    )
    latency_ms = (time.perf_counter() - start) * 1000.0

    text = completion.choices[0].message.content or ""
    input_tokens = completion.usage.prompt_tokens
    output_tokens = completion.usage.completion_tokens
    return text, input_tokens, output_tokens, latency_ms


def ask_copilot(question: str, context: dict = None, model: str = "gpt-4o-mini") -> str:
    """
    Answers a plain-English question about risk/quant metrics, grounded in
    whatever the frontend last computed (portfolio metrics, position
    contributions, option Greeks, etc.) so answers reference the user's
    actual numbers instead of generic textbook explanations.
    """
    import json
    client = get_client()
    system = (
        "You are Meridian's risk copilot, built into a risk & quant monitoring "
        "dashboard used by an asset manager's front office. Answer concisely "
        "(3-6 sentences unless asked for more detail), reference the specific "
        "numbers provided in context when relevant, explain financial/quant "
        "concepts precisely, and flag when a number looks like an outlier or "
        "risk-limit concern. If no context is provided, answer generally."
    )
    user_content = question
    if context:
        user_content += f"\n\nCurrent dashboard context (JSON):\n{json.dumps(context, default=str)}"

    completion = client.chat.completions.create(
        model=model,
        max_tokens=500,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    )
    return completion.choices[0].message.content or ""


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Rough USD cost from the static PRICING table -- for the dashboard's
    cost-risk readout only, not for billing."""
    price = PRICING.get(model, DEFAULT_PRICE)
    return (input_tokens / 1_000_000) * price["input"] + (output_tokens / 1_000_000) * price["output"]
