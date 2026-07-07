"""
Generic (no-brand) text pipeline: one parse call -> USDA FDC -> deterministic math.
"""
import time
from typing import Optional

from .. import prompts
from ..config import VariantSpec
from ..llm_schemas import PARSE_SCHEMA
from ..providers.base import extract_json
from ..providers.dispatch import call_llm, stage_usage
from ..schemas import ParseResult, StageUsage, V2Result
from .common import (
    fdc_decompose_fallback,
    fdc_resolve_all,
    format_message,
    single_source_url,
    sum_totals,
)


async def run(
    text: str,
    spec: VariantSpec,
    *,
    grams: str = "",
    serving_hint: str = "",
    parsed: Optional[ParseResult] = None,
    parse_stage: Optional[StageUsage] = None,
) -> V2Result:
    """`parsed`/`parse_stage` let the auto-router reuse its own parse call
    instead of paying for a second one."""
    t0 = time.perf_counter()
    result = V2Result(intent="log_meal", variant=spec.variant)

    if parsed is None:
        hints = ", ".join(x for x in [f"amount: {grams} g" if grams else "", serving_hint] if x)
        resp = await call_llm(
            spec.parse_provider,
            spec.parse_model,
            prompts.parse_user_msg(text, hints),
            system=prompts.PARSE_SYSTEM,
            json_schema=PARSE_SCHEMA,
            schema_name="parse_result",
        )
        parse_stage = stage_usage("parse", spec.parse_provider, spec.parse_model, resp)
        parsed = ParseResult.model_validate(extract_json(resp.text))
    if parse_stage is not None:
        result.add_stage(parse_stage)

    fdc_t0 = time.perf_counter()
    items, fdc_hits = await fdc_resolve_all(parsed.items)
    result.add_stage(
        StageUsage(
            stage="fdc_lookup",
            provider="fdc",
            duration_ms=round((time.perf_counter() - fdc_t0) * 1000, 1),
        )
    )

    # Composite dishes (сырники, хачапури...) have no single USDA equivalent
    # and end up linkless — decompose them into components so each line still
    # carries a verifiable USDA link.
    decomposed = False
    unlinked = [i for i in items if not i.source_url]
    if unlinked:
        dec_items, dec_stage, dec_hits = await fdc_decompose_fallback(
            unlinked, spec, parsed.language
        )
        if dec_stage is not None:
            result.add_stage(dec_stage)
        if dec_items:
            items = [i for i in items if i.source_url] + dec_items
            fdc_hits += dec_hits
            decomposed = True

    result.items = items
    result.totals = sum_totals(items)
    all_explicit = bool(parsed.items) and all(p.explicit_grams for p in parsed.items)
    result.confidence = (
        "HIGH"
        if (all_explicit and fdc_hits == len(items) and not decomposed)
        else "ESTIMATE"
    )
    result.source_url = single_source_url(items)

    note_bits = []
    if fdc_hits:
        note_bits.append(f"{fdc_hits}/{len(items)} items matched to USDA FoodData Central.")
    if parsed.note:
        note_bits.append(parsed.note)
    result.message_text = format_message(
        result.totals,
        result.confidence,
        note=" ".join(note_bits),
        source="fdc.nal.usda.gov" if fdc_hits else "none",
    )
    result.total_duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    return result
