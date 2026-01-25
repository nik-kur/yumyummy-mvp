from datetime import date
from typing import Any, Dict, Optional

import httpx
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


async def ping_backend() -> Optional[Dict[str, Any]]:
    """
    Бьём в /health backend'а.
    Возвращаем JSON-ответ или None, если что-то пошло не так.
    """
    url = f"{settings.backend_base_url}/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def ensure_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    """
    Гарантируем, что пользователь с таким telegram_id есть в backend.
    Вызывает POST /users.
    Возвращает JSON-данные пользователя или None, если ошибка.
    """
    url = f"{settings.backend_base_url}/users"
    payload = {"telegram_id": str(telegram_id)}  # наша схема ждёт str

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def create_meal(
    user_id: int,
    day: date,
    description: str,
    calories: float,
    protein_g: float = 0,
    fat_g: float = 0,
    carbs_g: float = 0,
    accuracy_level: Optional[str] = None,
    source_provider: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Создаём приём пищи через POST /meals.
    """
    url = f"{settings.backend_base_url}/meals"
    payload = {
        "user_id": user_id,
        "date": day.isoformat(),
        "description_user": description,
        "calories": calories,
        "protein_g": protein_g,
        "fat_g": fat_g,
        "carbs_g": carbs_g,
    }
    if accuracy_level:
        payload["accuracy_level"] = accuracy_level
    if source_provider:
        payload["source_provider"] = source_provider

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def get_day_summary(user_id: int, day: date) -> Optional[Dict[str, Any]]:
    """
    Получаем сводку по дню через GET /day/{user_id}/{date}
    """
    url = f"{settings.backend_base_url}/day/{user_id}/{day.isoformat()}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def update_meal(
    meal_id: int,
    description: Optional[str] = None,
    calories: Optional[float] = None,
    protein_g: Optional[float] = None,
    fat_g: Optional[float] = None,
    carbs_g: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Обновляем приём пищи через PATCH /meals/{meal_id}.
    """
    url = f"{settings.backend_base_url}/meals/{meal_id}"
    payload: Dict[str, Any] = {}
    if description is not None:
        payload["description_user"] = description
    if calories is not None:
        payload["calories"] = calories
    if protein_g is not None:
        payload["protein_g"] = protein_g
    if fat_g is not None:
        payload["fat_g"] = fat_g
    if carbs_g is not None:
        payload["carbs_g"] = carbs_g

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.patch(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def delete_meal(meal_id: int) -> bool:
    """
    Удаляем приём пищи через DELETE /meals/{meal_id}.
    """
    url = f"{settings.backend_base_url}/meals/{meal_id}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.delete(url)
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            return True
    except Exception:
        return False

async def ai_parse_meal(text: str) -> Optional[Dict[str, Any]]:
    """
    Вызывает POST /ai/parse_meal в backend.
    Возвращает dict с полями:
      description, calories, protein_g, fat_g, carbs_g, accuracy_level, notes
    или None, если ошибка.
    """
    url = f"{settings.backend_base_url}/ai/parse_meal"
    payload = {"text": text}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def product_parse_meal_by_barcode(barcode: str) -> Optional[Dict[str, Any]]:
    """
    Вызывает POST /ai/product_parse_meal с штрихкодом.
    Возвращает dict с полями:
      description, calories, protein_g, fat_g, carbs_g, accuracy_level, source_provider, notes
    или None, если ошибка.
    """
    url = f"{settings.backend_base_url}/ai/product_parse_meal"
    payload = {"barcode": barcode}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def product_parse_meal_by_name(
    name: str,
    brand: Optional[str] = None,
    store: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Вызывает POST /ai/product_parse_meal с названием продукта.
    Возвращает dict с полями:
      description, calories, protein_g, fat_g, carbs_g, accuracy_level, source_provider, notes
    или None, если ошибка.
    """
    url = f"{settings.backend_base_url}/ai/product_parse_meal"
    payload = {"name": name}
    if brand:
        payload["brand"] = brand
    if store:
        payload["store"] = store

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def voice_parse_meal(audio_bytes: bytes) -> Optional[Dict[str, Any]]:
    """
    Вызывает POST /ai/voice_parse_meal в backend.
    Отправляет аудиофайл для распознавания и парсинга.
    Возвращает dict с полями:
      transcript, description, calories, protein_g, fat_g, carbs_g, accuracy_level, notes
    или None, если ошибка.
    """
    url = f"{settings.backend_base_url}/ai/voice_parse_meal"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"audio": ("voice.ogg", audio_bytes, "audio/ogg")}
            resp = await client.post(url, files=files)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def restaurant_parse_meal(restaurant: str, dish: str) -> Optional[Dict[str, Any]]:
    """
    Вызывает POST /ai/restaurant_parse_meal в backend.
    Возвращает dict с полями:
      description, calories, protein_g, fat_g, carbs_g, accuracy_level, source_provider, notes, source_url
    или None, если ошибка.
    """
    url = f"{settings.backend_base_url}/ai/restaurant_parse_meal"
    payload = {
        "restaurant": restaurant,
        "dish": dish,
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def restaurant_parse_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Вызывает POST /ai/restaurant_parse_text в backend.
    Возвращает dict с полями:
      description, calories, protein_g, fat_g, carbs_g, accuracy_level, source_provider, notes, source_url
    или None, если ошибка.
    """
    url = f"{settings.backend_base_url}/ai/restaurant_parse_text"
    payload = {
        "text": text,
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def restaurant_parse_text_openai(text: str) -> Optional[Dict[str, Any]]:
    """
    EXPERIMENTAL: Вызывает POST /ai/restaurant_parse_text_openai в backend.
    Использует OpenAI Responses API с web_search tool (Path A для A/B тестирования).
    Возвращает dict с полями:
      description, calories, protein_g, fat_g, carbs_g, accuracy_level, source_provider, notes, source_url
    или None, если ошибка.
    """
    url = f"{settings.backend_base_url}/ai/restaurant_parse_text_openai"
    payload = {
        "text": text,
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:  # Longer timeout for OpenAI API
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"[API] restaurant_parse_text_openai HTTP error: {e.response.status_code} - {e.response.text[:200]}")
        return None
    except httpx.RequestError as e:
        logger.error(f"[API] restaurant_parse_text_openai request error: {e}")
        return None
    except Exception as e:
        logger.error(f"[API] restaurant_parse_text_openai unexpected error: {e}", exc_info=True)
        return None


async def agent_query(user_id: int, text: str, date: Optional[str] = None, conversation_context: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Вызывает POST /ai/agent в backend.
    Возвращает dict с полями:
      intent, reply_text, meal, day_summary, week_summary
    или None, если ошибка.
    """
    url = f"{settings.backend_base_url}/ai/agent"
    payload = {
        "user_id": user_id,
        "text": text,
    }
    if date:
        payload["date"] = date
    if conversation_context:
        payload["conversation_context"] = conversation_context
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout for agent processing
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"[API] agent_query HTTP error: {e.response.status_code} - {e.response.text[:200]}")
        return None
    except httpx.RequestError as e:
        logger.error(f"[API] agent_query request error: {e}")
        return None
    except Exception as e:
        logger.error(f"[API] agent_query unexpected error: {e}", exc_info=True)
        return None


async def agent_run_workflow(telegram_id: str, text: str) -> Optional[Dict[str, Any]]:
    """
    Вызывает POST /agent/run в backend.
    Возвращает dict с полями:
      intent, message_text, confidence, totals, items, source_url
    или None, если ошибка.
    """
    url = f"{settings.backend_base_url}/agent/run"
    payload = {
        "telegram_id": str(telegram_id),
        "text": text,
    }
    
    # Увеличенный таймаут для агентных ответов (до 180 секунд для web search)
    timeout = httpx.Timeout(180.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            
            # Log response for debugging
            logger.debug(
                f"[API] agent_run_workflow response: "
                f"status={resp.status_code}, "
                f"intent={result.get('intent')}, "
                f"has_message_text={'message_text' in result}, "
                f"has_totals={'totals' in result}, "
                f"has_items={'items' in result}"
            )
            
            return result
    except httpx.ReadTimeout:
        logger.warning("[API] agent_run_workflow timeout")
        return {
            "intent": "help",
            "message_text": "Я думаю дольше обычного 😅 Попробуй ещё раз через 10–20 секунд или уточни запрос.",
            "confidence": None,
            "totals": {"calories_kcal": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0},
            "items": [],
            "source_url": None
        }
    except httpx.HTTPStatusError as e:
        logger.error(f"[API] agent_run_workflow HTTP error: {e.response.status_code} - {e.response.text[:200]}")
        return None
    except httpx.RequestError as e:
        logger.error(f"[API] agent_run_workflow request error: {e}")
        return None
    except Exception as e:
        logger.error(f"[API] agent_run_workflow unexpected error: {e}", exc_info=True)
        return None
