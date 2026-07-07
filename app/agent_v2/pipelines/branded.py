"""
Branded/restaurant pipeline: ONE grounded LLM call with a strict JSON schema.

The provider does the searching inside the same request (Gemini google_search
grounding / Sonar built-in retrieval / OpenAI web_search tool). No agent loop.
"""
import time
from typing import List, Optional

from .. import prompts
from ..config import VariantSpec
from ..llm_schemas import BRANDED_SCHEMA
from ..providers.base import LLMResponse, extract_json
from ..providers.dispatch import call_llm, stage_usage
from ..schemas import Assessment, BrandedResult, Item, V2Result
from .common import (
    domain_of,
    fdc_decompose_fallback,
    format_message,
    is_official_source,
    is_redirect_url,
    macros_sane,
    probe_urls,
    rank_candidates,
    resolve_redirect_urls,
    single_source_url,
    sum_totals,
)


async def _provider_urls(resp: LLMResponse) -> List[str]:
    """Real pages the provider's search layer returned (redirects resolved)."""
    direct = [u for u in resp.source_urls if u and not is_redirect_url(u)]
    redirects = [u for u in resp.source_urls if u and is_redirect_url(u)]
    resolved = await resolve_redirect_urls(redirects) if redirects else []
    return direct + resolved


async def run(
    text: str,
    spec: VariantSpec,
    *,
    intent: str = "product",
    grams: str = "",
    serving_hint: str = "",
    language: str = "ru",
    image_bytes: Optional[bytes] = None,
) -> V2Result:
    t0 = time.perf_counter()
    result = V2Result(intent=intent, variant=spec.variant)

    async def _attempt() -> LLMResponse:
        return await call_llm(
            spec.branded_provider,
            spec.branded_model,
            prompts.branded_user_msg(
                text, grams=grams, serving_hint=serving_hint, language=language
            ),
            system=prompts.BRANDED_SYSTEM,
            json_schema=BRANDED_SCHEMA,
            schema_name="branded_result",
            use_search=True,
            image_bytes=image_bytes,
        )

    resp = await _attempt()
    result.add_stage(
        stage_usage("branded_search", spec.branded_provider, spec.branded_model, resp)
    )
    try:
        branded = BrandedResult.model_validate(extract_json(resp.text))
    except Exception:
        # One retry on malformed/truncated JSON (rare; costs one extra call).
        resp = await _attempt()
        result.add_stage(
            stage_usage("branded_search_retry", spec.branded_provider, spec.branded_model, resp)
        )
        branded = BrandedResult.model_validate(extract_json(resp.text))
    provider_urls = await _provider_urls(resp)
    official = branded.official_domain

    # Probe every candidate we might show (main + per-item) in one parallel
    # sweep: catches hard 404s AND soft 404s (200 + "page not found" body).
    # Ranking: official product page > store/retailer > aggregator > bare
    # homepage. The best LIVE page wins — a store page with the real data
    # beats a brand homepage that has none.
    main_ranked = rank_candidates(branded.source_url, provider_urls, official)[:4]
    item_ranked = {
        i: rank_candidates(bi.source_url, provider_urls, official)[:3]
        for i, bi in enumerate(branded.items)
    }
    to_probe = list(dict.fromkeys(main_ranked + [u for r in item_ranked.values() for u in r]))
    alive = await probe_urls(to_probe)

    def first_alive(ranked: List[str]) -> Optional[str]:
        for u in ranked:
            if alive.get(u):
                return u
        return None

    items: List[Item] = []
    for i, bi in enumerate(branded.items):
        items.append(
            Item(
                name=bi.name,
                grams=bi.grams or None,
                calories_kcal=round(bi.calories_kcal, 1),
                protein_g=round(bi.protein_g, 1),
                fat_g=round(bi.fat_g, 1),
                carbs_g=round(bi.carbs_g, 1),
                source_url=first_alive(item_ranked[i]),
            )
        )
    result.items = items
    result.totals = sum_totals(items)

    confidence = branded.confidence if branded.confidence in ("HIGH", "ESTIMATE") else "ESTIMATE"
    source_url = first_alive(main_ranked)
    if not source_url:
        # Model sometimes cites per-item only; promote a unanimous item URL.
        item_urls = {i.source_url for i in items if i.source_url}
        if len(item_urls) == 1:
            source_url = next(iter(item_urls))

    note = branded.note or ""
    decomposed = False
    if items and not source_url and not any(i.source_url for i in items):
        # Nothing verifiable online at all (no-name dish, obscure product):
        # map to USDA generic foods so every line still carries a source.
        dec_items, dec_stage, dec_hits = await fdc_decompose_fallback(
            items, spec, language
        )
        if dec_stage is not None:
            result.add_stage(dec_stage)
        if dec_items:
            items = dec_items
            result.items = items
            result.totals = sum_totals(items)
            source_url = single_source_url(items)
            confidence = "ESTIMATE"  # grams are assumed, not from a source
            decomposed = True
            note = (note + " " if note else "") + (
                f"{dec_hits}/{len(items)} items matched to USDA FoodData Central."
            )

    # A claimed HIGH without any provider-confirmed page is suspect: the model
    # answered from memory. Keep the URL but downgrade confidence.
    if confidence == "HIGH" and not provider_urls and resp.search_queries == 0:
        confidence = "ESTIMATE"
    # HIGH requires a verifiable link — downgrade otherwise (mirrors v1 rules).
    if confidence == "HIGH" and not source_url:
        confidence = "ESTIMATE"
    # Atwater consistency guard on totals.
    t = result.totals
    if confidence == "HIGH" and not macros_sane(t.calories_kcal, t.protein_g, t.fat_g, t.carbs_g):
        confidence = "ESTIMATE"

    result.confidence = confidence
    result.source_url = source_url

    verified = sum(1 for i in items if i.source_url)
    if decomposed:
        method, dom = "usda_components", "fdc.nal.usda.gov"
    elif source_url and is_official_source(source_url, official):
        method, dom = "official", domain_of(source_url)
    elif source_url or verified:
        method, dom = "web", domain_of(source_url or "") or None
    else:
        method, dom = "estimate", None
    result.assessment = Assessment(
        method=method,
        domain=dom,
        # Grams from a text request come from the model unless the user stated
        # them; decomposition always assumes component weights.
        portion_estimated=decomposed,
        verified_items=verified,
        total_items=len(items),
    )

    # Expose provider-verified domains for eval scoring (grounding metadata).
    cited_domains = sorted(
        {d for d in ([domain_of(u) for u in provider_urls] + resp.source_domains) if d}
    )
    src_label = domain_of(source_url or "")
    if not src_label and any(i.source_url for i in items):
        src_label = "fdc.nal.usda.gov" if decomposed else "per-item links"
    result.message_text = format_message(
        result.totals,
        confidence,
        note=note,
        source=src_label or "none",
    )
    result.total_duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    result.cited_domains = cited_domains
    return result
