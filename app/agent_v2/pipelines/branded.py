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
from ..schemas import BrandedResult, Item, V2Result
from .common import (
    choose_source_url,
    domain_of,
    format_message,
    is_redirect_url,
    macros_sane,
    resolve_redirect_urls,
    sum_totals,
    url_alive_quick,
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

    items: List[Item] = []
    for bi in branded.items:
        items.append(
            Item(
                name=bi.name,
                grams=bi.grams or None,
                calories_kcal=round(bi.calories_kcal, 1),
                protein_g=round(bi.protein_g, 1),
                fat_g=round(bi.fat_g, 1),
                carbs_g=round(bi.carbs_g, 1),
                source_url=choose_source_url(bi.source_url, provider_urls, official),
            )
        )
    result.items = items
    result.totals = sum_totals(items)

    confidence = branded.confidence if branded.confidence in ("HIGH", "ESTIMATE") else "ESTIMATE"
    source_url = choose_source_url(branded.source_url, provider_urls, official)
    # A model-typed URL the search layer didn't confirm may be hallucinated:
    # one cheap HEAD probe, fall back to the best confirmed page if dead.
    if source_url and source_url not in provider_urls:
        if not await url_alive_quick(source_url):
            source_url = choose_source_url("", provider_urls, official)
    if not source_url:
        # Model sometimes cites per-item only; promote a unanimous item URL.
        item_urls = {i.source_url for i in items if i.source_url}
        if len(item_urls) == 1:
            source_url = next(iter(item_urls))
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

    # Expose provider-verified domains for eval scoring (grounding metadata).
    cited_domains = sorted(
        {d for d in ([domain_of(u) for u in provider_urls] + resp.source_domains) if d}
    )
    note = branded.note or ""
    result.message_text = format_message(
        result.totals,
        confidence,
        note=note,
        source=domain_of(source_url or "") or "none",
    )
    result.total_duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    result.cited_domains = cited_domains
    return result
