"""
Barcode pipeline: OpenFoodFacts direct lookup (no LLM), grounded fallback.

Reuses the existing OFF client from app/external (read-only import — that
module has no side effects and only depends on httpx).
"""
import re
import time
from typing import Optional

from app.external.openfoodfacts_client import fetch_product_by_barcode

from ..config import VariantSpec
from ..schemas import Assessment, Item, StageUsage, V2Result
from . import branded as branded_pipeline
from .common import format_message, sum_totals

_BARCODE_RE = re.compile(r"\b(\d{8,14})\b")


def extract_barcode(text: str) -> Optional[str]:
    m = _BARCODE_RE.search(text or "")
    return m.group(1) if m else None


async def run(
    text: str,
    spec: VariantSpec,
    *,
    grams: str = "",
    serving_hint: str = "",
    language: str = "ru",
) -> V2Result:
    t0 = time.perf_counter()
    result = V2Result(intent="barcode", variant=spec.variant)

    barcode = extract_barcode(text)
    product = None
    if barcode:
        off_t0 = time.perf_counter()
        product = await fetch_product_by_barcode(barcode)
        result.add_stage(
            StageUsage(
                stage="off_lookup",
                provider="openfoodfacts",
                duration_ms=round((time.perf_counter() - off_t0) * 1000, 1),
            )
        )

    if product is None:
        # OFF miss -> one grounded call, same as a branded text request.
        sub = await branded_pipeline.run(
            text,
            spec,
            intent="barcode",
            grams=grams,
            serving_hint=serving_hint,
            language=language,
        )
        sub.stages = result.stages + sub.stages
        sub.total_duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        sub.intent = "barcode"
        return sub

    nutr = product.get("nutriments") or {}
    kcal100 = float(nutr.get("energy-kcal_100g") or (float(nutr.get("energy_100g") or 0) / 4.184))
    protein100 = float(nutr.get("proteins_100g") or 0)
    fat100 = float(nutr.get("fat_100g") or 0)
    carbs100 = float(nutr.get("carbohydrates_100g") or 0)

    serving = 0.0
    if grams:
        try:
            serving = float(grams)
        except ValueError:
            serving = 0.0
    if serving <= 0:
        sq = product.get("serving_quantity")
        try:
            serving = float(sq) if sq else 0.0
        except (TypeError, ValueError):
            serving = 0.0
    serving_assumed = serving <= 0
    if serving <= 0:
        serving = 100.0

    k = serving / 100.0
    name = product.get("product_name") or product.get("generic_name") or f"Product {barcode}"
    brand = product.get("brands") or ""
    display = f"{brand} {name}".strip()
    url = f"https://world.openfoodfacts.org/product/{barcode}"

    item = Item(
        name=display,
        grams=serving,
        calories_kcal=round(kcal100 * k, 1),
        protein_g=round(protein100 * k, 1),
        fat_g=round(fat100 * k, 1),
        carbs_g=round(carbs100 * k, 1),
        source_url=url,
    )
    result.items = [item]
    result.totals = sum_totals(result.items)
    result.confidence = "HIGH"
    result.source_url = url
    result.assessment = Assessment(
        method="off",
        domain="openfoodfacts.org",
        portion_estimated=serving_assumed,
        verified_items=1,
        total_items=1,
    )
    result.message_text = format_message(
        result.totals,
        "HIGH",
        note=f"Serving: {serving:.0f} g/ml (OpenFoodFacts data).",
        source="openfoodfacts.org",
    )
    result.total_duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    return result
