import logging
from datetime import date as date_type

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)
from app.deps import get_db
from app.models.user import User
from app.models.user_day import UserDay
from app.models.meal_entry import MealEntry
from app.schemas.user import UserCreate, UserRead
from app.schemas.meal import MealCreate, MealRead, DaySummary

from app.services.llm_client import chat_completion
from app.services.meal_parser import parse_meal_text
from app.services.nutrition_lookup import NutritionQuery, nutrition_lookup
from app.services.web_nutrition import estimate_nutrition_with_web
from app.services.web_restaurant import estimate_restaurant_meal_with_web
from app.schemas.ai import ParseMealRequest, MealParsed, ProductMealRequest, RestaurantMealRequest
from app.ai.stt_client import transcribe_audio

app = FastAPI(title="YumYummy API")


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
    
    # 2) Fallback на LLM
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
