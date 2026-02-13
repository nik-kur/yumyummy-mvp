import json
import logging
import re
from datetime import date as date_type

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.core.config import settings

logger = logging.getLogger(__name__)
from app.deps import get_db
from app.db.session import SessionLocal
from app.models.user import User
from app.models.user_day import UserDay
from app.models.meal_entry import MealEntry
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.schemas.meal import MealCreate, MealRead, MealUpdate, DaySummary

from app.services.llm_client import chat_completion
from app.services.meal_parser import parse_meal_text
from app.services.nutrition_lookup import NutritionQuery, nutrition_lookup
from app.services.web_nutrition import estimate_nutrition_with_web
from app.services.web_restaurant import estimate_restaurant_meal_with_web
from app.services.openai_websearch_restaurant import estimate_restaurant_meal_with_openai_websearch
from app.schemas.ai import ParseMealRequest, MealParsed, ProductMealRequest, RestaurantMealRequest, RestaurantTextRequest, AgentRequest, AgentResponse, WorkflowRunRequest, WorkflowRunResponse, WorkflowTotals, WorkflowItem
from app.services.agent_runner import run_agent
from app.agent_runner import run_yumyummy_workflow, WorkflowNotInstalledError
from app.services.agent_persist import persist_agent_result
from app.ai.stt_client import transcribe_audio
from anyio import to_thread
from openai import OpenAI
import uuid

# Import OpenAI exceptions - handle both old and new SDK versions
try:
    from openai import RateLimitError, APIConnectionError, APIError
except ImportError:
    # Fallback for older SDK versions
    try:
        from openai.error import RateLimitError, APIConnectionError, APIError
    except ImportError:
        # If exceptions don't exist, define dummy classes
        class RateLimitError(Exception):
            pass
        class APIConnectionError(Exception):
            pass
        class APIError(Exception):
            pass

app = FastAPI(title="YumYummy API")


@app.on_event("startup")
def run_migrations():
    """Auto-apply Alembic migrations on startup."""
    import subprocess
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            logger.info(f"[STARTUP] Alembic migrations applied successfully: {result.stdout.strip()}")
        else:
            logger.error(f"[STARTUP] Alembic migration failed: {result.stderr.strip()}")
    except Exception as e:
        logger.error(f"[STARTUP] Alembic migration error: {e}")


# Include context API router for agent tools
from app.api.context import router as context_router
app.include_router(context_router)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": "YumYummy",
        "db_url_present": bool(settings.database_url),
    }

@app.get("/ai/test")
async def ai_test():
    """
    Тестовый endpoint, чтобы проверить связку с OpenAI.
    """
    messages = [
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": "Ответь одной короткой фразой, что такое проект YumYummy."},
    ]
    answer = await chat_completion(messages)
    return {"answer": answer}

@app.post("/ai/parse_meal", response_model=MealParsed)
async def ai_parse_meal(payload: ParseMealRequest):
    """
    Получить оценку КБЖУ по тексту описания приёма пищи.
    Пока только парсим текст, ничего не записываем в БД.
    """
    try:
        parsed = await parse_meal_text(payload.text)
    except ValueError as e:
        # Если LLM вернул мусор, говорим об этом клиенту
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail=str(e))

    return MealParsed(**parsed)


@app.post("/ai/voice_parse_meal")
async def ai_voice_parse_meal(audio: UploadFile = File(...)):
    """
    Получить оценку КБЖУ по голосовому сообщению.
    Делает STT через OpenAI, затем парсит текст как /ai/parse_meal.
    """
    try:
        file_bytes = await audio.read()
    except Exception as e:
        logger.error(f"[VOICE] Error reading audio file: {e}")
        raise HTTPException(status_code=400, detail="Не удалось прочитать аудиофайл")

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Пустой аудиофайл")

    try:
        transcript = await transcribe_audio(
            file_bytes=file_bytes,
            filename=audio.filename or "voice.ogg",
        )
    except Exception as e:
        logger.error(f"[VOICE] Error transcribing audio: {e}")
        raise HTTPException(status_code=500, detail="Не удалось распознать речь")

    if not transcript.strip():
        raise HTTPException(status_code=400, detail="Не удалось распознать речь")

    # Пробуем product pipeline (web-search-first) на основе transcript
    product_result = None
    try:
        payload = ProductMealRequest(
            name=transcript.strip(),
            brand=None,
            store=None,
            locale="ru-RU",
        )
        product_result = await _product_parse_logic(payload)
        
        # Если product pipeline вернул результат с WEB или OPENFOODFACTS - используем его
        source_provider = product_result.get("source_provider", "")
        if source_provider and source_provider in ("WEB", "OPENFOODFACTS", "WEB_SEARCH_LLM"):
            logger.info(f"[VOICE] Using product pipeline result with source_provider={source_provider}")
            return {
                "transcript": transcript,
                "description": product_result.get("description", ""),
                "calories": product_result.get("calories", 0.0),
                "protein_g": product_result.get("protein_g", 0.0),
                "fat_g": product_result.get("fat_g", 0.0),
                "carbs_g": product_result.get("carbs_g", 0.0),
                "accuracy_level": product_result.get("accuracy_level", "ESTIMATE"),
                "source_provider": source_provider,
                "notes": product_result.get("notes", ""),
                "source_url": product_result.get("source_url"),
            }
        else:
            # Если product pipeline вернул LLM_ESTIMATE или пустой source_provider - fallback
            logger.info(f"[VOICE] Product pipeline returned {source_provider}, falling back to LLM")
    except Exception as e:
        logger.warning(f"[VOICE] Product pipeline failed: {e}, falling back to LLM")
    
    # Fallback: если product pipeline вернул LLM_ESTIMATE или упал - используем обычный parse_meal_text
    try:
        parsed = await parse_meal_text(transcript)
    except ValueError as e:
        logger.error(f"[VOICE] Error parsing meal text: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "transcript": transcript,
        "description": parsed.get("description", ""),
        "calories": parsed.get("calories", 0.0),
        "protein_g": parsed.get("protein_g", 0.0),
        "fat_g": parsed.get("fat_g", 0.0),
        "carbs_g": parsed.get("carbs_g", 0.0),
        "accuracy_level": parsed.get("accuracy_level", "ESTIMATE"),
        "source_provider": "LLM_ESTIMATE",
        "notes": parsed.get("notes", ""),
        "source_url": None,
    }


async def _product_parse_logic(payload: ProductMealRequest) -> dict:
    """
    Внутренняя логика парсинга продукта (WebSearch -> OpenFoodFacts -> LLM fallback).
    Возвращает dict с полями: description, calories, protein_g, fat_g, carbs_g,
    accuracy_level, source_provider, notes, source_url.
    """
    # 1) Пробуем Web Search (только для name-based запросов, без barcode)
    if payload.name and not payload.barcode:
        try:
            web_result = await estimate_nutrition_with_web(
                name=payload.name,
                brand=payload.brand,
                store=payload.store,
                locale=payload.locale
            )
            
            if web_result and web_result.get("calories", 0) > 0:
                # Округляем значения (уже округлены в web_nutrition, но на всякий случай)
                calories = round(web_result.get("calories", 0.0))
                protein_g = round(web_result.get("protein_g", 0.0), 1)
                fat_g = round(web_result.get("fat_g", 0.0), 1)
                carbs_g = round(web_result.get("carbs_g", 0.0), 1)
                
                source_url = web_result.get("source_url")
                logger.info(f"[BACKEND] Web result source_url: {source_url}, type: {type(source_url)}")
                
                return {
                    "description": web_result.get("description") or payload.name,
                    "calories": calories,
                    "protein_g": protein_g,
                    "fat_g": fat_g,
                    "carbs_g": carbs_g,
                    "accuracy_level": web_result.get("accuracy_level", "ESTIMATE"),
                    "source_provider": "WEB",
                    "notes": web_result.get("notes", ""),
                    "source_url": source_url,
                }
        except Exception as e:
            logger.warning(f"[BACKEND] Web search failed: {e}, falling back")
    
    # 2) Пробуем через nutrition_lookup (OpenFoodFacts)
    try:
        query = NutritionQuery(
            barcode=payload.barcode,
            name=payload.name,
            brand=payload.brand,
            store=payload.store,
            locale=payload.locale,
        )
        
        result = await nutrition_lookup(query)
        
        # Если нашли в OpenFoodFacts
        if result.found and result.calories is not None and result.calories > 0:
            # Формируем описание
            parts = [result.name or payload.name or "Продукт"]
            if result.brand or payload.brand:
                parts.append(f"бренд: {result.brand or payload.brand}")
            if payload.store:
                parts.append(f"магазин: {payload.store}")
            description = ", ".join(parts)
            
            # Формируем notes
            notes = "Данные из OpenFoodFacts"
            if result.portion_grams and result.portion_grams != 100.0:
                notes += f" (пересчитано на упаковку {result.portion_grams:.0f} г, исходно на 100 г)"
            
            # Округляем значения
            calories = round(result.calories or 0.0)
            protein_g = round(result.protein_g or 0.0, 1)
            fat_g = round(result.fat_g or 0.0, 1)
            carbs_g = round(result.carbs_g or 0.0, 1)
            
            return {
                "description": description,
                "calories": calories,
                "protein_g": protein_g,
                "fat_g": fat_g,
                "carbs_g": carbs_g,
                "accuracy_level": result.accuracy_level,
                "source_provider": "OPENFOODFACTS",
                "notes": notes,
                "source_url": result.source_url,
            }
    except Exception as e:
        logger.warning(f"[BACKEND] OpenFoodFacts lookup failed: {e}, falling back")
    
    # 3) Fallback на LLM
    desc_parts = []
    if payload.name:
        desc_parts.append(payload.name)
    if payload.brand:
        desc_parts.append(f"бренд {payload.brand}")
    if payload.store:
        desc_parts.append(f"из магазина {payload.store}")
    if payload.barcode:
        desc_parts.append(f"штрихкод {payload.barcode}")
    
    fallback_text = "упаковочный продукт: " + ", ".join(desc_parts)
    
    try:
        parsed = await parse_meal_text(fallback_text)
    except ValueError as e:
        logger.error(f"[BACKEND] LLM fallback failed: {e}")
        raise
    
    # Округляем значения
    calories = round(parsed.get("calories", 0.0))
    protein_g = round(parsed.get("protein_g", 0.0), 1)
    fat_g = round(parsed.get("fat_g", 0.0), 1)
    carbs_g = round(parsed.get("carbs_g", 0.0), 1)
    
    return {
        "description": parsed.get("description") or fallback_text,
        "calories": calories,
        "protein_g": protein_g,
        "fat_g": fat_g,
        "carbs_g": carbs_g,
        "accuracy_level": parsed.get("accuracy_level", "ESTIMATE"),
        "source_provider": "LLM_ESTIMATE",
        "notes": parsed.get("notes", ""),
        "source_url": None,
    }


@app.post("/ai/product_parse_meal")
async def ai_product_parse_meal(payload: ProductMealRequest):
    """
    Получить оценку КБЖУ по штрихкоду или названию продукта.
    Приоритет: WebSearch -> OpenFoodFacts -> LLM fallback.
    """
    if not payload.barcode and not payload.name:
        raise HTTPException(
            status_code=400,
            detail="Нужно указать либо штрихкод, либо название продукта"
        )
    
    return await _product_parse_logic(payload)


@app.post("/ai/restaurant_parse_meal")
async def ai_restaurant_parse_meal(payload: RestaurantMealRequest):
    """
    Получить оценку КБЖУ блюда из ресторана/кафе/доставки.
    Приоритет: WebSearch -> LLM fallback.
    """
    # 1) Пробуем Web Search
    web_result = await estimate_restaurant_meal_with_web(
        restaurant=payload.restaurant,
        dish=payload.dish,
        locale=payload.locale
    )
    
    # Если web_result есть и calories > 0 - успешное извлечение из web
    if web_result and web_result.get("calories", 0) > 0:
        # Округляем значения (уже округлены в web_restaurant, но на всякий случай)
        calories = round(web_result.get("calories", 0.0))
        protein_g = round(web_result.get("protein_g", 0.0), 1)
        fat_g = round(web_result.get("fat_g", 0.0), 1)
        carbs_g = round(web_result.get("carbs_g", 0.0), 1)
        
        source_url = web_result.get("source_url")
        logger.info(f"[BACKEND] Restaurant web result source_url: {source_url}, type: {type(source_url)}")
        
        return {
            "description": web_result.get("description") or f"{payload.dish} в {payload.restaurant}",
            "calories": calories,
            "protein_g": protein_g,
            "fat_g": fat_g,
            "carbs_g": carbs_g,
            "accuracy_level": web_result.get("accuracy_level", "ESTIMATE"),
            "notes": web_result.get("notes", ""),
            "source_provider": "WEB_RESTAURANT",
            "source_url": source_url,
        }
    
    # 2) Fallback на LLM (если web_result is None или calories=0)
    fallback_text = f"блюдо из ресторана: {payload.dish} в {payload.restaurant}"
    
    try:
        parsed = await parse_meal_text(fallback_text)
    except ValueError as e:
        logger.error(f"[BACKEND] LLM fallback failed for restaurant meal: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    # Округляем значения
    calories = round(parsed.get("calories", 0.0))
    protein_g = round(parsed.get("protein_g", 0.0), 1)
    fat_g = round(parsed.get("fat_g", 0.0), 1)
    carbs_g = round(parsed.get("carbs_g", 0.0), 1)
    
    return {
        "description": parsed.get("description") or fallback_text,
        "calories": calories,
        "protein_g": protein_g,
        "fat_g": fat_g,
        "carbs_g": carbs_g,
        "accuracy_level": parsed.get("accuracy_level", "ESTIMATE"),
        "source_provider": "LLM_RESTAURANT_ESTIMATE",
        "notes": parsed.get("notes", ""),
        "source_url": None,
    }


@app.post("/ai/restaurant_parse_text")
async def ai_restaurant_parse_text(payload: RestaurantTextRequest):
    """
    Получить оценку КБЖУ блюда из ресторана по свободному тексту.
    LLM парсит текст, извлекает restaurant и dish, затем использует web-search.
    Приоритет: WebSearch -> LLM fallback.
    """
    try:
        text = payload.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Текст не может быть пустым")
        
        # 1) LLM парсит текст в JSON: restaurant, dish, city
        parse_prompt = (
            "Ты ассистент. Тебе дают текст с описанием блюда из ресторана/кафе/доставки. "
            "Извлеки из текста название ресторана (если есть) и название блюда.\n\n"
            "Отвечай СТРОГО в формате JSON с полями:\n"
            "- restaurant: строка или null (название ресторана/кафе/доставки, если указано)\n"
            "- dish: строка (название блюда, ПОЛНОЕ название со всеми деталями)\n"
            "- city: строка или null (город, если указан)\n\n"
            "Правила:\n"
            "1) Если ресторан не удаётся выделить, restaurant=null, dish=исходный текст (убери только предлоги 'в/из/at/in' если они есть в начале)\n"
            "2) Если в тексте есть 'в/из/at/in' - это может указывать на ресторан\n"
            "3) dish должно содержать ПОЛНОЕ название блюда со всеми деталями (например, 'бенедикт с ветчиной', а не просто 'бенедикт')\n"
            "4) Примеры:\n"
            "   'сырники из кофемании' -> {\"restaurant\": \"кофемания\", \"dish\": \"сырники\", \"city\": null}\n"
            "   'бенедикт с ветчиной из Кофемании' -> {\"restaurant\": \"Кофемания\", \"dish\": \"бенедикт с ветчиной\", \"city\": null}\n"
            "   'паста карбонара в vapiano' -> {\"restaurant\": \"vapiano\", \"dish\": \"паста карбонара\", \"city\": null}\n"
            "   'бургер' -> {\"restaurant\": null, \"dish\": \"бургер\", \"city\": null}\n\n"
            "Отвечай ТОЛЬКО JSON, без дополнительного текста."
        )
        
        try:
            parse_messages = [
                {"role": "system", "content": parse_prompt},
                {"role": "user", "content": f"Текст: {text}"},
            ]
            parse_response = await chat_completion(parse_messages)
            
            # Парсим JSON из ответа LLM
            json_match = re.search(r'\{.*\}', parse_response, re.DOTALL)
            if not json_match:
                logger.warning(f"LLM parse response does not contain JSON: {parse_response[:200]}")
                # Fallback: используем весь текст как dish
                restaurant = None
                dish = text
            else:
                try:
                    parse_data = json.loads(json_match.group(0))
                    restaurant = parse_data.get("restaurant")
                    dish = parse_data.get("dish", text).strip()
                    if not dish:
                        dish = text
                    logger.info(f"[BACKEND] Restaurant text parsed: restaurant={restaurant}, dish={dish}")
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse LLM JSON: {e}, raw: {parse_response[:200]}")
                    restaurant = None
                    dish = text
                    logger.info(f"[BACKEND] Restaurant text parse failed, using fallback: restaurant=None, dish={dish}")
        except Exception as e:
            logger.warning(f"Error parsing text with LLM: {e}, using full text as dish")
            restaurant = None
            dish = text
        
        # 2) Вызываем существующую логику restaurant web estimation
        try:
            web_result = await estimate_restaurant_meal_with_web(
                restaurant=restaurant,
                dish=dish,
                locale=payload.locale
            )
        except Exception as e:
            logger.error(f"[BACKEND] Error in estimate_restaurant_meal_with_web: {e}", exc_info=True)
            # Продолжаем с fallback на LLM
            web_result = None
        
        # Если web_result есть и calories > 0 - успешное извлечение из web
        if web_result and web_result.get("calories", 0) > 0:
            # Округляем значения (уже округлены в web_restaurant, но на всякий случай)
            calories = round(web_result.get("calories", 0.0))
            protein_g = round(web_result.get("protein_g", 0.0), 1)
            fat_g = round(web_result.get("fat_g", 0.0), 1)
            carbs_g = round(web_result.get("carbs_g", 0.0), 1)
            
            source_url = web_result.get("source_url")
            logger.info(f"[BACKEND] Restaurant text web result source_url: {source_url}, type: {type(source_url)}")
            
            return {
                "description": web_result.get("description") or (f"{dish} в {restaurant}" if restaurant else dish),
                "calories": calories,
                "protein_g": protein_g,
                "fat_g": fat_g,
                "carbs_g": carbs_g,
                "accuracy_level": web_result.get("accuracy_level", "ESTIMATE"),
                "notes": web_result.get("notes", ""),
                "source_provider": "WEB_RESTAURANT",
                "source_url": source_url,
            }
        
        # 3) Fallback на LLM (если web_result is None или calories=0)
        if restaurant:
            fallback_text = f"блюдо из ресторана: {dish} в {restaurant}"
        else:
            fallback_text = f"блюдо: {dish}"
        
        try:
            parsed = await parse_meal_text(fallback_text)
        except ValueError as e:
            logger.error(f"[BACKEND] LLM fallback failed for restaurant text: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.error(f"[BACKEND] Unexpected error in LLM fallback: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Ошибка при обработке запроса")
        
        # Округляем значения
        calories = round(parsed.get("calories", 0.0))
        protein_g = round(parsed.get("protein_g", 0.0), 1)
        fat_g = round(parsed.get("fat_g", 0.0), 1)
        carbs_g = round(parsed.get("carbs_g", 0.0), 1)
        
        return {
            "description": parsed.get("description") or fallback_text,
            "calories": calories,
            "protein_g": protein_g,
            "fat_g": fat_g,
            "carbs_g": carbs_g,
            "accuracy_level": parsed.get("accuracy_level", "ESTIMATE"),
            "source_provider": "LLM_RESTAURANT_ESTIMATE",
            "notes": parsed.get("notes", ""),
            "source_url": None,
        }
    except HTTPException:
        # Пробрасываем HTTPException как есть
        raise
    except Exception as e:
        logger.error(f"[BACKEND] Unexpected error in restaurant_parse_text: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка при обработке запроса")


@app.post("/ai/restaurant_parse_text_openai")
async def ai_restaurant_parse_text_openai(payload: RestaurantTextRequest):
    """
    EXPERIMENTAL: Получить оценку КБЖУ блюда из ресторана через OpenAI Responses API с web_search.
    Это Path A для A/B тестирования - параллельно существующему подходу на основе Tavily.
    
    Использует двухшаговый поиск: сначала находит официальный URL, затем извлекает нутрицию с проверкой evidence.
    """
    try:
        text = payload.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Текст не может быть пустым")
        
        # Определяем стратегию поиска и domain hints
        text_lower = text.lower()
        domain_hint_candidates = []
        strategy = None
        
        # Проверяем known_official_domain case
        if "кофеман" in text_lower:
            domain_hint_candidates = ["coffeemania.ru"]
            strategy = "official_domain"
            logger.info(f"[BACKEND] Domain hint candidates: {domain_hint_candidates}, strategy=official_domain")
        elif "joe and the juice" in text_lower or "joe&thejuice" in text_lower:
            domain_hint_candidates = ["joeandthejuice.is"]
            strategy = "official_domain"
            logger.info(f"[BACKEND] Domain hint candidates: {domain_hint_candidates}, strategy=official_domain")
        
        # Проверяем global_chain case
        global_chains = [
            ("starbucks", "старбакс"),
            ("mcdonald", "макдон"),
            ("kfc", "кфс"),
            ("burger king", "бургер кинг"),
            ("subway", "сабвей")
        ]
        
        for chain_en, chain_ru in global_chains:
            if chain_en in text_lower or chain_ru in text_lower:
                if strategy is None:
                    strategy = "global_chain"
                    logger.info(f"[BACKEND] Detected global chain: {chain_en}, strategy=global_chain")
                break
        
        # Если не определили стратегию, используем по умолчанию global_chain
        if strategy is None:
            strategy = "global_chain"
            logger.info(f"[BACKEND] No specific strategy detected, defaulting to strategy=global_chain")
        
        # Базовый system prompt (общий для обеих стратегий)
        base_system_prompt = (
            "You are a nutrition researcher. Your task is to find accurate nutritional information "
            "for restaurant dishes using web search.\n\n"
            "CRITICAL RULES:\n"
            "1. You MUST use web_search tool.\n"
            "2. Prefer official restaurant site or official menu item page.\n"
            "3. If official site has no nutrition, then prefer reputable delivery/menu pages (UberEats, Yandex.Eda, etc.).\n"
            "4. Do NOT use user-generated calorie databases (FatSecret, MyFitnessPal, EatThisMuch, health-diet) as sources.\n"
            "5. Return source_url only if the page contains nutrition numbers and you can quote evidence snippets from it.\n"
            "6. Return STRICT JSON only, no additional text.\n\n"
            "JSON format:\n"
            "{\n"
            '  "restaurant": str|null,\n'
            '  "dish": str,\n'
            '  "description": "full dish name with restaurant",\n'
            '  "portion_grams": number|null,\n'
            '  "calories": number,\n'
            '  "protein_g": number,\n'
            '  "fat_g": number,\n'
            '  "carbs_g": number,\n'
            '  "accuracy_level": "HIGH"|"ESTIMATE",\n'
            '  "source_url": str|null,\n'
            '  "evidence_snippets": [str, ...],\n'
            '  "notes": str\n'
            "}\n\n"
            "RULES:\n"
            "- Set accuracy_level=\"HIGH\" only if source_url is official/delivery/menu page with evidence_snippets.\n"
            "- Otherwise accuracy_level=\"ESTIMATE\" and source_url=null.\n"
            "- evidence_snippets must be 2-4 short verbatim strings from the page that include the numbers.\n"
        )
        
        # Формируем промпты в зависимости от стратегии
        if strategy == "official_domain" and domain_hint_candidates:
            # Стратегия для известных официальных доменов
            domain_hint = domain_hint_candidates[0]
            
            system_prompt = base_system_prompt + (
                "\nSPECIFIC INSTRUCTIONS FOR OFFICIAL DOMAIN SEARCH:\n"
                "- You MUST run exactly 1 web_search query with site:{domain} + dish name first.\n"
                "- If that fails to find nutrition, run one more query without site: restriction but include the domain as keyword.\n"
                "- STRONGLY prefer pages on {domain} domain.\n"
                "- Return best single source_url from {domain} if possible.\n"
            ).format(domain=domain_hint)
            
            user_prompt_parts = [
                f"Input query: {text}\n\n",
                "OFFICIAL DOMAIN SEARCH PROCESS:\n",
                f"1) Identify restaurant name and dish name from the query.\n",
                f"2) Run EXACTLY 1 web_search query: site:{domain_hint} [dish name]\n",
                f"3) If that doesn't find nutrition, run 1 more query: {domain_hint} [dish name] nutrition (without site: restriction)\n",
                f"4) Prefer pages from {domain_hint} domain.\n",
                f"5) Extract nutrition (calories/protein/fat/carbs and portion grams) from the best page found.\n",
                f"6) Provide evidence_snippets: 2-4 short verbatim strings from the page that include the numbers.\n",
                f"7) Output STRICT JSON with the format specified above.\n\n",
                "If you only find user-generated databases, do not cite them as source_url."
            ]
            user_prompt = "".join(user_prompt_parts)
            
        else:
            # Стратегия для глобальных сетей (multi-query с региональными вариантами)
            system_prompt = base_system_prompt + (
                "\nSPECIFIC INSTRUCTIONS FOR GLOBAL CHAIN SEARCH:\n"
                "- You MUST perform at least 3 separate web_search calls with different queries.\n"
                "- You MUST include at least 2 English queries even if user input is in Russian.\n"
                "- For global chains: explicitly try US and UK/EU variants if the first attempt fails.\n"
                "- Prefer official nutrition pages, nutrition PDFs, or official menu item pages that show calories/macros and serving size.\n"
            )
            
            user_prompt_parts = [
                f"Input query: {text}\n\n",
                "GLOBAL CHAIN SEARCH PROCESS:\n",
                "1) Identify restaurant name and dish name from the query.\n",
                "2) Generate at least 3 different search queries:\n",
                "   - Include queries in both Russian (if applicable) and English.\n",
                "   - For global chains, include region variants (US, UK, EU) if applicable.\n",
                "   - Examples: \"[restaurant] [dish] nutrition\", \"[restaurant] [dish] calories\", \"[restaurant] [dish] menu nutrition facts\"\n",
                "3) Run web_search with at least 3 of these queries (prioritize official sources).\n",
                "4) Extract nutrition (calories/protein/fat/carbs and portion grams) from the best page found.\n",
                "5) Provide evidence_snippets: 2-4 short verbatim strings from the page that include the numbers.\n",
                "6) Output STRICT JSON with the format specified above.\n\n",
                "If you only find user-generated databases, do not cite them as source_url."
            ]
            user_prompt = "".join(user_prompt_parts)
        
        logger.info(f"[BACKEND] Using strategy={strategy} for query: {text[:50]}...")
        
        # Инициализируем OpenAI client
        openai_client = OpenAI(api_key=settings.openai_api_key)
        
        # Вызываем Responses API
        def _call_responses_api():
            if not hasattr(openai_client, 'responses') or not hasattr(openai_client.responses, 'create'):
                raise AttributeError("Responses API not available")
            
            return openai_client.responses.create(
                model="gpt-4o",
                tools=[{"type": "web_search"}],
                # НЕ форсируем tool_choice - оставляем auto
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            )
        
        try:
            response = await to_thread.run_sync(_call_responses_api)
        except AttributeError as e:
            logger.error(f"[BACKEND] Responses API not available: {e}")
            # Fallback на parse_meal_text
            parsed = await parse_meal_text(text)
            return {
                "description": parsed.get("description") or text,
                "calories": round(parsed.get("calories", 0.0)),
                "protein_g": round(parsed.get("protein_g", 0.0), 1),
                "fat_g": round(parsed.get("fat_g", 0.0), 1),
                "carbs_g": round(parsed.get("carbs_g", 0.0), 1),
                "accuracy_level": "ESTIMATE",
                "source_provider": "LLM_RESTAURANT_ESTIMATE",
                "notes": "Official nutrition not found; estimate. " + (parsed.get("notes", "") or ""),
                "source_url": None,
            }
        except Exception as e:
            logger.error(f"[BACKEND] Error calling Responses API: {e}", exc_info=True)
            # Fallback на parse_meal_text
            parsed = await parse_meal_text(text)
            return {
                "description": parsed.get("description") or text,
                "calories": round(parsed.get("calories", 0.0)),
                "protein_g": round(parsed.get("protein_g", 0.0), 1),
                "fat_g": round(parsed.get("fat_g", 0.0), 1),
                "carbs_g": round(parsed.get("carbs_g", 0.0), 1),
                "accuracy_level": "ESTIMATE",
                "source_provider": "LLM_RESTAURANT_ESTIMATE",
                "notes": "Official nutrition not found; estimate. " + (parsed.get("notes", "") or ""),
                "source_url": None,
            }
        
        # Извлекаем данные из response
        output_items = []
        has_web_search_call = False
        source_url = None
        output_content = None
        web_context_all = ""  # Агрегированный веб-контекст для проверки evidence
        
        # Проверяем response.output
        if hasattr(response, 'output') and response.output:
            if isinstance(response.output, list):
                output_types = [getattr(item, 'type', type(item).__name__) for item in response.output]
                logger.info(f"[BACKEND] Response output types: {output_types}")
                output_items = response.output
            else:
                logger.info(f"[BACKEND] Response output is not a list: {type(response.output)}")
                output_items = [response.output] if response.output else []
            
            # Проверяем наличие web_search_call и извлекаем контент
            for item in output_items:
                item_type = getattr(item, 'type', None)
                if item_type == "web_search_call":
                    has_web_search_call = True
                    logger.info(f"[BACKEND] Found web_search_call in output")
                    # Пытаемся извлечь контент из web_search результатов
                    if hasattr(item, 'results') and item.results:
                        for result in item.results:
                            if hasattr(result, 'content'):
                                web_context_all += str(result.content) + " "
                            elif hasattr(result, 'text'):
                                web_context_all += str(result.text) + " "
                            elif isinstance(result, dict):
                                web_context_all += str(result.get('content', '')) + " "
                                web_context_all += str(result.get('text', '')) + " "
                    break
            
            logger.info(f"[BACKEND] Has web_search_call: {has_web_search_call}")
            
            # Извлекаем content из message items и ищем annotations
            for item in output_items:
                item_type = getattr(item, 'type', None)
                
                # Если это message item, извлекаем content
                if item_type == "message" or hasattr(item, 'content'):
                    content = getattr(item, 'content', None)
                    if content:
                        if isinstance(content, list):
                            for block in content:
                                if hasattr(block, 'text'):
                                    block_text = block.text
                                    if not output_content:
                                        output_content = block_text
                                    web_context_all += block_text + " "
                                elif isinstance(block, str):
                                    if not output_content:
                                        output_content = block
                                    web_context_all += block + " "
                                elif isinstance(block, dict):
                                    block_text = block.get('text', '')
                                    if block_text:
                                        if not output_content:
                                            output_content = block_text
                                        web_context_all += block_text + " "
                        elif isinstance(content, str):
                            output_content = content
                            web_context_all += content + " "
                    
                    # Ищем annotations в message item
                    if hasattr(item, 'annotations'):
                        annotations = item.annotations
                        if annotations:
                            if isinstance(annotations, list):
                                for ann in annotations:
                                    ann_type = getattr(ann, 'type', None)
                                    if ann_type == "url_citation" or hasattr(ann, 'url_citation'):
                                        url_citation = getattr(ann, 'url_citation', None)
                                        if url_citation:
                                            if hasattr(url_citation, 'url'):
                                                source_url = url_citation.url
                                            elif isinstance(url_citation, dict) and 'url' in url_citation:
                                                source_url = url_citation['url']
                                            elif isinstance(url_citation, str):
                                                source_url = url_citation
                                            
                                            if source_url:
                                                logger.info(f"[BACKEND] Extracted source_url from url_citation: {source_url}")
                                                break
                            elif hasattr(annotations, 'url_citation'):
                                url_citation = annotations.url_citation
                                if hasattr(url_citation, 'url'):
                                    source_url = url_citation.url
                                elif isinstance(url_citation, dict) and 'url' in url_citation:
                                    source_url = url_citation['url']
                                
                                if source_url:
                                    logger.info(f"[BACKEND] Extracted source_url from annotations.url_citation: {source_url}")
        
        # Если не нашли content, пробуем альтернативные пути
        if not output_content:
            if hasattr(response, 'content'):
                output_content = response.content
                web_context_all += str(response.content) + " "
            elif hasattr(response, 'text'):
                output_content = response.text
                web_context_all += str(response.text) + " "
        
        if not output_content:
            logger.warning("[BACKEND] No content extracted from response, falling back to parse_meal_text")
            parsed = await parse_meal_text(text)
            return {
                "description": parsed.get("description") or text,
                "calories": round(parsed.get("calories", 0.0)),
                "protein_g": round(parsed.get("protein_g", 0.0), 1),
                "fat_g": round(parsed.get("fat_g", 0.0), 1),
                "carbs_g": round(parsed.get("carbs_g", 0.0), 1),
                "accuracy_level": "ESTIMATE",
                "source_provider": "LLM_RESTAURANT_ESTIMATE",
                "notes": "Official nutrition not found; estimate. " + (parsed.get("notes", "") or ""),
                "source_url": None,
            }
        
        # Парсим JSON из ответа
        json_match = re.search(r'\{.*\}', output_content, re.DOTALL)
        if not json_match:
            logger.warning(f"[BACKEND] Response does not contain JSON: {output_content[:200]}")
            parsed = await parse_meal_text(text)
            return {
                "description": parsed.get("description") or text,
                "calories": round(parsed.get("calories", 0.0)),
                "protein_g": round(parsed.get("protein_g", 0.0), 1),
                "fat_g": round(parsed.get("fat_g", 0.0), 1),
                "carbs_g": round(parsed.get("carbs_g", 0.0), 1),
                "accuracy_level": "ESTIMATE",
                "source_provider": "LLM_RESTAURANT_ESTIMATE",
                "notes": "Official nutrition not found; estimate. " + (parsed.get("notes", "") or ""),
                "source_url": None,
            }
        
        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            logger.warning(f"[BACKEND] Failed to parse JSON: {e}, raw: {output_content[:200]}")
            parsed = await parse_meal_text(text)
            return {
                "description": parsed.get("description") or text,
                "calories": round(parsed.get("calories", 0.0)),
                "protein_g": round(parsed.get("protein_g", 0.0), 1),
                "fat_g": round(parsed.get("fat_g", 0.0), 1),
                "carbs_g": round(parsed.get("carbs_g", 0.0), 1),
                "accuracy_level": "ESTIMATE",
                "source_provider": "LLM_RESTAURANT_ESTIMATE",
                "notes": "Official nutrition not found; estimate. " + (parsed.get("notes", "") or ""),
                "source_url": None,
            }
        
        # Извлекаем данные из JSON
        restaurant = data.get("restaurant")
        dish = data.get("dish", text)
        description = data.get("description", text)
        portion_grams = data.get("portion_grams")
        calories = float(data.get("calories", 0) or 0)
        protein_g = float(data.get("protein_g", 0) or 0)
        fat_g = float(data.get("fat_g", 0) or 0)
        carbs_g = float(data.get("carbs_g", 0) or 0)
        accuracy_level = data.get("accuracy_level", "ESTIMATE")
        notes = data.get("notes", "")
        evidence_snippets = data.get("evidence_snippets", [])
        
        # Извлекаем source_url из JSON (если не был извлечен из citations)
        extracted_source_url_from_json = data.get("source_url")
        if extracted_source_url_from_json and extracted_source_url_from_json != "null" and extracted_source_url_from_json:
            if not source_url:
                source_url = extracted_source_url_from_json
        
        # Логируем извлеченные данные
        logger.info(f"[BACKEND] Parsed data: restaurant={restaurant}, dish={dish}, calories={calories}, "
                   f"source_url={source_url}, evidence_snippets_count={len(evidence_snippets) if evidence_snippets else 0}")
        
        # Валидация: если calories <= 0 или source_url is null -> fallback
        if calories <= 0:
            logger.info(f"[BACKEND] calories={calories} <= 0, falling back to parse_meal_text")
            parsed = await parse_meal_text(text)
            return {
                "description": parsed.get("description") or text,
                "calories": round(parsed.get("calories", 0.0)),
                "protein_g": round(parsed.get("protein_g", 0.0), 1),
                "fat_g": round(parsed.get("fat_g", 0.0), 1),
                "carbs_g": round(parsed.get("carbs_g", 0.0), 1),
                "accuracy_level": "ESTIMATE",
                "source_provider": "LLM_RESTAURANT_ESTIMATE",
                "notes": "Official nutrition not found; estimate. " + (parsed.get("notes", "") or ""),
                "source_url": None,
            }
        
        if not source_url:
            logger.info(f"[BACKEND] source_url is null, falling back to parse_meal_text")
            parsed = await parse_meal_text(text)
            return {
                "description": parsed.get("description") or text,
                "calories": round(parsed.get("calories", 0.0)),
                "protein_g": round(parsed.get("protein_g", 0.0), 1),
                "fat_g": round(parsed.get("fat_g", 0.0), 1),
                "carbs_g": round(parsed.get("carbs_g", 0.0), 1),
                "accuracy_level": "ESTIMATE",
                "source_provider": "LLM_RESTAURANT_ESTIMATE",
                "notes": "Official nutrition not found; estimate. " + (parsed.get("notes", "") or ""),
                "source_url": None,
            }
        
        # Верификация evidence_snippets
        web_context_lower = web_context_all.lower()
        evidence_verified = True
        
        if not evidence_snippets or not isinstance(evidence_snippets, list) or len(evidence_snippets) == 0:
            logger.warning(f"[BACKEND] No evidence_snippets provided")
            evidence_verified = False
        else:
            # Проверяем каждую snippet
            for snippet in evidence_snippets:
                if not snippet or not isinstance(snippet, str) or not snippet.strip():
                    logger.warning(f"[BACKEND] Empty or invalid evidence_snippet: {snippet}")
                    evidence_verified = False
                    break
                
                snippet_lower = snippet.lower().strip()
                # Проверяем, что snippet встречается в web_context (case-insensitive)
                if snippet_lower not in web_context_lower:
                    logger.warning(f"[BACKEND] Evidence snippet not found in web context: {snippet[:50]}...")
                    evidence_verified = False
                    break
        
        logger.info(f"[BACKEND] Evidence verification result: {evidence_verified}")
        
        # Если верификация не прошла -> fallback
        if not evidence_verified:
            logger.info(f"[BACKEND] Evidence verification failed, falling back to parse_meal_text")
            parsed = await parse_meal_text(text)
            return {
                "description": parsed.get("description") or text,
                "calories": round(parsed.get("calories", 0.0)),
                "protein_g": round(parsed.get("protein_g", 0.0), 1),
                "fat_g": round(parsed.get("fat_g", 0.0), 1),
                "carbs_g": round(parsed.get("carbs_g", 0.0), 1),
                "accuracy_level": "ESTIMATE",
                "source_provider": "LLM_RESTAURANT_ESTIMATE",
                "notes": "Official nutrition not found; estimate. " + (parsed.get("notes", "") or ""),
                "source_url": None,
            }
        
        # Валидация accuracy_level
        if accuracy_level not in ["HIGH", "ESTIMATE"]:
            accuracy_level = "ESTIMATE"
        
        # Если верификация прошла - возвращаем результат
        if notes:
            notes = f"Verified by evidence. {notes}"
        else:
            notes = "Verified by evidence."
        
        return {
            "description": description,
            "calories": round(calories),
            "protein_g": round(protein_g, 1),
            "fat_g": round(fat_g, 1),
            "carbs_g": round(carbs_g, 1),
            "accuracy_level": accuracy_level,
            "source_provider": "OPENAI_WEB_SEARCH",
            "notes": notes,
            "source_url": source_url,
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BACKEND] Unexpected error in restaurant_parse_text_openai: {e}", exc_info=True)
        # Fallback на parse_meal_text даже при неожиданной ошибке
        try:
            parsed = await parse_meal_text(text)
            return {
                "description": parsed.get("description") or text,
                "calories": round(parsed.get("calories", 0.0)),
                "protein_g": round(parsed.get("protein_g", 0.0), 1),
                "fat_g": round(parsed.get("fat_g", 0.0), 1),
                "carbs_g": round(parsed.get("carbs_g", 0.0), 1),
                "accuracy_level": "ESTIMATE",
                "source_provider": "LLM_RESTAURANT_ESTIMATE",
                "notes": "Official nutrition not found; estimate. " + (parsed.get("notes", "") or ""),
                "source_url": None,
            }
        except Exception as fallback_error:
            logger.error(f"[BACKEND] Fallback parse_meal_text also failed: {fallback_error}", exc_info=True)
            raise HTTPException(status_code=500, detail="Ошибка при обработке запроса")


# ---------- AGENT ----------


@app.post("/ai/agent", response_model=AgentResponse)
async def ai_agent(payload: AgentRequest, db: Session = Depends(get_db)):
    """
    Agentic mode endpoint using OpenAI Responses API with tools.
    Understands user intent and can log meals, show summaries, etc.
    """
    try:
        result = await run_agent(
            db=db,
            user_id=payload.user_id,
            text=payload.text,
            date_str=payload.date,
            conversation_context=payload.conversation_context,
        )
        return result
    except Exception as e:
        logger.error(f"[BACKEND] Error in agent endpoint: {e}", exc_info=True)
        return {
            "intent": "error",
            "reply_text": f"Произошла ошибка: {str(e)}",
            "meal": None,
            "day_summary": None,
            "week_summary": None,
        }


# ---------- WORKFLOW (Telegram Bridge) ----------


@app.post("/agent/run", response_model=WorkflowRunResponse)
async def agent_run(payload: WorkflowRunRequest):
    """
    Run the YumYummy Agent Builder workflow.
    Returns the final JSON with intent, message_text, confidence, totals, items, source_url.
    Also persists meal entries to database for log_meal/product/eatout/barcode intents.
    
    Note: Workflow runs WITHOUT DB connection to avoid stale connections during long operations.
    Persist uses a fresh DB session after workflow completes, with retry on OperationalError.
    """
    request_id = str(uuid.uuid4())[:8]
    telegram_id = payload.telegram_id
    user_text = payload.text
    
    try:
        # Run the workflow WITHOUT DB connection
        result = await run_yumyummy_workflow(user_text=user_text, telegram_id=telegram_id)
        
        # Extract values for logging
        intent = result.get("intent", "unknown")
        confidence = result.get("confidence")
        source_url = result.get("source_url")
        has_source_url = source_url is not None and source_url != ""
        
        # Log the request
        logger.info(
            f"[WORKFLOW] request_id={request_id} telegram_id={telegram_id} "
            f"intent={intent} confidence={confidence} source_url_present={has_source_url}"
        )
        
        # Persist to database (if applicable) using a FRESH session
        # Retry once if OperationalError occurs (connection closed)
        try:
            db2 = SessionLocal()
            try:
                persist_agent_result(db=db2, telegram_id=telegram_id, agent_result=result)
            finally:
                db2.close()
        except OperationalError as op_error:
            # Retry once with a fresh session
            logger.warning(
                f"[WORKFLOW] request_id={request_id} telegram_id={telegram_id} "
                f"OperationalError during persist: {op_error}, retrying once with new session"
            )
            db3 = SessionLocal()
            try:
                persist_agent_result(db=db3, telegram_id=telegram_id, agent_result=result)
            finally:
                db3.close()
        except Exception as persist_error:
            # Don't fail the request if persistence fails, just log it
            logger.error(
                f"[WORKFLOW] request_id={request_id} telegram_id={telegram_id} "
                f"Failed to persist result: {persist_error}",
                exc_info=True
            )
        
        # Ensure the response matches the expected schema
        # Convert to WorkflowRunResponse model (will validate)
        try:
            # Log result structure for debugging
            logger.debug(
                f"[WORKFLOW] request_id={request_id} telegram_id={telegram_id} "
                f"result keys: {list(result.keys())}, "
                f"intent={result.get('intent')}, "
                f"has_totals={'totals' in result}, "
                f"has_items={'items' in result}"
            )
            
            # Validate and convert to WorkflowRunResponse
            response = WorkflowRunResponse(**result)
            return response
        except Exception as validation_error:
            # Log validation error with full details
            logger.error(
                f"[WORKFLOW] request_id={request_id} telegram_id={telegram_id} "
                f"Validation error: {validation_error}, "
                f"result structure: {result}",
                exc_info=True
            )
            # Return friendly error response instead of crashing
            return WorkflowRunResponse(
                intent="help",
                message_text="Произошла ошибка при обработке ответа. Попробуйте позже.",
                confidence=None,
                totals=WorkflowTotals(
                    calories_kcal=0.0,
                    protein_g=0.0,
                    fat_g=0.0,
                    carbs_g=0.0,
                ),
                items=[],
                source_url=None,
            )
        
    except WorkflowNotInstalledError as e:
        error_msg = str(e)
        # Check if it's an OPENAI_API_KEY error
        if "OPENAI_API_KEY" in error_msg:
            logger.error(f"[WORKFLOW] request_id={request_id} telegram_id={telegram_id} {error_msg}")
            return WorkflowRunResponse(
                intent="help",
                message_text="Сервис временно не настроен (нет ключа OpenAI). Сообщите администратору.",
                confidence=None,
                totals=WorkflowTotals(
                    calories_kcal=0.0,
                    protein_g=0.0,
                    fat_g=0.0,
                    carbs_g=0.0,
                ),
                items=[],
                source_url=None,
            )
        else:
            logger.warning(f"[WORKFLOW] request_id={request_id} telegram_id={telegram_id} workflow not installed: {e}")
            # Return friendly JSON saying workflow is not connected
            return WorkflowRunResponse(
                intent="help",
                message_text="Сервис временно не подключен. Попробуйте позже.",
                confidence=None,
                totals=WorkflowTotals(
                    calories_kcal=0.0,
                    protein_g=0.0,
                    fat_g=0.0,
                    carbs_g=0.0,
                ),
                items=[],
                source_url=None,
            )
    
    except (RateLimitError, APIConnectionError, APIError) as e:
        logger.error(
            f"[WORKFLOW] request_id={request_id} telegram_id={telegram_id} "
            f"OpenAI API error: {e}",
            exc_info=True
        )
        # Return friendly JSON for quota/rate-limit errors
        return WorkflowRunResponse(
            intent="help",
            message_text="Сервис перегружен или лимит исчерпан. Попробуй чуть позже.",
            confidence=None,
            totals=WorkflowTotals(
                calories_kcal=0.0,
                protein_g=0.0,
                fat_g=0.0,
                carbs_g=0.0,
            ),
            items=[],
            source_url=None,
        )
    
    except Exception as e:
        logger.error(
            f"[WORKFLOW] request_id={request_id} telegram_id={telegram_id} "
            f"unexpected error: {e}",
            exc_info=True
        )
        # Return friendly JSON for any other error (never crash)
        return WorkflowRunResponse(
            intent="help",
            message_text="Произошла ошибка при обработке запроса. Попробуйте позже.",
            confidence=None,
            totals=WorkflowTotals(
                calories_kcal=0.0,
                protein_g=0.0,
                fat_g=0.0,
                carbs_g=0.0,
            ),
            items=[],
            source_url=None,
        )


# ---------- USERS ----------


@app.post("/users", response_model=UserRead)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Создать пользователя по telegram_id.
    Если такой уже есть — возвращаем его (идемпотентно).
    """
    existing = db.query(User).filter(User.telegram_id == user_in.telegram_id).first()
    if existing:
        return existing

    user = User(telegram_id=user_in.telegram_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/users/{telegram_id}", response_model=UserRead)
def get_user_by_telegram_id(telegram_id: str, db: Session = Depends(get_db)):
    """
    Получить пользователя по telegram_id.
    """
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.patch("/users/{telegram_id}", response_model=UserRead)
def update_user_profile(telegram_id: str, user_update: UserUpdate, db: Session = Depends(get_db)):
    """
    Обновить профиль пользователя (онбординг, цели КБЖУ и т.д.)
    """
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Обновляем только переданные поля
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    return user


@app.get("/users/{telegram_id}/export")
def export_user_meals(telegram_id: str, db: Session = Depends(get_db)):
    """
    Экспорт всех приёмов пищи пользователя в CSV формате.
    """
    from fastapi.responses import StreamingResponse
    import csv
    import io
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Получаем все приёмы пищи
    meals = (
        db.query(MealEntry)
        .filter(MealEntry.user_id == user.id)
        .order_by(MealEntry.eaten_at.desc())
        .all()
    )
    
    # Создаём CSV в памяти
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Заголовок
    writer.writerow([
        "date", "time", "description", "calories", 
        "protein_g", "fat_g", "carbs_g", "accuracy", "source"
    ])
    
    # Данные
    for meal in meals:
        writer.writerow([
            meal.eaten_at.strftime("%Y-%m-%d"),
            meal.eaten_at.strftime("%H:%M"),
            meal.description_user,
            meal.calories,
            meal.protein_g,
            meal.fat_g,
            meal.carbs_g,
            meal.accuracy_level or "UNKNOWN",
            meal.uc_type or "UNKNOWN"
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=yumyummy_export_{telegram_id}.csv"
        }
    )


# ---------- MEALS ----------


@app.post("/meals", response_model=MealRead)
def create_meal(meal_in: MealCreate, db: Session = Depends(get_db)):
    """
    Залогировать приём пищи:
    - user_id — id пользователя
    - date — за какой день логируем
    - description_user — описание еды (что съел)
    - calories / protein_g / fat_g / carbs_g — КБЖУ (ручной ввод)
    """
    user = db.query(User).filter(User.id == meal_in.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Находим или создаём UserDay для этого дня
    user_day = (
        db.query(UserDay)
        .filter(UserDay.user_id == user.id, UserDay.date == meal_in.date)
        .first()
    )

    if not user_day:
        user_day = UserDay(
            user_id=user.id,
            date=meal_in.date,
            total_calories=0,
            total_protein_g=0,
            total_fat_g=0,
            total_carbs_g=0,
        )
        db.add(user_day)
        db.flush()  # чтобы у user_day появился id до коммита

    # Определяем accuracy_level: если передан - используем, иначе по умолчанию
    accuracy = meal_in.accuracy_level or "EXACT"
    # Нормализуем: EXACT / ESTIMATE / APPROX
    accuracy_upper = accuracy.upper()
    if accuracy_upper == "HIGH":
        # Если пришло HIGH из web-search, маппим на ESTIMATE
        accuracy = "ESTIMATE"
    elif accuracy_upper not in ("EXACT", "ESTIMATE", "APPROX"):
        accuracy = "ESTIMATE"
    
    meal = MealEntry(
        user_id=user.id,
        user_day_id=user_day.id,
        description_user=meal_in.description_user,
        calories=meal_in.calories,
        protein_g=meal_in.protein_g,
        fat_g=meal_in.fat_g,
        carbs_g=meal_in.carbs_g,
        uc_type="UC1",          # пока считаем, что это ручной ввод
        accuracy_level=accuracy,
    )

    # Обновляем агрегаты по дню
    user_day.total_calories += meal_in.calories
    user_day.total_protein_g += meal_in.protein_g
    user_day.total_fat_g += meal_in.fat_g
    user_day.total_carbs_g += meal_in.carbs_g

    db.add(meal)
    db.commit()
    db.refresh(meal)

    return meal


@app.patch("/meals/{meal_id}", response_model=MealRead)
def update_meal(
    meal_id: int,
    meal_in: MealUpdate,
    db: Session = Depends(get_db),
):
    meal = db.query(MealEntry).filter(MealEntry.id == meal_id).first()
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    user_day = db.query(UserDay).filter(UserDay.id == meal.user_day_id).first()
    if not user_day:
        raise HTTPException(status_code=404, detail="User day not found")

    old_calories = meal.calories
    old_protein = meal.protein_g
    old_fat = meal.fat_g
    old_carbs = meal.carbs_g

    new_calories = old_calories if meal_in.calories is None else meal_in.calories
    new_protein = old_protein if meal_in.protein_g is None else meal_in.protein_g
    new_fat = old_fat if meal_in.fat_g is None else meal_in.fat_g
    new_carbs = old_carbs if meal_in.carbs_g is None else meal_in.carbs_g

    if meal_in.description_user is not None:
        meal.description_user = meal_in.description_user

    if meal_in.eaten_at is not None:
        meal.eaten_at = meal_in.eaten_at

    meal.calories = new_calories
    meal.protein_g = new_protein
    meal.fat_g = new_fat
    meal.carbs_g = new_carbs

    user_day.total_calories += new_calories - old_calories
    user_day.total_protein_g += new_protein - old_protein
    user_day.total_fat_g += new_fat - old_fat
    user_day.total_carbs_g += new_carbs - old_carbs

    db.commit()
    db.refresh(meal)

    return meal


@app.delete("/meals/{meal_id}")
def delete_meal(meal_id: int, db: Session = Depends(get_db)):
    meal = db.query(MealEntry).filter(MealEntry.id == meal_id).first()
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    user_day = db.query(UserDay).filter(UserDay.id == meal.user_day_id).first()
    if not user_day:
        raise HTTPException(status_code=404, detail="User day not found")

    user_day.total_calories -= meal.calories
    user_day.total_protein_g -= meal.protein_g
    user_day.total_fat_g -= meal.fat_g
    user_day.total_carbs_g -= meal.carbs_g

    db.delete(meal)
    db.commit()

    return {"status": "deleted"}


# ---------- DAY SUMMARY ----------


@app.get("/day/{user_id}/{day}", response_model=DaySummary)
def get_day_summary(
    user_id: int,
    day: date_type,
    db: Session = Depends(get_db),
):
    """
    Сводка по дню:
    - общие КБЖУ
    - список приёмов пищи
    """
    user_day = (
        db.query(UserDay)
            .filter(UserDay.user_id == user_id, UserDay.date == day)
            .first()
    )
    if not user_day:
        raise HTTPException(status_code=404, detail="No data for this day")

    meals = (
        db.query(MealEntry)
            .filter(MealEntry.user_day_id == user_day.id)
            .order_by(MealEntry.eaten_at.asc())
            .all()
    )

    return DaySummary(
        user_id=user_id,
        date=day,
        total_calories=user_day.total_calories,
        total_protein_g=user_day.total_protein_g,
        total_fat_g=user_day.total_fat_g,
        total_carbs_g=user_day.total_carbs_g,
        meals=meals,
    )
