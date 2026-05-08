from typing import Dict, List

from openai import AsyncOpenAI

from app.core.config import settings

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
