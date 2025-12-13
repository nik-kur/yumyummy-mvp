from datetime import date as date_type

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.deps import get_db
from app.models.user import User
from app.models.user_day import UserDay
from app.models.meal_entry import MealEntry
from app.schemas.user import UserCreate, UserRead
from app.schemas.meal import MealCreate, MealRead, DaySummary

from app.services.llm_client import chat_completion
from app.services.meal_parser import parse_meal_text
from app.services.nutrition_lookup import NutritionQuery, nutrition_lookup
from app.schemas.ai import ParseMealRequest, MealParsed, ProductMealRequest

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


@app.post("/ai/product_parse_meal")
async def ai_product_parse_meal(payload: ProductMealRequest):
    """
    Получить оценку КБЖУ по штрихкоду или названию продукта.
    Сначала пробует OpenFoodFacts, затем fallback на LLM.
    """
    if not payload.barcode and not payload.name:
        raise HTTPException(
            status_code=400,
            detail="Нужно указать либо штрихкод, либо название продукта"
        )
    
    # Пробуем через nutrition_lookup
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
        
        return {
            "description": description,
            "calories": result.calories,
            "protein_g": result.protein_g or 0.0,
            "fat_g": result.fat_g or 0.0,
            "carbs_g": result.carbs_g or 0.0,
            "accuracy_level": result.accuracy_level,
            "source_provider": "OPENFOODFACTS",
            "notes": notes,
        }
    
    # Fallback на LLM
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
        raise HTTPException(status_code=500, detail=str(e))
    
    return {
        "description": parsed.get("description") or fallback_text,
        "calories": parsed.get("calories", 0.0),
        "protein_g": parsed.get("protein_g", 0.0),
        "fat_g": parsed.get("fat_g", 0.0),
        "carbs_g": parsed.get("carbs_g", 0.0),
        "accuracy_level": parsed.get("accuracy_level", "ESTIMATE"),
        "source_provider": "LLM_ESTIMATE",
        "notes": parsed.get("notes", ""),
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

    meal = MealEntry(
        user_id=user.id,
        user_day_id=user_day.id,
        description_user=meal_in.description_user,
        calories=meal_in.calories,
        protein_g=meal_in.protein_g,
        fat_g=meal_in.fat_g,
        carbs_g=meal_in.carbs_g,
        uc_type="UC1",          # пока считаем, что это ручной ввод
        accuracy_level="EXACT",  # вручную заданные КБЖУ
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
