"""
Perplexity Sonar client (OpenAI-compatible chat completions over httpx).

Every Sonar request runs live web retrieval; real source URLs come back in
`search_results`. Structured output via response_format json_schema — note the
first call with a NEW schema can take 10–30s while Perplexity compiles it
(warm up once in evals before timing).
"""
from typing import Any, Dict, List, Optional

import httpx

from ..config import DEFAULT_TIMEOUT_S, env
from .base import LLMResponse, ProviderError, Stopwatch

_URL = "https://api.perplexity.ai/chat/completions"


async def generate(
    model: str,
    prompt: str,
    *,
    system: Optional[str] = None,
    json_schema: Optional[Dict[str, Any]] = None,
    schema_name: str = "result",
    search_context_size: str = "medium",
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> LLMResponse:
    key = env("PERPLEXITY_API_KEY")
    if not key:
        raise ProviderError("perplexity", "PERPLEXITY_API_KEY is not set")

    messages: List[Dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": 2000,  # unbounded defaults occasionally truncate JSON
        "web_search_options": {"search_context_size": search_context_size},
    }
    if json_schema is not None:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": json_schema},
        }

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        with Stopwatch() as sw:
            resp = await client.post(_URL, headers=headers, json=body)

    if resp.status_code != 200:
        raise ProviderError(
            "perplexity", f"HTTP {resp.status_code}: {resp.text[:500]}", resp.status_code
        )

    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise ProviderError("perplexity", f"no choices: {str(data)[:300]}")
    text = (choices[0].get("message") or {}).get("content") or ""

    usage = data.get("usage") or {}
    results = data.get("search_results") or data.get("citations") or []
    urls: List[str] = []
    for r in results:
        if isinstance(r, str):
            urls.append(r)
        elif isinstance(r, dict) and r.get("url"):
            urls.append(r["url"])

    return LLMResponse(
        text=text,
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
        # Sonar bills per request (context-size fee), not per query; keep 1
        # so the eval can count "requests with search".
        search_queries=1,
        source_urls=urls,
        duration_ms=sw.ms,
        raw=data,
    )
