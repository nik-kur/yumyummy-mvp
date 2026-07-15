import logging
from typing import Dict, List, Tuple

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# Async client so awaits do not block the event loop. Reused as a singleton —
# AsyncOpenAI manages its own connection pool internally.
_client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=60.0)


async def chat_completion(
    messages: List[Dict[str, str]],
    model: str = "gpt-4.1-mini",
    temperature: float = 0.3,
) -> str:
    """Async chat completion. Returns the content of the first choice."""
    response = await _client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


async def moderate_text(text: str) -> Tuple[bool, List[str]]:
    """Screen free-text user input with OpenAI's (free) moderation endpoint.

    Returns ``(flagged, categories)``. We **fail open**: if the moderation
    call errors or times out we return ``(False, [])`` so a transient OpenAI
    hiccup can never block a paying user from logging a meal. The goal here is
    to catch clearly abusive/harmful input to our AI (self-harm, sexual,
    hateful, violent content), not to be a hard gate.
    """
    if not text or not text.strip():
        return False, []
    try:
        resp = await _client.moderations.create(
            model="omni-moderation-latest",
            input=text[:8000],
        )
        result = resp.results[0]
        if not result.flagged:
            return False, []
        categories = [
            name for name, value in result.categories.model_dump().items() if value
        ]
        return True, categories
    except Exception as exc:  # fail open — never block logging on a moderation error
        logger.warning("[MODERATION] check failed, allowing through: %s", exc)
        return False, []
