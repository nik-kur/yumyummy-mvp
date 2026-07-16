"""
Production adapter: exposes Agent v2 under the exact contract of
run_yumyummy_workflow(), so /app/agent/run can switch engines behind a
feature flag without the client noticing any shape difference.

- force_intent=None        -> intent="auto" (engine routes: barcode/photo/parse)
- force_intent="advice"    -> food_advice (mobile advisor tab)
- force_intent="edit_meal" -> UnsupportedIntentError (caller falls back to v1)
- returns the WorkflowRunResponse dict + "_usage" in the v1 billing shape.
"""
import os
from typing import Any, Dict, List, Optional

from . import engine
from .schemas import V2Result

_INTENT_MAP = {
    "": "auto",
    "advice": "food_advice",
    "food_advice": "food_advice",
    "log_meal": "log_meal",
    "eatout": "eatout",
    "product": "product",
    "barcode": "barcode",
    "photo_meal": "photo_meal",
}


class UnsupportedIntentError(Exception):
    """Raised for intents v2 does not implement (e.g. edit_meal)."""


def _usage_payload(res: V2Result) -> Dict[str, Any]:
    """Build the v1-shaped usage summary record_usage_for_user() expects."""
    models: Dict[str, Dict[str, int]] = {}
    input_tokens = output_tokens = web_search_calls = requests = 0
    model_costs: Dict[str, float] = {}
    for st in res.stages:
        if st.model:
            bucket = models.setdefault(
                st.model,
                {"requests": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            )
            bucket["requests"] += 1
            bucket["input_tokens"] += st.input_tokens
            bucket["output_tokens"] += st.output_tokens
            bucket["total_tokens"] += st.input_tokens + st.output_tokens
            model_costs[st.model] = round(model_costs.get(st.model, 0.0) + st.cost_usd, 6)
            requests += 1
        input_tokens += st.input_tokens
        output_tokens += st.output_tokens
        web_search_calls += st.search_queries

    return {
        "requests": requests,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "web_search_calls": web_search_calls,
        "models": models,
        "cost": {
            "model_costs_usd": model_costs,
            "model_cost_total_usd": res.total_cost_usd,
            "web_search_cost_usd": 0.0,  # search is bundled in provider pricing
            "estimated_total_cost_usd": res.total_cost_usd,
        },
        "engine": f"v2:{res.variant}",
    }


async def run_v2_workflow(
    user_text: str,
    telegram_id: Optional[str] = None,
    image_url: Optional[str] = None,
    image_urls: Optional[List[str]] = None,
    force_intent: Optional[str] = None,
    nutrition_context: Optional[str] = None,
    history_context: Optional[str] = None,
    conversation_context: Optional[str] = None,
    variant: Optional[str] = None,
) -> dict:
    intent = _INTENT_MAP.get((force_intent or "").strip().lower())
    if intent is None:
        raise UnsupportedIntentError(f"agent v2 does not support intent={force_intent!r}")

    variant = variant or os.getenv("AGENT_V2_VARIANT", "v2g")
    res = await engine.run(
        intent,
        user_text or "",
        variant=variant,
        image_url=image_url,
        image_urls=image_urls,
        nutrition_context=nutrition_context or "",
        history_context=history_context or "",
        conversation_context=conversation_context or "",
    )
    if res.error:
        # Surface as an exception so the endpoint's try/except can fall back to v1.
        raise RuntimeError(f"agent v2 failed: {res.error}")

    out = res.to_v1_dict()
    out["_usage"] = _usage_payload(res)
    return out
