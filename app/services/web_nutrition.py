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


def _user_specified_portion(name: str, brand: Optional[str] = None, store: Optional[str] = None) -> bool:
    """
    Проверяет, указал ли пользователь размер порции в запросе.
    Ищет паттерны вида "200г", "500 грамм", "250мл" и т.д.
    """
    text = f"{name} {brand or ''} {store or ''}".lower()
    
    # Проверяем наличие цифр
    has_digit = any(c.isdigit() for c in text)
    if not has_digit:
        return False
    
    # Проверяем наличие единиц измерения рядом с цифрами
    units = ["г", "гр", "грамм", "kg", "кг", "ml", "мл", "л", "l"]
    for unit in units:
        # Ищем паттерн "число + единица" или "единица + число"
        pattern1 = r'\d+\s*' + re.escape(unit)
        pattern2 = re.escape(unit) + r'\s*\d+'
        if re.search(pattern1, text) or re.search(pattern2, text):
            return True
    
    return False


async def _find_portion_size_with_web(
    name: str,
    brand: Optional[str] = None,
    store: Optional[str] = None,
    api_key: str = None
) -> Optional[float]:
    """
    Ищет размер порции/упаковки продукта через веб-поиск.
    Возвращает размер в граммах или None.
    """
    if not api_key:
        return None
    
    try:
        # Формируем поисковый запрос специально для размера упаковки
        query_parts = [name]
        if brand:
            query_parts.append(brand)
        if store:
            query_parts.append(store)
        query_parts.extend(["масса нетто", "объем", "упаковка", "сколько грамм", "размер порции"])
        search_query = " ".join(query_parts)
        
        # Выполняем поиск через Tavily
        tavily_result = await tavily_search(
            query=search_query,
            api_key=api_key,
            max_results=3  # Меньше результатов для более точного поиска
        )
        
        if not tavily_result or "results" not in tavily_result:
            logger.debug("Tavily returned no results for portion size")
            return None
        
        results = tavily_result.get("results", [])
        if not results:
            logger.debug("Tavily returned empty results for portion size")
            return None
        
        # Формируем контекст из результатов
        context_parts = []
        for i, result in enumerate(results[:3]):
            title = result.get("title", "").strip()
            content = result.get("content", "").strip()
            
            if title:
                context_parts.append(f"Источник {i+1}: {title}")
            if content:
                if len(content) > 400:
                    content = content[:400] + "..."
                context_parts.append(content)
        
        if not context_parts:
            logger.debug("No useful content for portion size")
            return None
        
        context = "\n\n".join(context_parts)
        if len(context) > 1500:
            context = context[:1500] + "..."
        
        # Формируем промпт для LLM - только для поиска размера порции
        system_prompt = (
            "Ты ассистент. Тебе дают описание продукта и результаты веб-поиска. "
            "Твоя задача: найти размер упаковки/порции продукта в граммах или миллилитрах.\n\n"
            "ВАЖНО: отвечай СТРОГО в формате JSON с полями:\n"
            "- portion_grams: число (размер порции/упаковки в граммах) или null, если не найден\n"
            "- notes: краткое объяснение, откуда взялось значение\n\n"
            "Правила:\n"
            "1) Ищи массу нетто, объем упаковки, размер порции в тексте\n"
            "2) Если указано в мл - приравняй к граммам (1 мл ≈ 1 г)\n"
            "3) Если указано в кг - переведи в граммы (1 кг = 1000 г)\n"
            "4) Если точного размера нет, но можно оценить типичный размер для этого типа продукта - верни оценку и укажи это в notes\n"
            "5) НЕ возвращай 100 г просто потому что это 'на 100 г' - это нутриция, не размер упаковки\n"
            "6) Если совсем ничего не найдено - верни null\n\n"
            "Отвечай ТОЛЬКО JSON, без дополнительного текста."
        )
        
        user_prompt = (
            f"Продукт: {name}"
            + (f", бренд: {brand}" if brand else "")
            + (f", магазин: {store}" if store else "")
            + f"\n\nРезультаты поиска:\n{context}\n\n"
            "Найди размер упаковки/порции в граммах."
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
            logger.debug(f"LLM response for portion size does not contain JSON: {raw_response[:200]}")
            return None
        
        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse LLM JSON for portion size: {e}, raw: {raw_response[:200]}")
            return None
        
        portion_grams_val = data.get("portion_grams")
        if portion_grams_val is None:
            logger.debug("LLM did not provide portion_grams")
            return None
        
        try:
            portion_grams = float(portion_grams_val)
            # Проверяем разумность значения
            if portion_grams <= 0:
                return None
            if portion_grams < 20 or portion_grams > 3000:
                logger.debug(f"Portion size out of reasonable bounds: {portion_grams}")
                return None
            return portion_grams
        except (ValueError, TypeError):
            logger.debug(f"Invalid portion_grams value: {portion_grams_val}")
            return None
            
    except Exception as e:
        logger.debug(f"Error in _find_portion_size_with_web: {e}")
        return None


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
        
        # Определяем, является ли запрос конкретным (с брендом или штрихкодом)
        is_specific_product = bool(brand)
        
        # Формируем промпт для LLM
        if is_specific_product:
            # Для конкретных продуктов - выбираем один наиболее релевантный источник
            system_prompt = (
                "Ты нутриционный ассистент. Тебе даётся описание КОНКРЕТНОГО продукта (с брендом) и результаты веб-поиска. "
                "На основе этого извлеки КБЖУ (калории, белки, жиры, углеводы).\n\n"
                "ВАЖНО: для конкретного продукта выбери ОДИН наиболее релевантный источник, который точно соответствует "
                "указанному продукту и бренду. НЕ усредняй значения из разных источников. "
                "Используй данные только из того источника, который наиболее точно описывает именно этот продукт.\n\n"
                "Отвечай СТРОГО в формате JSON с полями:\n"
                "- description: краткое описание продукта\n"
                "- portion_grams: число или null (вес порции/упаковки в граммах, если указан в источнике, иначе 100)\n"
                "- per_100g: объект с полями { \"calories\": number|null, \"protein_g\": number|null, \"fat_g\": number|null, \"carbs_g\": number|null }\n"
                "- notes: строка с пояснениями (укажи, из какого источника взяты данные)\n\n"
                "Если в источнике указаны значения на упаковку (например, '500 г, 250 ккал'), "
                "попытайся пересчитать на 100г. Если пересчёт невозможен, оставь per_100g.* = null и укажи в notes.\n\n"
                "Отвечай ТОЛЬКО JSON, без дополнительного текста."
            )
        else:
            # Для общих продуктов - можно усреднять
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
        
        # Получаем notes из ответа LLM (будет использоваться позже)
        notes = data.get("notes", "").strip()
        
        # Определяем portion_grams
        # Сначала проверяем, указал ли пользователь размер порции в запросе
        user_specified = _user_specified_portion(name, brand, store)
        portion_grams = 100.0
        
        if user_specified:
            # Пытаемся извлечь размер порции из запроса пользователя
            user_text = f"{name} {brand or ''} {store or ''}".lower()
            match = re.search(r'(\d+\.?\d*)\s*(г|гр|грамм|kg|кг|ml|мл|л|l)', user_text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                unit = match.group(2).lower()
                if unit in ("кг", "kg"):
                    portion_grams = value * 1000
                elif unit in ("л", "l"):
                    portion_grams = value * 1000  # мл
                elif unit in ("мл", "ml", "г", "гр", "грамм", "g"):
                    portion_grams = value
                logger.info(f"User specified portion size: {portion_grams} г")
        else:
            # Пробуем получить из ответа LLM (первый проход)
            portion_grams_val = data.get("portion_grams")
            if portion_grams_val is not None:
                try:
                    portion_grams = float(portion_grams_val)
                    if portion_grams <= 0:
                        portion_grams = 100.0
                except (ValueError, TypeError):
                    portion_grams = 100.0
            
            # Если LLM не вернул размер порции или вернул 100г, делаем отдельный поиск
            if portion_grams == 100.0:
                logger.info("Portion size not found in first pass, searching separately...")
                found_portion = await _find_portion_size_with_web(
                    name=name,
                    brand=brand,
                    store=store,
                    api_key=settings.tavily_api_key
                )
                if found_portion and found_portion != 100.0:
                    portion_grams = found_portion
                    logger.info(f"Found portion size from separate search: {portion_grams} г")
                    # Обновляем notes, если нашли размер порции
                    if notes:
                        notes = f"{notes} Размер упаковки найден в интернете: {portion_grams:.0f} г."
                    else:
                        notes = f"Размер упаковки найден в интернете: {portion_grams:.0f} г."
        
        # Пересчитываем на порцию
        factor = portion_grams / 100.0
        
        calories = float(calories_per_100g) * factor
        protein_per_100g = per_100g.get("protein_g")
        fat_per_100g = per_100g.get("fat_g")
        carbs_per_100g = per_100g.get("carbs_g")
        
        protein_g = float(protein_per_100g) * factor if protein_per_100g is not None else 0.0
        fat_g = float(fat_per_100g) * factor if fat_per_100g is not None else 0.0
        carbs_g = float(carbs_per_100g) * factor if carbs_per_100g is not None else 0.0
        
        # Округляем все значения: калории до целого, макросы до 1 знака после запятой
        calories = round(calories)
        protein_g = round(protein_g, 1)
        fat_g = round(fat_g, 1)
        carbs_g = round(carbs_g, 1)
        portion_grams = round(portion_grams, 1)
        
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
