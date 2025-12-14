from datetime import date
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings


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
