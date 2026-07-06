"""
Gemini client via the generateContent REST API (no SDK dependency).

Supports:
- google_search grounding tool (Gemini 3: billed per search query, 5k/mo free)
- structured output (responseJsonSchema) combined with tools (Gemini 3 only)
- thinking_level control (falls back gracefully if the field is rejected)
- inline images (base64)

Grounding metadata note: chunk URIs are Google redirect links; the real origin
is exposed in `web.domain` (newer API) or has to be read from `web.title`.
We surface both the redirect URLs and the extracted domains.
"""
import asyncio
import base64
from typing import Any, Dict, List, Optional

import httpx

from ..config import DEFAULT_TIMEOUT_S, env
from .base import LLMResponse, ProviderError, Stopwatch

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _headers() -> Dict[str, str]:
    key = env("GEMINI_API_KEY")
    if not key:
        raise ProviderError("gemini", "GEMINI_API_KEY is not set")
    return {"x-goog-api-key": key, "Content-Type": "application/json"}


def _extract_grounding(candidate: Dict[str, Any]) -> Dict[str, Any]:
    meta = candidate.get("groundingMetadata") or {}
    queries = meta.get("webSearchQueries") or []
    urls: List[str] = []
    domains: List[str] = []
    for chunk in meta.get("groundingChunks") or []:
        web = chunk.get("web") or {}
        uri = web.get("uri")
        if uri:
            urls.append(uri)
        domain = web.get("domain") or web.get("title")
        if domain:
            domains.append(domain)
    return {"queries": len(queries), "urls": urls, "domains": domains}


async def generate(
    model: str,
    prompt: str,
    *,
    system: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    image_mime: str = "image/jpeg",
    json_schema: Optional[Dict[str, Any]] = None,
    use_search: bool = False,
    thinking_level: Optional[str] = "low",
    temperature: Optional[float] = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> LLMResponse:
    parts: List[Dict[str, Any]] = [{"text": prompt}]
    if image_bytes is not None:
        parts.append(
            {
                "inline_data": {
                    "mime_type": image_mime,
                    "data": base64.b64encode(image_bytes).decode("ascii"),
                }
            }
        )

    body: Dict[str, Any] = {"contents": [{"role": "user", "parts": parts}]}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if use_search:
        body["tools"] = [{"google_search": {}}]

    gen_cfg: Dict[str, Any] = {}
    if json_schema is not None:
        gen_cfg["responseMimeType"] = "application/json"
        gen_cfg["responseJsonSchema"] = json_schema
    if temperature is not None:
        gen_cfg["temperature"] = temperature
    if thinking_level:
        gen_cfg["thinkingConfig"] = {"thinkingLevel": thinking_level}
    if gen_cfg:
        body["generationConfig"] = gen_cfg

    url = f"{_BASE}/{model}:generateContent"

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        with Stopwatch() as sw:
            resp = await client.post(url, headers=_headers(), json=body)
            # Some field combos differ across model generations; degrade
            # gracefully instead of failing the whole pipeline.
            if resp.status_code == 400 and "thinkingConfig" in str(body.get("generationConfig", {})):
                body["generationConfig"].pop("thinkingConfig", None)
                resp = await client.post(url, headers=_headers(), json=body)
            if resp.status_code == 400 and json_schema is not None:
                # Retry without structured output; caller parses JSON from text.
                cfg = body.get("generationConfig", {})
                cfg.pop("responseJsonSchema", None)
                cfg.pop("responseMimeType", None)
                resp = await client.post(url, headers=_headers(), json=body)
            # Transient overload/rate-limit: one quick retry beats failing the
            # request (in prod a failure falls back to the much slower v1).
            if resp.status_code in (429, 500, 502, 503, 504):
                await asyncio.sleep(0.7)
                resp = await client.post(url, headers=_headers(), json=body)

    if resp.status_code != 200:
        raise ProviderError("gemini", f"HTTP {resp.status_code}: {resp.text[:500]}", resp.status_code)

    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise ProviderError("gemini", f"no candidates: {str(data)[:300]}")
    cand = candidates[0]
    text_parts = [p.get("text", "") for p in (cand.get("content") or {}).get("parts") or []]
    text = "".join(text_parts)

    usage = data.get("usageMetadata") or {}
    grounding = _extract_grounding(cand)

    return LLMResponse(
        text=text,
        input_tokens=int(usage.get("promptTokenCount") or 0),
        output_tokens=int(usage.get("candidatesTokenCount") or 0)
        + int(usage.get("thoughtsTokenCount") or 0),
        search_queries=grounding["queries"],
        source_urls=grounding["urls"],
        source_domains=grounding["domains"],
        duration_ms=sw.ms,
        raw=data,
    )
