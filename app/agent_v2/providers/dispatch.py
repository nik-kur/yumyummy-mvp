"""Uniform entrypoint over the three LLM providers + cost accounting."""
import json
from typing import Any, Dict, Optional

from ..config import PRICING
from ..schemas import StageUsage
from . import gemini, openai_client, perplexity
from .base import LLMResponse, ProviderError

# gemini-3.5-flash silently disables google_search grounding when
# responseJsonSchema is set (observed 2026-07: 0 search queries on 30/30
# runs; works fine without the schema). For that combo we embed the schema
# in the prompt instead and parse JSON from free text.
_SCHEMA_BREAKS_SEARCH_PREFIXES = ("gemini-3.5",)


async def call_llm(
    provider: str,
    model: str,
    prompt: str,
    *,
    system: Optional[str] = None,
    json_schema: Optional[Dict[str, Any]] = None,
    schema_name: str = "result",
    use_search: bool = False,
    image_bytes: Optional[bytes] = None,
    image_mime: str = "image/jpeg",
) -> LLMResponse:
    if provider == "gemini":
        schema_arg = json_schema
        if (
            use_search
            and json_schema is not None
            and model.startswith(_SCHEMA_BREAKS_SEARCH_PREFIXES)
        ):
            prompt = (
                f"{prompt}\n\nReturn ONLY a JSON object matching this JSON Schema "
                f"(no prose, no markdown fences):\n{json.dumps(json_schema)}"
            )
            schema_arg = None
        return await gemini.generate(
            model,
            prompt,
            system=system,
            json_schema=schema_arg,
            use_search=use_search,
            image_bytes=image_bytes,
            image_mime=image_mime,
            thinking_level="low",
        )
    if provider == "perplexity":
        if image_bytes is not None:
            raise ProviderError("perplexity", "image input not wired for Sonar in v2")
        return await perplexity.generate(
            model,
            prompt,
            system=system,
            json_schema=json_schema,
            schema_name=schema_name,
        )
    if provider == "openai":
        return await openai_client.generate(
            model,
            prompt,
            system=system,
            json_schema=json_schema,
            schema_name=schema_name,
            use_search=use_search,
            image_bytes=image_bytes,
            image_mime=image_mime,
            reasoning_effort="low",
        )
    raise ProviderError(provider, "unknown provider")


def stage_usage(
    stage: str, provider: str, model: str, resp: LLMResponse
) -> StageUsage:
    rates = PRICING.get(model)
    cost = 0.0
    if rates:
        cost = (
            resp.input_tokens / 1e6 * rates.input_per_m
            + resp.output_tokens / 1e6 * rates.output_per_m
            + resp.search_queries * rates.search_per_call
            + rates.request_fee
        )
    return StageUsage(
        stage=stage,
        provider=provider,
        model=model,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
        search_queries=resp.search_queries,
        duration_ms=round(resp.duration_ms, 1),
        cost_usd=round(cost, 6),
    )
