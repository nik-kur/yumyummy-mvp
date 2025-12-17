"""
Web-поиск нутриции блюд из ресторанов через Tavily + LLM.
"""
import json
import logging
import re
from typing import Optional, Dict, Any, List

from app.core.config import settings
from app.services.web_search import tavily_search
from app.services.llm_client import chat_completion

logger = logging.getLogger(__name__)

# Приоритетные домены (официальные сайты ресторанов и платформы доставки)
PREFER_DOMAINS = [
    "ubereats.com",
    "ubereats.ru",
    "yandex.ru",
    "eda.yandex",
    "deliveroo",
    "wolt",
    "glovoapp.com",
    "glovo.ru",
    "dostavka",
    "menu",
    "restaurant",
    "cafe",
]

# Домены с низким приоритетом (случайные базы данных)
PENALTY_DOMAINS = [
    "myfitnesspal",
    "fatsecret",
    "pinterest",
    "livejournal",
    "reddit",
    "vk.com",
    "facebook",
]


def _normalize_restaurant_name(name: str) -> str:
    """Нормализует название ресторана для сравнения."""
    if not name:
        return ""
    # lowercase, убрать пробелы и спецсимволы
    normalized = re.sub(r'[^\w]', '', name.lower())
    return normalized


def _get_domain_from_url(url: str) -> str:
    """Извлекает домен из URL."""
    if not url:
        return ""
    try:
        # Убираем протокол
        domain = url.replace("http://", "").replace("https://", "").replace("www.", "")
        # Берем только домен (до первого /)
        domain = domain.split("/")[0]
        return domain.lower()
    except Exception:
        return ""


def rank_results(results: List[Dict[str, Any]], restaurant_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Ранжирует результаты поиска по приоритету источников.
    
    Args:
        results: список результатов от Tavily
        restaurant_name: название ресторана (опционально)
    
    Returns:
        Отсортированный список результатов с добавленным полем _score
    """
    normalized_restaurant = _normalize_restaurant_name(restaurant_name) if restaurant_name else ""
    
    scored_results = []
    for result in results:
        url = result.get("url", "")
        domain = _get_domain_from_url(url)
        score = 0
        
        # +50 если домен содержит нормализованное название ресторана
        if normalized_restaurant and normalized_restaurant in domain:
            score += 50
            logger.debug(f"Result {url} got +50 for restaurant match")
        
        # +30 если домен в prefer_domains
        for prefer_domain in PREFER_DOMAINS:
            if prefer_domain in domain:
                score += 30
                logger.debug(f"Result {url} got +30 for prefer domain: {prefer_domain}")
                break
        
        # -50 если домен в penalty_domains
        for penalty_domain in PENALTY_DOMAINS:
            if penalty_domain in domain:
                score -= 50
                logger.debug(f"Result {url} got -50 for penalty domain: {penalty_domain}")
                break
        
        # Сохраняем score в результате
        result_with_score = result.copy()
        result_with_score["_score"] = score
        scored_results.append(result_with_score)
    
    # Сортируем по score (desc)
    scored_results.sort(key=lambda x: x.get("_score", 0), reverse=True)
    
    return scored_results


async def _collect_candidates(
    restaurant: Optional[str],
    dish: str,
    api_key: str
) -> List[Dict[str, Any]]:
    """
    Собирает кандидатов из нескольких Tavily запросов.
    
    Returns:
        Список кандидатов [{url, title, content, raw_content}], дедуплицированный по url.
    """
    # Безопасная функция для извлечения строк
    def _s(x):
        return (x or "").strip() if isinstance(x, str) else ""
    
    # Проверяем входные данные
    if not dish or not dish.strip():
        logger.warning("_collect_candidates: empty dish")
        return []
    
    dish = dish.strip()
    if restaurant:
        restaurant = restaurant.strip()
    
    all_candidates = []
    seen_urls = set()
    
    # Запрос A: официальный сайт меню (более точный)
    if restaurant:
        query_a = f"{restaurant} официальный сайт меню питание кбжу {dish}"
        # Дополнительный запрос для меню на сайте ресторана (пробуем разные варианты домена)
        restaurant_lower = restaurant.lower().replace(' ', '').replace('ё', 'е')
        query_a2 = f"{restaurant_lower}.ru menu {dish}"
        query_a3 = f"{restaurant_lower}.com menu {dish}"
        # Еще один запрос с упрощенным названием блюда (первое слово)
        dish_words = dish.split()
        dish_first_word = dish_words[0] if dish_words else dish
        query_a4 = f"{restaurant} menu {dish_first_word}"
    else:
        query_a = f"{dish} официальный сайт меню питание кбжу"
        query_a2 = None
        query_a3 = None
        query_a4 = None
    
    try:
        result_a = await tavily_search(query=query_a, api_key=api_key, max_results=6)
        if result_a and "results" in result_a:
            for r in result_a.get("results", []):
                url = _s(r.get("url"))
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_candidates.append({
                        "url": url,
                        "title": _s(r.get("title")),
                        "content": _s(r.get("content")),
                        "raw_content": _s(r.get("raw_content")),
                    })
        logger.info(f"restaurant query A (official): {len(result_a.get('results', [])) if result_a else 0} results, {len([c for c in all_candidates if c['url'] in seen_urls])} unique")
    except Exception as e:
        logger.warning(f"restaurant query A failed: {e}")
    
    # Запрос A2: прямой поиск на сайте ресторана .ru (если есть restaurant)
    if query_a2:
        try:
            result_a2 = await tavily_search(query=query_a2, api_key=api_key, max_results=6)
            if result_a2 and "results" in result_a2:
                for r in result_a2.get("results", []):
                    url = _s(r.get("url"))
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_candidates.append({
                            "url": url,
                            "title": _s(r.get("title")),
                            "content": _s(r.get("content")),
                            "raw_content": _s(r.get("raw_content")),
                        })
            logger.info(f"restaurant query A2 (site .ru): {len(result_a2.get('results', [])) if result_a2 else 0} results, {len([c for c in all_candidates if c['url'] in seen_urls])} unique")
        except Exception as e:
            logger.warning(f"restaurant query A2 failed: {e}")
    
    # Запрос A3: прямой поиск на сайте ресторана .com (если есть restaurant)
    if query_a3:
        try:
            result_a3 = await tavily_search(query=query_a3, api_key=api_key, max_results=6)
            if result_a3 and "results" in result_a3:
                for r in result_a3.get("results", []):
                    url = _s(r.get("url"))
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_candidates.append({
                            "url": url,
                            "title": _s(r.get("title")),
                            "content": _s(r.get("content")),
                            "raw_content": _s(r.get("raw_content")),
                        })
            logger.info(f"restaurant query A3 (site .com): {len(result_a3.get('results', [])) if result_a3 else 0} results, {len([c for c in all_candidates if c['url'] in seen_urls])} unique")
        except Exception as e:
            logger.warning(f"restaurant query A3 failed: {e}")
    
    # Запрос A4: упрощенный поиск по первому слову блюда (если есть restaurant)
    if query_a4:
        try:
            result_a4 = await tavily_search(query=query_a4, api_key=api_key, max_results=6)
            if result_a4 and "results" in result_a4:
                for r in result_a4.get("results", []):
                    url = _s(r.get("url"))
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_candidates.append({
                            "url": url,
                            "title": _s(r.get("title")),
                            "content": _s(r.get("content")),
                            "raw_content": _s(r.get("raw_content")),
                        })
            logger.info(f"restaurant query A4 (simplified dish): {len(result_a4.get('results', [])) if result_a4 else 0} results, {len([c for c in all_candidates if c['url'] in seen_urls])} unique")
        except Exception as e:
            logger.warning(f"restaurant query A4 failed: {e}")
    
    # Запрос B: калории и нутриция (расширенный)
    if restaurant:
        query_b = f"{restaurant} {dish} calories kcal nutrition protein fat carbs"
        # Альтернативный запрос с упрощенным названием блюда
        dish_words = dish.split()
        dish_simple = dish_words[0] if dish_words else dish  # Первое слово блюда
        query_b2 = f"{restaurant} {dish_simple} menu calories"
    else:
        query_b = f"{dish} calories kcal nutrition protein fat carbs"
        query_b2 = None
    
    try:
        result_b = await tavily_search(query=query_b, api_key=api_key, max_results=6)
        if result_b and "results" in result_b:
            for r in result_b.get("results", []):
                url = _s(r.get("url"))
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_candidates.append({
                        "url": url,
                        "title": _s(r.get("title")),
                        "content": _s(r.get("content")),
                        "raw_content": _s(r.get("raw_content")),
                    })
        logger.info(f"restaurant query B (nutrition): {len(result_b.get('results', [])) if result_b else 0} results, {len([c for c in all_candidates if c['url'] in seen_urls])} unique")
    except Exception as e:
        logger.warning(f"restaurant query B failed: {e}")
    
    # Запрос B2: упрощенный поиск по первому слову блюда
    if query_b2:
        try:
            result_b2 = await tavily_search(query=query_b2, api_key=api_key, max_results=6)
            if result_b2 and "results" in result_b2:
                for r in result_b2.get("results", []):
                    url = _s(r.get("url"))
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_candidates.append({
                            "url": url,
                            "title": _s(r.get("title")),
                            "content": _s(r.get("content")),
                            "raw_content": _s(r.get("raw_content")),
                        })
            logger.info(f"restaurant query B2 (simplified): {len(result_b2.get('results', [])) if result_b2 else 0} results, {len([c for c in all_candidates if c['url'] in seen_urls])} unique")
        except Exception as e:
            logger.warning(f"restaurant query B2 failed: {e}")
    
    # Запрос C: доставка и меню
    if restaurant:
        query_c = f"{restaurant} {dish} delivery order menu calories"
    else:
        query_c = f"{dish} delivery order menu calories"
    
    try:
        result_c = await tavily_search(query=query_c, api_key=api_key, max_results=6)
        if result_c and "results" in result_c:
            for r in result_c.get("results", []):
                url = _s(r.get("url"))
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_candidates.append({
                        "url": url,
                        "title": _s(r.get("title")),
                        "content": _s(r.get("content")),
                        "raw_content": _s(r.get("raw_content")),
                    })
        logger.info(f"restaurant query C (delivery): {len(result_c.get('results', [])) if result_c else 0} results, {len([c for c in all_candidates if c['url'] in seen_urls])} unique")
    except Exception as e:
        logger.warning(f"restaurant query C failed: {e}")
    
    logger.info(f"restaurant total candidates collected: {len(all_candidates)}")
    return all_candidates


async def _rank_sources_with_llm(
    restaurant: Optional[str],
    dish: str,
    candidates: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Ранжирует кандидатов с помощью LLM.
    
    Returns:
        dict с полями:
        - ranking: list[int] (индексы кандидатов по убыванию качества)
        - reason: str (краткое объяснение выбора топ-1)
        или None, если не удалось получить ответ
    """
    if not candidates:
        return None
    
    if not dish or not dish.strip():
        logger.warning("_rank_sources_with_llm: empty dish")
        return None
    
    # Безопасная функция для извлечения строк
    def _s(x):
        return (x or "").strip() if isinstance(x, str) else ""
    
    # Нормализуем dish
    dish = dish.strip()
    if restaurant:
        restaurant = restaurant.strip() if restaurant else None
    
    # Формируем список кандидатов для LLM
    candidates_list = []
    for idx, cand in enumerate(candidates):
        url = _s(cand.get("url", ""))
        title = _s(cand.get("title", ""))
        content = _s(cand.get("content", ""))
        # Ограничиваем content для промпта
        if len(content) > 200:
            content = content[:200] + "..."
        candidates_list.append({
            "index": idx,
            "url": url,
            "title": title,
            "snippet": content,
        })
    
    # Формируем промпт для LLM
    candidates_text = "\n".join([
        f"{c['index']}. URL: {c['url']}\n   Title: {c['title']}\n   Snippet: {c['snippet']}"
        for c in candidates_list
    ])
    
    system_prompt = (
        "Ты помощник для ранжирования веб-источников по качеству для извлечения нутриционной информации о блюдах из ресторанов.\n\n"
        "Твоя задача: проанализировать список кандидатов и вернуть их индексы в порядке убывания качества.\n\n"
        "Критерии качества (в порядке приоритета):\n"
        "1) Официальный сайт ресторана с меню и нутрицией (домен содержит название ресторана или в title есть official/официальный)\n"
        "2) Страница меню/блюда на официальном сайте с указанием КБЖУ\n"
        "3) Платформы доставки (delivery/order/menu) с нутрицией для конкретного ресторана\n"
        "4) Агрегаторы меню ресторанов с нутрицией\n"
        "5) Исключить рецепты/\"how to cook\"/\"рецепт\" (если видишь такие слова в title/url)\n\n"
        "ВАЖНО:\n"
        "- Если официальный сайт НЕ содержит нутриции (нет kcal/ккал/белки/жиры/углеводы в snippet) - "
        "тогда доставка/меню агрегатор ресторана лучше, чем общая база калорий\n"
        "- Не придумывай информацию, используй только то, что видишь в url/title/snippet\n\n"
        "Отвечай СТРОГО в формате JSON:\n"
        "{\n"
        '  "ranking": [индексы по убыванию качества, например [2, 0, 1, 3]],\n'
        '  "reason": "краткое объяснение почему топ-1 выбран (до 30 слов)"\n'
        "}\n\n"
        "Отвечай ТОЛЬКО JSON, без дополнительного текста."
    )
    
    if restaurant:
        user_prompt = (
            f"Ресторан: {restaurant}\n"
            f"Блюдо: {dish}\n\n"
            f"Кандидаты:\n{candidates_text}\n\n"
            "Ранжируй кандидатов по качеству для извлечения нутриции."
        )
    else:
        user_prompt = (
            f"Блюдо: {dish}\n\n"
            f"Кандидаты:\n{candidates_text}\n\n"
            "Ранжируй кандидатов по качеству для извлечения нутриции. Ресторан неизвестен."
        )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    
    try:
        raw_response = await chat_completion(messages)
    except Exception as e:
        logger.warning(f"restaurant LLM ranking failed: {e}")
        return None
    
    # Парсим JSON
    json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
    if not json_match:
        logger.warning(f"restaurant LLM ranking: no JSON in response: {raw_response[:200]}")
        return None
    
    try:
        data = json.loads(json_match.group(0))
        ranking = data.get("ranking", [])
        reason = data.get("reason", "")
        
        if not isinstance(ranking, list) or len(ranking) == 0:
            logger.warning(f"restaurant LLM ranking: invalid ranking: {ranking}")
            return None
        
        # Проверяем, что все индексы валидны
        valid_indices = [i for i in ranking if isinstance(i, int) and 0 <= i < len(candidates)]
        if len(valid_indices) != len(ranking):
            logger.warning(f"restaurant LLM ranking: some indices invalid, using valid ones only")
            ranking = valid_indices
        
        return {
            "ranking": ranking,
            "reason": reason.strip(),
        }
    except json.JSONDecodeError as e:
        logger.warning(f"restaurant LLM ranking: JSON parse error: {e}, raw: {raw_response[:200]}")
        return None


async def estimate_restaurant_meal_with_web(
    restaurant: Optional[str],
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
    if not dish or not dish.strip():
        logger.warning("estimate_restaurant_meal_with_web: missing dish")
        return None
    
    # Нормализуем dish
    dish = dish.strip()
    
    if not settings.tavily_api_key:
        logger.warning("estimate_restaurant_meal_with_web: missing tavily_api_key")
        return None
    
    try:
        # Безопасная функция для извлечения строк
        def _s(x):
            return (x or "").strip() if isinstance(x, str) else ""
        
        # 1) Собираем кандидатов из нескольких запросов
        candidates = await _collect_candidates(
            restaurant=restaurant,
            dish=dish,
            api_key=settings.tavily_api_key
        )
        
        if not candidates:
            logger.info("restaurant: no candidates collected")
            return None
        
        # Фильтр рецептов: исключаем результаты с рецептами/блогами
        recipe_keywords = ["recipe", "рецепт", "how-to", "how to", "как приготовить", "рецепт приготовления"]
        
        def _is_recipe_result(candidate):
            """Проверяет, является ли кандидат рецептом/блогом."""
            title = _s(candidate.get("title", "")).lower()
            url = _s(candidate.get("url", "")).lower()
            for keyword in recipe_keywords:
                if keyword in title or keyword in url:
                    return True
            return False
        
        # Фильтруем рецепты
        filtered_candidates = [c for c in candidates if not _is_recipe_result(c)]
        
        if not filtered_candidates:
            logger.info("restaurant: all candidates filtered as recipes")
            return None
        
        # Логируем топ-3 кандидата до ранжирования
        logger.info(f"restaurant top-3 candidates before ranking:")
        for idx, cand in enumerate(filtered_candidates[:3]):
            logger.info(f"  [{idx}] {cand.get('url')} - {cand.get('title')}")
        
        # 2) Ранжируем кандидатов с помощью LLM
        ranking_result = await _rank_sources_with_llm(
            restaurant=restaurant,
            dish=dish,
            candidates=filtered_candidates
        )
        
        if not ranking_result:
            logger.warning("restaurant: LLM ranking failed, using original order")
            ranked_indices = list(range(len(filtered_candidates)))
        else:
            ranked_indices = ranking_result.get("ranking", [])
            reason = ranking_result.get("reason", "")
            logger.info(f"restaurant LLM ranking: top-5 indices={ranked_indices[:5]}, reason={reason}")
        
        # 3) Пробуем извлечь КБЖУ из ранжированных кандидатов
        # Helper функция для проверки наличия маркеров КБЖУ
        def _has_nutrition_signals(text: str) -> bool:
            """Проверяет наличие маркеров КБЖУ в тексте."""
            text_lower = text.lower()
            markers = [
                "ккал", "калорий", "энергетичес", "пищевая ценность", "белки", "жиры", "углеводы",
                "kcal", "calories", "nutrition", "protein", "fat", "carb"
            ]
            return any(marker in text_lower for marker in markers)
        
        # Пробуем первые 5 кандидатов из ранжированного списка
        max_candidates_to_try = min(5, len(ranked_indices))
        ranking_reason = ranking_result.get("reason", "") if ranking_result else ""
        
        for try_idx in range(max_candidates_to_try):
            candidate_idx = ranked_indices[try_idx]
            if candidate_idx >= len(filtered_candidates):
                continue
            
            candidate = filtered_candidates[candidate_idx]
            candidate_url = _s(candidate.get("url", ""))
            candidate_title = _s(candidate.get("title", ""))
            candidate_content = _s(candidate.get("content", ""))
            candidate_raw_content = _s(candidate.get("raw_content", ""))
            
            # Формируем контекст из этого кандидата
            candidate_context_parts = []
            if candidate_title:
                candidate_context_parts.append(candidate_title)
            if candidate_url:
                candidate_context_parts.append(candidate_url)
            if candidate_content:
                # Ограничиваем content до разумной длины
                if len(candidate_content) > 1500:
                    candidate_content = candidate_content[:1500] + "..."
                candidate_context_parts.append(candidate_content)
            if candidate_raw_content:
                # Ограничиваем raw_content до разумной длины
                if len(candidate_raw_content) > 1500:
                    candidate_raw_content = candidate_raw_content[:1500] + "..."
                candidate_context_parts.append(candidate_raw_content)
            
            candidate_context = "\n".join(candidate_context_parts)
            
            # Проверяем наличие маркеров КБЖУ
            has_signals = _has_nutrition_signals(candidate_context)
            logger.info(f"restaurant candidate[{try_idx}] (ranked_idx={candidate_idx}) url={candidate_url}, has_nutrition_signals={has_signals}")
            
            if not has_signals:
                logger.info(f"restaurant candidate[{try_idx}] extraction skipped: no nutrition signals")
                continue
            
            if not candidate_context.strip():
                logger.info(f"restaurant candidate[{try_idx}] extraction skipped: empty context")
                continue
            
            # Ограничиваем размер контекста для LLM
            if len(candidate_context) > 2000:
                candidate_context = candidate_context[:2000] + "..."
            
            # Формируем промпт для LLM extraction
            system_prompt = (
                "Ты нутриционный ассистент. Тебе даётся название ресторана/кафе, название блюда "
                "и текст с веб-страницы. На основе этого извлеки КБЖУ (калории, белки, жиры, углеводы).\n\n"
                "ВАЖНО: ты можешь вернуть данные ТОЛЬКО если они явно указаны в переданном тексте. "
                "Если в тексте нет цифр КБЖУ - верни calories=0 и evidence_snippets=[].\n\n"
                "Отвечай СТРОГО в формате JSON с полями:\n"
                "- calories: number (калории, если найдены в тексте, иначе 0)\n"
                "- protein_g: number (белки в граммах, если найдены, иначе 0)\n"
                "- fat_g: number (жиры в граммах, если найдены, иначе 0)\n"
                "- carbs_g: number (углеводы в граммах, если найдены, иначе 0)\n"
                "- portion_grams: number или null (вес порции в граммах, если указан)\n"
                "- accuracy_level: строка \"HIGH\" (всегда HIGH, так как данные из источника)\n"
                "- notes: строка с кратким пояснением (опционально)\n"
                "- evidence_snippets: массив строк (КОРОТКИЕ, до 20-30 слов, ДОСЛОВНЫЕ фрагменты из текста, которые подтверждают цифры)\n\n"
                "Правила:\n"
                "1) Если в тексте нет цифр КБЖУ - верни calories=0, evidence_snippets=[]\n"
                "2) Если calories>0, evidence_snippets ДОЛЖЕН быть НЕ пустым\n"
                "3) Каждый evidence_snippet должен быть ДОСЛОВНОЙ подстрокой из переданного текста\n"
                "4) evidence_snippets должны быть короткими (до 20-30 слов каждый)\n"
                "5) Если значения указаны на 100г, а нужна порция - укажи portion_grams и пересчитай на порцию\n\n"
                "Отвечай ТОЛЬКО JSON, без дополнительного текста."
            )
            
            if restaurant:
                user_prompt = (
                    f"Ресторан: {restaurant}\n"
                    f"Блюдо: {dish}\n\n"
                    f"Текст с веб-страницы:\n{candidate_context}\n\n"
                    "Извлеки КБЖУ для этого блюда. Верни calories=0, если цифр нет в тексте."
                )
            else:
                user_prompt = (
                    f"Блюдо: {dish}\n\n"
                    f"Текст с веб-страницы:\n{candidate_context}\n\n"
                    "Извлеки КБЖУ для этого блюда. Ресторан неизвестен. Верни calories=0, если цифр нет в тексте."
                )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            
            # Вызываем LLM
            try:
                raw_response = await chat_completion(messages)
            except Exception as e:
                logger.warning(f"restaurant candidate[{try_idx}] LLM call failed: {e}")
                continue
            
            # Парсим JSON
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if not json_match:
                logger.info(f"restaurant candidate[{try_idx}] extraction failed: no JSON in response")
                continue
            
            try:
                data = json.loads(json_match.group(0))
            except json.JSONDecodeError as e:
                logger.info(f"restaurant candidate[{try_idx}] extraction failed: JSON parse error: {e}")
                continue
            
            # Извлекаем данные
            calories_val = data.get("calories", 0)
            protein_g_val = data.get("protein_g", 0)
            fat_g_val = data.get("fat_g", 0)
            carbs_g_val = data.get("carbs_g", 0)
            portion_grams_val = data.get("portion_grams")
            evidence_snippets = data.get("evidence_snippets", [])
            notes_raw = data.get("notes", "").strip()
            
            # Проверяем calories > 0
            try:
                calories = float(calories_val)
            except (ValueError, TypeError):
                calories = 0.0
            
            if calories <= 0:
                logger.info(f"restaurant candidate[{try_idx}] extraction failed: calories={calories}")
                continue
            
            # Проверяем evidence_snippets
            if not isinstance(evidence_snippets, list) or len(evidence_snippets) == 0:
                logger.info(f"restaurant candidate[{try_idx}] extraction failed: empty evidence_snippets")
                continue
            
            # Проверяем, что каждый evidence_snippet встречается в context (защита от галлюцинаций)
            context_lower = candidate_context.lower()
            all_evidence_valid = True
            for snippet in evidence_snippets:
                if not isinstance(snippet, str):
                    all_evidence_valid = False
                    break
                snippet_clean = snippet.strip()
                if len(snippet_clean) < 10:  # Слишком короткий фрагмент
                    all_evidence_valid = False
                    break
                # Проверяем, что snippet встречается в context (case-insensitive)
                if snippet_clean.lower() not in context_lower:
                    logger.info(f"restaurant candidate[{try_idx}] extraction failed: evidence_snippet not found in context: {snippet_clean[:50]}")
                    all_evidence_valid = False
                    break
            
            if not all_evidence_valid:
                logger.info(f"restaurant candidate[{try_idx}] extraction failed: invalid evidence_snippets")
                continue
            
            # Все проверки пройдены - возвращаем результат
            try:
                protein_g = float(protein_g_val) if protein_g_val is not None else 0.0
                fat_g = float(fat_g_val) if fat_g_val is not None else 0.0
                carbs_g = float(carbs_g_val) if carbs_g_val is not None else 0.0
            except (ValueError, TypeError):
                protein_g = 0.0
                fat_g = 0.0
                carbs_g = 0.0
            
            portion_grams = None
            if portion_grams_val is not None:
                try:
                    portion_grams = float(portion_grams_val)
                    if portion_grams <= 0:
                        portion_grams = None
                except (ValueError, TypeError):
                    portion_grams = None
            
            # Формируем notes
            if notes_raw:
                notes = notes_raw
            else:
                notes = "Данные извлечены из web-источника."
            
            # Округляем значения
            calories = round(float(calories))
            protein_g = round(float(protein_g), 1)
            fat_g = round(float(fat_g), 1)
            carbs_g = round(float(carbs_g), 1)
            if portion_grams:
                portion_grams = round(portion_grams, 1)
            
            description = f"{dish} в {restaurant}" if restaurant else dish
            
            logger.info(f"restaurant extraction success=True, chosen_url={candidate_url}")
            
            return {
                "description": description,
                "calories": calories,
                "protein_g": protein_g,
                "fat_g": fat_g,
                "carbs_g": carbs_g,
                "portion_grams": portion_grams,
                "accuracy_level": "HIGH",
                "notes": notes,
                "source_url": candidate_url,
            }
        
        # Ни один кандидат не прошёл проверку
        logger.info(f"restaurant extraction success=False: no valid candidates")
        return None
        
    except Exception as e:
        logger.error(f"Error in estimate_restaurant_meal_with_web: {e}", exc_info=True)
        return None

