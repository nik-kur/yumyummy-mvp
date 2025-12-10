from typing import Any, Dict, List

from openai import OpenAI

from app.core.config import settings

# Инициализируем клиент один раз
_client = OpenAI(api_key=settings.openai_api_key)


async def chat_completion(
    messages: List[Dict[str, str]],
    model: str = "gpt-4.1-mini",
    temperature: float = 0.3,
) -> str:
    """
    Обёртка над chat-completion.
    На вход:
      - messages: список сообщений формата {"role": "...", "content": "..."}
    На выход:
      - content первого ответа модели (строка).
    """
    # ВНИМАНИЕ: openai v1 клиент синхронный, поэтому здесь можно
    # либо вызвать его в отдельном потоке, либо пока оставить синхронно.
    #
    # Для MVP можно начать с sync-вызова, а потом, если нужно, обернуть в run_in_executor.
    #

    response = _client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    # Берем содержимое первого ответа
    return response.choices[0].message.content or ""
