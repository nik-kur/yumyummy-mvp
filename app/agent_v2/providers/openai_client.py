"""
OpenAI control-variant client (Responses API, single call).

Used to answer "would one capped web_search call on our current vendor already
be enough?" — isolating the win of the new topology from the provider switch.
"""
import base64
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from ..config import DEFAULT_TIMEOUT_S, env
from .base import LLMResponse, ProviderError, Stopwatch

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        key = env("OPENAI_API_KEY")
        if not key:
            raise ProviderError("openai", "OPENAI_API_KEY is not set")
        _client = AsyncOpenAI(api_key=key, timeout=DEFAULT_TIMEOUT_S)
    return _client


async def generate(
    model: str,
    prompt: str,
    *,
    system: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    image_mime: str = "image/jpeg",
    json_schema: Optional[Dict[str, Any]] = None,
    schema_name: str = "result",
    use_search: bool = False,
    reasoning_effort: str = "low",
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> LLMResponse:
    client = _get_client()

    content: List[Dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    if image_bytes is not None:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:{image_mime};base64,{b64}",
                "detail": "auto",
            }
        )

    kwargs: Dict[str, Any] = {
        "model": model,
        "input": [{"role": "user", "content": content}],
        "reasoning": {"effort": reasoning_effort},
        "timeout": timeout_s,
    }
    if system:
        kwargs["instructions"] = system
    if use_search:
        kwargs["tools"] = [{"type": "web_search"}]
    if json_schema is not None:
        kwargs["text"] = {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": json_schema,
                "strict": False,
            }
        }

    with Stopwatch() as sw:
        try:
            resp = await client.responses.create(**kwargs)
        except Exception as e:  # surface as ProviderError for uniform handling
            raise ProviderError("openai", str(e)[:500])

    search_calls = 0
    urls: List[str] = []
    for item in resp.output or []:
        itype = getattr(item, "type", "")
        if itype == "web_search_call":
            action = getattr(item, "action", None)
            action_type = getattr(action, "type", None) if action else None
            if action_type in (None, "search"):
                search_calls += 1
        elif itype == "message":
            for part in getattr(item, "content", []) or []:
                for ann in getattr(part, "annotations", []) or []:
                    url = getattr(ann, "url", None)
                    if url:
                        urls.append(url)

    usage = getattr(resp, "usage", None)
    return LLMResponse(
        text=resp.output_text or "",
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        search_queries=search_calls,
        source_urls=urls,
        duration_ms=sw.ms,
        raw=None,  # SDK objects serialize noisily; evals don't need the raw dump
    )
