"""
Advisor pipeline: one grounded call that either recommends 3 options, answers
an analysis question about the user's own diary, or politely redirects an
off-topic request. The model self-classifies via `answer_kind`.
"""
import time
from typing import Optional

from .. import prompts
from ..config import VariantSpec
from ..llm_schemas import ADVISOR_SCHEMA
from ..providers.base import extract_json
from ..providers.dispatch import call_llm, stage_usage
from ..schemas import AdvisorResult, Item, Totals, V2Result

# Map the model's self-classification to the wire `intent` the client reads.
_KIND_TO_INTENT = {
    "recommendation": "food_advice",
    "analysis": "nutrition_qa",
    "offtopic": "advisor_offtopic",
}


async def run(
    text: str,
    spec: VariantSpec,
    *,
    nutrition_context: str = "",
    history_context: str = "",
    conversation_context: str = "",
    image_bytes: Optional[bytes] = None,
) -> V2Result:
    t0 = time.perf_counter()
    result = V2Result(intent="food_advice", variant=spec.variant)

    resp = await call_llm(
        spec.branded_provider,
        spec.branded_model,
        prompts.advisor_user_msg(
            text, nutrition_context, history_context, conversation_context
        ),
        system=prompts.ADVISOR_SYSTEM,
        json_schema=ADVISOR_SCHEMA,
        schema_name="advisor_result",
        use_search=True,
        image_bytes=image_bytes,
    )
    result.add_stage(stage_usage("advisor", spec.branded_provider, spec.branded_model, resp))

    advisor = AdvisorResult.model_validate(extract_json(resp.text))
    kind = (advisor.answer_kind or "recommendation").lower()
    result.intent = _KIND_TO_INTENT.get(kind, "food_advice")

    # Only recommendations carry option cards; analysis/offtopic are text-only.
    if kind == "recommendation":
        result.items = [
            Item(
                name=o.name,
                calories_kcal=round(o.calories_kcal, 1),
                protein_g=round(o.protein_g, 1),
                fat_g=round(o.fat_g, 1),
                carbs_g=round(o.carbs_g, 1),
                source_url=o.source_url or None,
            )
            for o in advisor.items[:3]
        ]
        if result.items:
            best = result.items[0]
            result.totals = Totals(
                calories_kcal=best.calories_kcal,
                protein_g=best.protein_g,
                fat_g=best.fat_g,
                carbs_g=best.carbs_g,
            )
        result.confidence = "ESTIMATE"
        result.source_url = advisor.source_url or None

    result.message_text = advisor.message_text
    result.total_duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    return result
