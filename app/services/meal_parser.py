import json
from typing import Any, Dict

from app.services.llm_client import chat_completion


async def parse_meal_text(text: str, locale: str = "ru-RU") -> Dict[str, Any]:
    """
    Просим LLM оценить КБЖУ по текстовому описанию приёма пищи.
    Возвращаем dict с полями:
      - description: str
      - calories: float
      - protein_g: float
      - fat_g: float
      - carbs_g: float
      - accuracy_level: str  ("EXACT" / "ESTIMATE" / "APPROX")
      - notes: str (опционально)
    """

    system_prompt = (
        "You are a nutrition assistant. "
        "Given a user's description of what they ate, "
        "you estimate calories and macronutrients (protein, fat, carbs).\n\n"
        "Output STRICTLY a JSON object with the following fields:\n"
        "- description: short cleaned description of the meal in the same language as the user\n"
        "- calories: number (float), total kcal\n"
        "- protein_g: number (float), total grams of protein\n"
        "- fat_g: number (float), total grams of fat\n"
        "- carbs_g: number (float), total grams of carbohydrates\n"
        "- accuracy_level: one of ['EXACT', 'ESTIMATE', 'APPROX']\n"
        "- notes: short explanation in the same language as the user\n\n"
        "Do not output anything except this JSON."
    )

    user_prompt = (
        f"Locale: {locale}\n\n"
        f"User meal description:\n{text}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    raw = await chat_completion(messages)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Если модель чуть-чуть нарушила формат — пробуем почистить
        # На MVP просто бросаем ошибку наверх
        raise ValueError(f"LLM returned non-JSON response: {raw!r}")

    # Нормализуем и ставим дефолты
    result: Dict[str, Any] = {
        "description": data.get("description", "").strip() or "Описание не указано",
        "calories": float(data.get("calories", 0) or 0),
        "protein_g": float(data.get("protein_g", 0) or 0),
        "fat_g": float(data.get("fat_g", 0) or 0),
        "carbs_g": float(data.get("carbs_g", 0) or 0),
        "accuracy_level": str(data.get("accuracy_level", "ESTIMATE")).upper(),
        "notes": data.get("notes", ""),
    }

    # Подстрахуемся по accuracy_level
    if result["accuracy_level"] not in {"EXACT", "ESTIMATE", "APPROX"}:
        result["accuracy_level"] = "ESTIMATE"

    return result
