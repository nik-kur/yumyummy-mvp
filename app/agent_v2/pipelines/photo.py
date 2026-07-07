"""
Photo pipeline: ONE vision call -> (optionally) USDA verification -> answer.

Modes (eval subvariants):
  a — pure model estimate (Cal AI style)
  b — model identifies items, USDA FDC supplies macros for generic items (default)
  c — like b, plus a grounded branded lookup when a brand is clearly visible
"""
import asyncio
import time
from typing import Optional

from .. import prompts
from ..config import VariantSpec
from ..llm_schemas import PARSE_SCHEMA
from ..providers.base import extract_json
from ..providers.dispatch import call_llm, stage_usage
from ..schemas import ParseResult, StageUsage, V2Result
from . import branded as branded_pipeline
from .common import (
    _estimate_item,
    format_message,
    single_source_url,
    sum_totals,
    fdc_resolve_all,
)


async def run(
    image_bytes: bytes,
    spec: VariantSpec,
    *,
    caption: str = "",
    grams: str = "",
    serving_hint: str = "",
    mode: str = "b",
    image_mime: str = "image/jpeg",
) -> V2Result:
    t0 = time.perf_counter()
    result = V2Result(intent="photo_meal", variant=spec.variant)

    resp = await call_llm(
        spec.photo_provider,
        spec.photo_model,
        prompts.photo_user_msg(caption, grams=grams, serving_hint=serving_hint),
        system=prompts.PHOTO_SYSTEM,
        json_schema=PARSE_SCHEMA,
        schema_name="parse_result",
        image_bytes=image_bytes,
        image_mime=image_mime,
    )
    result.add_stage(stage_usage("photo_vision", spec.photo_provider, spec.photo_model, resp))

    parsed = ParseResult.model_validate(extract_json(resp.text))

    label_n = 0
    if mode == "a":
        items = [_estimate_item(p, p.grams if p.grams > 0 else 100.0) for p in parsed.items]
        fdc_hits = 0
    else:
        # Items whose numbers were READ off the photo (label / menu screenshot,
        # complete for the portion) are final: no FDC, no web lookup — exactly
        # what the user sees printed is what gets logged.
        label_items = [p for p in parsed.items if p.nutrition_source == "label"]
        rest = [p for p in parsed.items if p.nutrition_source != "label"]
        # label_partial + branded -> verify online; otherwise FDC/estimate.
        generic_parsed = [p for p in rest if not p.is_branded]
        branded_parsed = [p for p in rest if p.is_branded]

        items = [_estimate_item(p, p.grams if p.grams > 0 else 100.0) for p in label_items]
        label_n = len(items)

        fdc_hits = 0
        if generic_parsed:
            fdc_t0 = time.perf_counter()
            fdc_items, fdc_hits = await fdc_resolve_all(generic_parsed)
            items.extend(fdc_items)
            result.add_stage(
                StageUsage(
                    stage="fdc_lookup",
                    provider="fdc",
                    duration_ms=round((time.perf_counter() - fdc_t0) * 1000, 1),
                )
            )

        if branded_parsed:
            if mode == "c":
                # One grounded lookup PER brand, in parallel. A combined query
                # for several brands has no single official page, so search
                # drifts to aggregators; per-brand queries each rank their own
                # official domain first. Capped to bound cost/latency.
                lookups = branded_parsed[:3]
                extra = branded_parsed[3:]
                subs = await asyncio.gather(
                    *(
                        branded_pipeline.run(
                            f"Nutrition for: {p.brand} {p.name} ~{p.grams:.0f} g".strip(),
                            spec,
                            intent="photo_meal",
                        )
                        for p in lookups
                    )
                )
                for p, sub in zip(lookups, subs):
                    result.stages.extend(sub.stages)
                    result.total_cost_usd = round(result.total_cost_usd + sub.total_cost_usd, 6)
                    if sub.items and not sub.error:
                        items.extend(sub.items)
                    else:  # lookup failed — keep the vision estimate
                        items.append(_estimate_item(p, p.grams if p.grams > 0 else 100.0))
                items.extend(
                    _estimate_item(p, p.grams if p.grams > 0 else 100.0) for p in extra
                )
            else:
                items.extend(
                    _estimate_item(p, p.grams if p.grams > 0 else 100.0) for p in branded_parsed
                )

    result.items = items
    result.totals = sum_totals(items)
    # Fully-read labels are facts, not visual guesses -> HIGH confidence.
    all_from_label = bool(parsed.items) and label_n == len(parsed.items)
    result.confidence = "HIGH" if all_from_label else "ESTIMATE"
    result.source_url = single_source_url(items)

    note_bits = [f"mode={mode}"]
    if label_n:
        note_bits.append(f"{label_n} item(s) read from the label/menu in the photo.")
    if fdc_hits:
        note_bits.append(f"{fdc_hits} item(s) matched to USDA FoodData Central.")
    if parsed.note:
        note_bits.append(parsed.note)
    result.message_text = format_message(
        result.totals,
        result.confidence,
        note=" ".join(note_bits),
        source="photo label" if label_n else ("fdc.nal.usda.gov" if fdc_hits else "none"),
    )
    result.total_duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    return result
