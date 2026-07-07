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
from ..schemas import Assessment, ParseResult, StageUsage, V2Result
from . import branded as branded_pipeline
from .common import (
    _estimate_item,
    domain_of,
    fdc_decompose_fallback,
    fdc_resolve_all,
    format_message,
    single_source_url,
    sum_totals,
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
            result.add_stage(
                StageUsage(
                    stage="fdc_lookup",
                    provider="fdc",
                    duration_ms=round((time.perf_counter() - fdc_t0) * 1000, 1),
                )
            )
            # Visually-estimated composite dishes (dressed salads, stews...)
            # get no direct USDA match: decompose into components so they
            # still carry links. Items with printed label data stay as read.
            pairs = list(zip(fdc_items, generic_parsed))
            to_dec = [
                it for it, p in pairs
                if not it.source_url and p.nutrition_source == "estimate"
            ]
            kept = [
                it for it, p in pairs
                if it.source_url or p.nutrition_source != "estimate"
            ]
            if to_dec:
                dec_items, dec_stage, dec_hits = await fdc_decompose_fallback(
                    to_dec, spec, parsed.language
                )
                if dec_stage is not None:
                    result.add_stage(dec_stage)
                if dec_items:
                    fdc_items = kept + dec_items
                    fdc_hits += dec_hits
            items.extend(fdc_items)

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

    # Label lines carry no URL but ARE verified (numbers read off the photo).
    verified = min(len(items), label_n + sum(1 for i in items if i.source_url))
    if all_from_label:
        method, dom = "label", None
    elif verified:
        method = "photo"
        dom = (
            domain_of(result.source_url)
            if result.source_url
            else ("fdc.nal.usda.gov" if fdc_hits else None)
        )
    else:
        method, dom = "estimate", None
    result.assessment = Assessment(
        method=method,
        domain=dom,
        portion_estimated=not all_from_label,
        verified_items=verified,
        total_items=len(items),
    )

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


async def run_multi(
    images: list,
    spec: VariantSpec,
    *,
    caption: str = "",
    grams: str = "",
    serving_hint: str = "",
    mode: str = "b",
    image_mime: str = "image/jpeg",
) -> V2Result:
    """
    Multi-photo meal (25(1)+): each photo goes through the normal single-photo
    pipeline in parallel, then items/totals/usage are merged into one result.
    The caption is shared across photos (it describes the meal as a whole).
    """
    if len(images) == 1:
        return await run(
            images[0], spec, caption=caption, grams=grams,
            serving_hint=serving_hint, mode=mode, image_mime=image_mime,
        )

    t0 = time.perf_counter()
    subs = await asyncio.gather(
        *(
            run(
                img, spec, caption=caption, grams=grams,
                serving_hint=serving_hint, mode=mode, image_mime=image_mime,
            )
            for img in images
        )
    )
    good = [s for s in subs if not s.error]
    if not good:
        return subs[0]

    merged = V2Result(intent="photo_meal", variant=spec.variant)
    for s in good:
        merged.items.extend(s.items)
        merged.stages.extend(s.stages)
        merged.total_cost_usd = round(merged.total_cost_usd + s.total_cost_usd, 6)
        merged.cited_domains = sorted(set(merged.cited_domains) | set(s.cited_domains))
    merged.totals = sum_totals(merged.items)
    merged.confidence = "HIGH" if all(s.confidence == "HIGH" for s in good) else "ESTIMATE"
    merged.source_url = single_source_url(merged.items)

    sub_a = [s.assessment for s in good if s.assessment]
    verified = sum(a.verified_items for a in sub_a)
    total = sum(a.total_items for a in sub_a)
    if sub_a and all(a.method == "label" for a in sub_a):
        method, dom = "label", None
    elif verified:
        method = "photo"
        dom = domain_of(merged.source_url) if merged.source_url else None
        if not dom and any(a.domain == "fdc.nal.usda.gov" for a in sub_a):
            dom = "fdc.nal.usda.gov"
    else:
        method, dom = "estimate", None
    merged.assessment = Assessment(
        method=method,
        domain=dom,
        portion_estimated=any(a.portion_estimated for a in sub_a) if sub_a else True,
        verified_items=verified,
        total_items=total,
    )

    note = f"{len(good)} photo(s) analyzed."
    if len(good) < len(subs):
        note += f" {len(subs) - len(good)} photo(s) failed and were skipped."
    merged.message_text = format_message(
        merged.totals, merged.confidence, note=note,
        source=dom or ("photo label" if method == "label" else "none"),
    )
    merged.total_duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    return merged
