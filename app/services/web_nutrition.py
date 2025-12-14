"""
Web-поиск нутриции через Tavily + LLM.
"""
import json
import logging
import re
from typing import Optional, Dict, Any

from app.core.config import settings
from app.services.web_search import tavily_search
from app.services.llm_client import chat_completion

logger = logging.getLogger(__name__)


async def estimate_nutrition_with_web(
    name: str,
    brand: Optional[str] = None,
    store: Optional[str] = None,
    locale: str = "ru-RU"
) -> Optional[Dict[str, Any]]:
    """
    Оценивает КБЖУ продукта через веб-поиск (Tavily) + LLM.
    
    Возвращает dict в формате:
    {
        "description": str,
        "calories": float,
        "protein_g": float,
        "fat_g": float,
        "carbs_g": float,
        "portion_grams": float,
        "accuracy_level": "HIGH" | "ESTIMATE",
        "notes": str,
        "source_url": Optional[str],
    }
    или None при ошибке/отсутствии данных.
    """
    # Проверка наличия API ключа
    if not settings.tavily_api_key:
        logger.info("TAVILY_API_KEY is not set; web_search disabled")
        return None
    
    try:
        # Формируем поисковый запрос
        query_parts = [name]
        if brand:
            query_parts.append(brand)
        if store:
            query_parts.append(store)
        query_parts.extend(["кбжу", "калории", "белки", "жиры", "углеводы", "100", "г", "упаковка", "грамм"])
        search_query = " ".join(query_parts)
        
        # Выполняем поиск через Tavily
        tavily_result = await tavily_search(
            query=search_query,
            api_key=settings.tavily_api_key,
            max_results=5
        )
        
        if not tavily_result or "results" not in tavily_result:
            logger.debug("Tavily returned no results")
            return None
        
        results = tavily_result.get("results", [])
        if not results:
            logger.debug("Tavily returned empty results list")
            return None
        
        # Извлекаем top-3 результатов и формируем контекст
        context_parts = []
        source_url = None
        
        for i, result in enumerate(results[:3]):
            title = result.get("title", "").strip()
            content = result.get("content", "").strip()
            url = result.get("url", "").strip()
            
            if title:
                context_parts.append(f"Источник {i+1}: {title}")
            if content:
                # Ограничиваем длину контента
                if len(content) > 500:
                    content = content[:500] + "..."
                context_parts.append(content)
            
            # Берём URL первого результата
            if i == 0 and url:
                source_url = url
        
        if not context_parts:
            logger.debug("No useful content extracted from Tavily results")
            return None
        
        context = "\n\n".join(context_parts)
        # Ограничиваем общий размер контекста
        if len(context) > 2000:
            context = context[:2000] + "..."
        
        # Формируем промпт для LLM
        system_prompt = (
            "Ты нутриционный ассистент. Тебе даётся описание продукта и результаты веб-поиска. "
            "На основе этого извлеки КБЖУ (калории, белки, жиры, углеводы).\n\n"
            "ВАЖНО: отвечай СТРОГО в формате JSON с полями:\n"
            "- description: краткое описание продукта\n"
            "- portion_grams: число или null (вес порции/упаковки в граммах, если указан в источнике, иначе 100)\n"
            "- per_100g: объект с полями { \"calories\": number|null, \"protein_g\": number|null, \"fat_g\": number|null, \"carbs_g\": number|null }\n"
            "- notes: строка с пояснениями\n\n"
            "Если в источнике указаны значения на упаковку (например, '500 г, 250 ккал'), "
            "попытайся пересчитать на 100г. Если пересчёт невозможен, оставь per_100g.* = null и укажи в notes.\n\n"
            "Отвечай ТОЛЬКО JSON, без дополнительного текста."
        )
        
        user_prompt = (
            f"Продукт: {name}"
            + (f", бренд: {brand}" if brand else "")
            + (f", магазин: {store}" if store else "")
            + f"\n\nРезультаты поиска:\n{context}"
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        # Вызываем LLM
        raw_response = await chat_completion(messages)
        
        # Парсим JSON из ответа LLM
        # Ищем первый блок {...} - более надёжный паттерн для вложенных объектов
        json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if not json_match:
            logger.warning(f"LLM response does not contain JSON: {raw_response[:200]}")
            return None
        
        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON response: {e}, raw: {raw_response[:200]}")
            return None
        
        # Валидируем и извлекаем данные
        per_100g = data.get("per_100g", {})
        if not isinstance(per_100g, dict):
            per_100g = {}
        
        calories_per_100g = per_100g.get("calories")
        if calories_per_100g is None:
            logger.info("LLM did not provide calories per 100g")
            return None
        
        # Определяем portion_grams
        portion_grams_val = data.get("portion_grams")
        if portion_grams_val is not None:
            try:
                portion_grams = float(portion_grams_val)
                if portion_grams <= 0:
                    portion_grams = 100.0
            except (ValueError, TypeError):
                portion_grams = 100.0
        else:
            portion_grams = 100.0
        
        # Пересчитываем на порцию
        factor = portion_grams / 100.0
        
        calories = float(calories_per_100g) * factor
        protein_per_100g = per_100g.get("protein_g")
        fat_per_100g = per_100g.get("fat_g")
        carbs_per_100g = per_100g.get("carbs_g")
        
        protein_g = float(protein_per_100g) * factor if protein_per_100g is not None else 0.0
        fat_g = float(fat_per_100g) * factor if fat_per_100g is not None else 0.0
        carbs_g = float(carbs_per_100g) * factor if carbs_per_100g is not None else 0.0
        
        # Определяем accuracy_level
        has_explicit_values = (
            calories_per_100g is not None
            and protein_per_100g is not None
            and fat_per_100g is not None
            and carbs_per_100g is not None
        )
        has_explicit_portion = portion_grams != 100.0
        
        accuracy_level = "HIGH" if (has_explicit_values and has_explicit_portion) else "ESTIMATE"
        
        description = data.get("description", name).strip() or name
        notes = data.get("notes", "").strip()
        
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
        logger.error(f"Error in estimate_nutrition_with_web: {e}", exc_info=True)
        return None
