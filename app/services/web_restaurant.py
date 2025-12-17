"""
Web-поиск нутриции блюд из ресторанов через Tavily + LLM.
"""
import json
import logging
import re
from typing import Optional, Dict, Any

from app.core.config import settings
from app.services.web_search import tavily_search
from app.services.llm_client import chat_completion

logger = logging.getLogger(__name__)


async def estimate_restaurant_meal_with_web(
    restaurant: str,
    dish: str,
    locale: str = "ru-RU"
) -> Optional[Dict[str, Any]]:
    """
    Оценивает КБЖУ блюда из ресторана через веб-поиск.
    
    Args:
        restaurant: название ресторана/кафе/доставки
        dish: название блюда
        locale: локаль (по умолчанию "ru-RU")
    
    Returns:
        dict с полями:
        - description: str
        - calories: float
        - protein_g: float
        - fat_g: float
        - carbs_g: float
        - portion_grams: float|None
        - accuracy_level: "HIGH"|"ESTIMATE"
        - notes: str
        - source_url: Optional[str]
        или None, если не удалось найти
    """
    if not restaurant or not dish:
        logger.warning("estimate_restaurant_meal_with_web: missing restaurant or dish")
        return None
    
    if not settings.tavily_api_key:
        logger.warning("estimate_restaurant_meal_with_web: missing tavily_api_key")
        return None
    
    try:
        # Формируем поисковый запрос
        search_query = f"{restaurant} {dish} калории белки жиры углеводы кбжу порция грамм меню"
        
        # Выполняем поиск через Tavily
        tavily_result = await tavily_search(
            query=search_query,
            api_key=settings.tavily_api_key,
            max_results=5
        )
        
        if not tavily_result or "results" not in tavily_result:
            logger.debug("Tavily returned no results for restaurant meal")
            return None
        
        results = tavily_result.get("results", [])
        if not results:
            logger.debug("Tavily returned empty results for restaurant meal")
            return None
        
        # Берем source_url из первого результата
        source_url = results[0].get("url") if results else None
        
        # Формируем контекст из результатов поиска
        context_parts = []
        for i, result in enumerate(results[:5]):
            title = result.get("title", "").strip()
            content = result.get("content", "").strip()
            
            if title:
                context_parts.append(f"Источник {i+1}: {title}")
            if content:
                if len(content) > 500:
                    content = content[:500] + "..."
                context_parts.append(content)
        
        if not context_parts:
            logger.debug("No useful content for restaurant meal")
            return None
        
        context = "\n\n".join(context_parts)
        if len(context) > 2500:
            context = context[:2500] + "..."
        
        # Формируем промпт для LLM
        system_prompt = (
            "Ты нутриционный ассистент. Тебе даётся название ресторана/кафе, название блюда "
            "и результаты веб-поиска. На основе этого извлеки КБЖУ (калории, белки, жиры, углеводы).\n\n"
            "Отвечай СТРОГО в формате JSON с полями:\n"
            "- description: строка (должно включать dish + restaurant, например \"паста карбонара в Vapiano\")\n"
            "- nutrition_basis: строка, одно из \"PER_100G\" или \"PER_PORTION\"\n"
            "- portion_grams: число или null (вес порции в граммах, если указан в источнике)\n"
            "- per_100g: объект {\"calories\": number|null, \"protein_g\": number|null, \"fat_g\": number|null, \"carbs_g\": number|null} или null\n"
            "- per_portion: объект {\"calories\": number|null, \"protein_g\": number|null, \"fat_g\": number|null, \"carbs_g\": number|null} или null\n"
            "- accuracy_level: строка, одно из \"HIGH\" или \"ESTIMATE\"\n"
            "- notes: строка с пояснениями\n\n"
            "Правила:\n"
            "1) Если в источнике указаны значения на порцию - используй PER_PORTION и заполни per_portion\n"
            "2) Если в источнике указаны значения на 100г - используй PER_100G и заполни per_100g\n"
            "3) Если указан размер порции в граммах - укажи его в portion_grams\n"
            "4) accuracy_level = \"HIGH\" только если найдены явные значения КБЖУ в источнике, иначе \"ESTIMATE\"\n"
            "5) description должно включать и название блюда, и название ресторана\n\n"
            "Отвечай ТОЛЬКО JSON, без дополнительного текста."
        )
        
        user_prompt = (
            f"Ресторан: {restaurant}\n"
            f"Блюдо: {dish}\n\n"
            f"Результаты поиска:\n{context}\n\n"
            "Извлеки КБЖУ для этого блюда из этого ресторана."
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        # Вызываем LLM
        raw_response = await chat_completion(messages)
        
        # Парсим JSON
        json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if not json_match:
            logger.debug(f"LLM response does not contain JSON: {raw_response[:200]}")
            return None
        
        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse LLM JSON: {e}, raw: {raw_response[:200]}")
            return None
        
        # Извлекаем данные
        description = data.get("description", "").strip() or f"{dish} в {restaurant}"
        nutrition_basis = data.get("nutrition_basis", "PER_100G")
        portion_grams_val = data.get("portion_grams")
        per_100g = data.get("per_100g")
        per_portion = data.get("per_portion")
        accuracy_level = data.get("accuracy_level", "ESTIMATE")
        notes = data.get("notes", "").strip()
        
        # Нормализуем nutrition_basis
        if nutrition_basis not in ("PER_100G", "PER_PORTION"):
            nutrition_basis = "PER_100G"
        
        # Нормализуем accuracy_level
        if accuracy_level not in ("HIGH", "ESTIMATE"):
            accuracy_level = "ESTIMATE"
        
        # Определяем portion_grams
        portion_grams = None
        if portion_grams_val is not None:
            try:
                portion_grams = float(portion_grams_val)
                if portion_grams <= 0:
                    portion_grams = None
            except (ValueError, TypeError):
                portion_grams = None
        
        # Извлекаем значения КБЖУ в зависимости от nutrition_basis
        calories = None
        protein_g = None
        fat_g = None
        carbs_g = None
        
        if nutrition_basis == "PER_PORTION" and per_portion:
            calories = per_portion.get("calories")
            protein_g = per_portion.get("protein_g")
            fat_g = per_portion.get("fat_g")
            carbs_g = per_portion.get("carbs_g")
        elif nutrition_basis == "PER_100G" and per_100g:
            calories_per_100g = per_100g.get("calories")
            protein_per_100g = per_100g.get("protein_g")
            fat_per_100g = per_100g.get("fat_g")
            carbs_per_100g = per_100g.get("carbs_g")
            
            # Если есть portion_grams, пересчитываем на порцию
            if portion_grams and portion_grams > 0:
                factor = portion_grams / 100.0
                calories = float(calories_per_100g) * factor if calories_per_100g is not None else None
                protein_g = float(protein_per_100g) * factor if protein_per_100g is not None else None
                fat_g = float(fat_per_100g) * factor if fat_per_100g is not None else None
                carbs_g = float(carbs_per_100g) * factor if carbs_per_100g is not None else None
            else:
                # Если portion_grams нет, оставляем на 100г
                calories = calories_per_100g
                protein_g = protein_per_100g
                fat_g = fat_per_100g
                carbs_g = carbs_per_100g
                if not notes:
                    notes = "Значения указаны на 100 г, размер порции не найден"
                else:
                    notes = f"{notes}. Значения указаны на 100 г, размер порции не найден"
        
        # Проверяем, что есть хотя бы калории
        if calories is None or calories <= 0:
            logger.debug("LLM did not provide calories")
            return None
        
        # Округляем значения
        calories = round(float(calories))
        protein_g = round(float(protein_g or 0.0), 1)
        fat_g = round(float(fat_g or 0.0), 1)
        carbs_g = round(float(carbs_g or 0.0), 1)
        if portion_grams:
            portion_grams = round(portion_grams, 1)
        
        return {
            "description": description,
            "calories": calories,
            "protein_g": protein_g,
            "fat_g": fat_g,
            "carbs_g": carbs_g,
            "portion_grams": portion_grams,
            "accuracy_level": accuracy_level,
            "notes": notes,
            "source_url": source_url,
        }
        
    except Exception as e:
        logger.error(f"Error in estimate_restaurant_meal_with_web: {e}", exc_info=True)
        return None

