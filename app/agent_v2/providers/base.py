"""Shared plumbing for provider clients."""
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LLMResponse:
    """Normalized response from any provider."""
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    search_queries: int = 0
    # Real source URLs surfaced by the provider (citations / grounding chunks).
    source_urls: List[str] = field(default_factory=list)
    # Domains extracted from grounding metadata when full URLs are redirects.
    source_domains: List[str] = field(default_factory=list)
    duration_ms: float = 0
    raw: Optional[Dict[str, Any]] = None


class ProviderError(RuntimeError):
    def __init__(self, provider: str, message: str, status: Optional[int] = None):
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.status = status


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def extract_json(text: str) -> Any:
    """
    Robustly pull a JSON object out of model text.

    Handles fenced blocks, <think> prefixes (Sonar reasoning models), and
    leading/trailing prose around the outermost {...}.
    """
    if not text:
        raise ValueError("empty model response")
    cleaned = _THINK_RE.sub("", text).strip()
    fence = _JSON_FENCE_RE.search(cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        return json.loads(cleaned[start : end + 1])
    raise ValueError(f"no JSON object found in response: {cleaned[:200]!r}")


class Stopwatch:
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.ms = (time.perf_counter() - self.t0) * 1000
