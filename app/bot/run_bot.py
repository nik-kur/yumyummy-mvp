import asyncio
import logging
from datetime import date as date_type, timedelta
from typing import Dict, Optional

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from app.core.config import settings

logger = logging.getLogger(__name__)
from app.bot.api_client import (
    ping_backend,
    ensure_user,
    create_meal,
    get_day_summary,
    ai_parse_meal,
    product_parse_meal_by_barcode,
    product_parse_meal_by_name,
    voice_parse_meal,
    restaurant_parse_meal,
    restaurant_parse_text,
    restaurant_parse_text_openai,
    agent_query,
    agent_run_workflow,
)


router = Router()

# FSM States for agent clarification
class AgentClarification(StatesGroup):
    waiting_for_clarification = State()


@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    """
    Обработка /start:
    - регистрируем пользователя в backend (POST /users)
    - показываем приветствие
    """
    tg_id = message.from_user.id

    user = await ensure_user(tg_id)

    if user is None:
        await message.answer(
            "Привет! Я YumYummy 🧃\n\n"
            "Похоже, сейчас не могу связаться с сервером.\n"
            "Попробуй, пожалуйста, чуть позже 🙏"
        )
        return

    text = (
        "Привет! Я YumYummy 🧃\n\n"
        "Я помогу тебе логировать питание и считать КБЖУ.\n"
        "Пока я на стадии MVP, но уже умею:\n"
        "• создавать твою учётку в системе (/start)\n"
        "• проверять связь с сервером (/ping)\n\n"
        f"Твой внутренний id в системе: {user['id']}"
    )
    await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    text = (
        "Доступные команды:\n"
        "/start - приветствие и регистрация в системе\n"
        "/help - помощь\n"
        "/ping - проверить связь с сервером YumYummy\n"
        "/log - вручную записать приём пищи (калории и, опционально, КБЖУ)\n"
        "/ai_log - описать, что ты съел, а я сам оценю КБЖУ с помощью AI\n"
        "/barcode - записать продукт по штрихкоду\n"
        "/product - записать продукт по названию (можно указать бренд/магазин)\n"
        "/eatout - записать блюдо из ресторана (пример: /eatout сырники из кофемании)\n"
        "/eatoutA - экспериментальная версия через OpenAI (пример: /eatoutA сырники из кофемании)\n"
        "/today - показать сводку за сегодня\n"
        "/week - показать сводку за последние 7 дней\n\n"
        "Можно отправить голосовое сообщение — я распознаю и запишу."
    )
    await message.answer(text)



@router.message(Command("ping"))
async def cmd_ping(message: types.Message) -> None:
    """
    Проверяем связь с backend'ом через /health.
    """
    health = await ping_backend()
    if health is None:
        await message.answer("❌ Не удалось связаться с сервером YumYummy.")
        return

    status = health.get("status", "unknown")
    app_name = health.get("app", "unknown")

    await message.answer(
        f"✅ Связь с backend'ом есть.\n"
        f"status: {status}\n"
        f"app: {app_name}"
    )

@router.message(Command("log"))
async def cmd_log(message: types.Message) -> None:
    """
    Логируем приём пищи.

    Форматы:
    /log 350 овсянка с бананом
    /log 350 25 10 40 овсянка с бананом
      └─ калории белки жиры углеводы описание...
    """
    if not message.text:
        await message.answer("Не понял сообщение. Пример: /log 350 овсянка с бананом")
        return

    # Отделяем команду от аргументов
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Нужно передать параметры.\n\n"
            "Примеры:\n"
            "/log 350 овсянка с бананом\n"
            "/log 350 25 10 40 овсянка с бананом"
        )
        return

    args_str = parts[1]
    tokens = args_str.split()

    if not tokens:
        await message.answer(
            "Не удалось разобрать параметры.\n"
            "Пример: /log 350 25 10 40 овсянка с бананом"
        )
        return

    # Парсим калории
    try:
        calories = float(tokens[0])
    except ValueError:
        await message.answer(
            "Первая цифра после /log должна быть калориями.\n"
            "Пример: /log 350 овсянка с бананом"
        )
        return

    # Пробуем последующие токены интерпретировать как белки, жиры, углеводы
    protein_g = 0.0
    fat_g = 0.0
    carbs_g = 0.0

    idx = 1

    def parse_float_token(i: int) -> tuple[float, int]:
        if i < len(tokens):
            try:
                value = float(tokens[i])
                return value, i + 1
            except ValueError:
                return 0.0, i
        return 0.0, i

    # Белки
    protein_g, idx = parse_float_token(idx)
    # Жиры
    fat_g, idx = parse_float_token(idx)
    # Углеводы
    carbs_g, idx = parse_float_token(idx)
    
    # Округляем значения для отображения
    calories = round(calories)
    protein_g = round(protein_g, 1)
    fat_g = round(fat_g, 1)
    carbs_g = round(carbs_g, 1)

    # Всё, что осталось — описание
    description = " ".join(tokens[idx:]).strip()
    if not description:
        description = "Без описания"

    # Гарантируем, что пользователь есть в backend
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Не удалось связаться с backend'ом. Попробуй позже 🙏")
        return

    user_id = user["id"]
    today = date_type.today()

    meal = await create_meal(
        user_id=user_id,
        day=today,
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
    )

    if meal is None:
        await message.answer("Не получилось записать приём пищи. Попробуй позже 🙏")
        return

    # Пробуем ещё и сводку за день вытащить
    summary = await get_day_summary(user_id=user_id, day=today)

    base_text = (
        "✅ Записал приём пищи:\n"
        f"• {description}\n"
        f"• Калории: {calories}"
    )

    macros_text = ""
    if protein_g or fat_g or carbs_g:
        macros_text = (
            f"\n• Белки: {protein_g} г"
            f"\n• Жиры: {fat_g} г"
            f"\n• Углеводы: {carbs_g} г"
        )

    summary_text = ""
    if summary:
        # Округляем значения сводки
        total_calories = round(summary.get('total_calories', 0))
        total_protein = round(summary.get('total_protein_g', 0), 1)
        total_fat = round(summary.get('total_fat_g', 0), 1)
        total_carbs = round(summary.get('total_carbs_g', 0), 1)
        
        summary_text = (
            "\n\nСводка за сегодня:\n"
            f"• Калории: {total_calories}\n"
            f"• Белки: {total_protein} г\n"
            f"• Жиры: {total_fat} г\n"
            f"• Углеводы: {total_carbs} г"
        )

    await message.answer(base_text + macros_text + summary_text)


@router.message(Command("barcode"))
async def cmd_barcode(message: types.Message) -> None:
    """
    Логируем приём пищи по штрихкоду продукта.

    Формат:
    /barcode 4607025392147

    Бот:
    - ищет продукт в OpenFoodFacts по штрихкоду,
    - создаёт MealEntry в backend,
    - показывает оценку + сводку за день.
    """
    if not message.text:
        await message.answer(
            "Не понял сообщение. Пример использования:\n"
            "/barcode 4607025392147"
        )
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Нужно добавить штрихкод после команды.\n\n"
            "Пример:\n"
            "/barcode 4607025392147"
        )
        return

    barcode = parts[1].strip()
    if not barcode:
        await message.answer(
            "Штрихкод пустой. Пример:\n"
            "/barcode 4607025392147"
        )
        return

    # 1) Гарантируем, что пользователь есть в backend
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Не удалось связаться с backend'ом. Попробуй позже 🙏")
        return

    user_id = user["id"]

    # Отправляем немедленный ответ, что запрос получен
    processing_msg = await message.answer("⏳ Обрабатываю запрос, это может занять несколько секунд...")

    # 2) Просим backend найти продукт по штрихкоду
    parsed = await product_parse_meal_by_barcode(barcode)
    if parsed is None:
        # Удаляем сообщение "Обрабатываю..." перед отправкой ошибки
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(
            "Не удалось связаться с backend'ом. Попробуй позже 🙏"
        )
        return

    description = parsed.get("description", "Продукт")
    calories = float(parsed.get("calories") or 0)
    protein_g = float(parsed.get("protein_g") or 0)
    fat_g = float(parsed.get("fat_g") or 0)
    carbs_g = float(parsed.get("carbs_g") or 0)
    accuracy_level = parsed.get("accuracy_level", "ESTIMATE")
    notes = parsed.get("notes", "")
    source_url = parsed.get("source_url")

    # Округляем значения для отображения
    calories = round(calories)
    protein_g = round(protein_g, 1)
    fat_g = round(fat_g, 1)
    carbs_g = round(carbs_g, 1)

    # 3) Записываем это как MealEntry на сегодня
    today = date_type.today()

    meal = await create_meal(
        user_id=user_id,
        day=today,
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
    )

    if meal is None:
        await message.answer("Не получилось записать приём пищи. Попробуй позже 🙏")
        return

    # 4) Получаем сводку за день
    summary = await get_day_summary(user_id=user_id, day=today)

    # 5) Формируем ответ пользователю
    base_text = f"✅ Записал приём пищи:\n• {description}\n"
    macros_text = (
        f"\nОценка КБЖУ:\n"
        f"• Калории: {calories}\n"
        f"• Белки: {protein_g} г\n"
        f"• Жиры: {fat_g} г\n"
        f"• Углеводы: {carbs_g} г\n"
        f"Точность: {accuracy_level}"
    )

    if notes:
        macros_text += f"\nПримечание: {notes}"

    summary_text = ""
    if summary:
        # Округляем значения сводки
        total_calories = round(summary.get('total_calories', 0))
        total_protein = round(summary.get('total_protein_g', 0), 1)
        total_fat = round(summary.get('total_fat_g', 0), 1)
        total_carbs = round(summary.get('total_carbs_g', 0), 1)
        
        summary_text = (
            "\n\nСводка за сегодня:\n"
            f"• Калории: {total_calories}\n"
            f"• Белки: {total_protein} г\n"
            f"• Жиры: {total_fat} г\n"
            f"• Углеводы: {total_carbs} г"
        )

    # Формируем финальный текст
    text = base_text + macros_text + summary_text
    
    # Добавляем ссылку на источник в текст и кнопку, если есть
    logger.info(f"[BOT] Checking source_url: {source_url}, type: {type(source_url)}")
    if source_url and str(source_url).strip():
        logger.info(f"[BOT] source_url is not empty, checking if valid URL...")
        # Проверяем, что это валидный URL
        if not (source_url.startswith("http://") or source_url.startswith("https://")):
            # Если URL без протокола, добавляем https://
            if source_url.startswith("www."):
                source_url = "https://" + source_url
            elif not source_url.startswith("http"):
                source_url = "https://" + source_url
        
        logger.info(f"[BOT] Final source_url: {source_url}")
        
        # Добавляем кнопку для удобства (ссылка только в кнопке, не в тексте)
        try:
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="🔗 Источник",
                            url=source_url
                        )
                    ]
                ]
            )
            logger.info(f"[BOT] Sending message with keyboard")
            # Удаляем сообщение "Обрабатываю..." и отправляем результат
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.answer(text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"[BOT] Error creating keyboard: {e}")
            # Если ошибка с кнопкой, отправляем хотя бы текст
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.answer(text)
    else:
        logger.info(f"[BOT] No source_url, sending message without link")
        # Удаляем сообщение "Обрабатываю..." и отправляем результат
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(text)


@router.message(Command("product"))
async def cmd_product(message: types.Message) -> None:
    """
    Логируем приём пищи по названию продукта (можно указать бренд/магазин).

    Формат:
    /product творог Простоквашино 5%
    /product творог бренд: Простоквашино магазин: Пятёрочка

    Бот:
    - ищет продукт в OpenFoodFacts по названию,
    - создаёт MealEntry в backend,
    - показывает оценку + сводку за день.
    """
    if not message.text:
        await message.answer(
            "Не понял сообщение. Пример использования:\n"
            "/product творог Простоквашино 5%"
        )
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Нужно добавить название после команды.\n\n"
            "Пример:\n"
            "/product творог Простоквашино 5%"
        )
        return

    text = parts[1].strip()
    if not text:
        await message.answer(
            "Название пустое. Пример:\n"
            "/product творог Простоквашино 5%"
        )
        return

    # Парсим название, бренд и магазин
    name = text
    brand = None
    store = None

    # Простой парсер: ищем "бренд:" и "магазин:"
    if "бренд:" in text.lower():
        parts_brand = text.lower().split("бренд:")
        if len(parts_brand) == 2:
            name = parts_brand[0].strip()
            rest = parts_brand[1].strip()
            if "магазин:" in rest.lower():
                parts_store = rest.split("магазин:")
                brand = parts_store[0].strip()
                store = parts_store[1].strip() if len(parts_store) > 1 else None
            else:
                brand = rest
    elif "магазин:" in text.lower():
        parts_store = text.lower().split("магазин:")
        if len(parts_store) == 2:
            name = parts_store[0].strip()
            store = parts_store[1].strip()

    # 1) Гарантируем, что пользователь есть в backend
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Не удалось связаться с backend'ом. Попробуй позже 🙏")
        return

    user_id = user["id"]

    # Отправляем немедленный ответ, что запрос получен
    processing_msg = await message.answer("⏳ Обрабатываю запрос, это может занять несколько секунд...")

    # 2) Просим backend найти продукт по названию
    parsed = await product_parse_meal_by_name(name, brand=brand, store=store)
    if parsed is None:
        # Удаляем сообщение "Обрабатываю..." перед отправкой ошибки
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(
            "Не удалось связаться с backend'ом. Попробуй позже 🙏"
        )
        return

    description = parsed.get("description", "Продукт")
    calories = float(parsed.get("calories") or 0)
    protein_g = float(parsed.get("protein_g") or 0)
    fat_g = float(parsed.get("fat_g") or 0)
    carbs_g = float(parsed.get("carbs_g") or 0)
    accuracy_level = parsed.get("accuracy_level", "ESTIMATE")
    notes = parsed.get("notes", "")
    source_url = parsed.get("source_url")

    # Округляем значения для отображения
    calories = round(calories)
    protein_g = round(protein_g, 1)
    fat_g = round(fat_g, 1)
    carbs_g = round(carbs_g, 1)

    # 3) Записываем это как MealEntry на сегодня
    today = date_type.today()

    meal = await create_meal(
        user_id=user_id,
        day=today,
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
    )

    if meal is None:
        await message.answer("Не получилось записать приём пищи. Попробуй позже 🙏")
        return

    # 4) Получаем сводку за день
    summary = await get_day_summary(user_id=user_id, day=today)

    # 5) Формируем ответ пользователю
    base_text = f"✅ Записал приём пищи:\n• {description}\n"
    macros_text = (
        f"\nОценка КБЖУ:\n"
        f"• Калории: {calories}\n"
        f"• Белки: {protein_g} г\n"
        f"• Жиры: {fat_g} г\n"
        f"• Углеводы: {carbs_g} г\n"
        f"Точность: {accuracy_level}"
    )

    if notes:
        macros_text += f"\nПримечание: {notes}"

    summary_text = ""
    if summary:
        # Округляем значения сводки
        total_calories = round(summary.get('total_calories', 0))
        total_protein = round(summary.get('total_protein_g', 0), 1)
        total_fat = round(summary.get('total_fat_g', 0), 1)
        total_carbs = round(summary.get('total_carbs_g', 0), 1)
        
        summary_text = (
            "\n\nСводка за сегодня:\n"
            f"• Калории: {total_calories}\n"
            f"• Белки: {total_protein} г\n"
            f"• Жиры: {total_fat} г\n"
            f"• Углеводы: {total_carbs} г"
        )

    # Формируем финальный текст
    text = base_text + macros_text + summary_text
    
    # Добавляем ссылку на источник в текст и кнопку, если есть
    logger.info(f"[BOT] Checking source_url: {source_url}, type: {type(source_url)}")
    if source_url and str(source_url).strip():
        logger.info(f"[BOT] source_url is not empty, checking if valid URL...")
        # Проверяем, что это валидный URL
        if not (source_url.startswith("http://") or source_url.startswith("https://")):
            # Если URL без протокола, добавляем https://
            if source_url.startswith("www."):
                source_url = "https://" + source_url
            elif not source_url.startswith("http"):
                source_url = "https://" + source_url
        
        logger.info(f"[BOT] Final source_url: {source_url}")
        
        # Добавляем кнопку для удобства (ссылка только в кнопке, не в тексте)
        try:
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="🔗 Источник",
                            url=source_url
                        )
                    ]
                ]
            )
            logger.info(f"[BOT] Sending message with keyboard")
            # Удаляем сообщение "Обрабатываю..." и отправляем результат
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.answer(text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"[BOT] Error creating keyboard: {e}")
            # Если ошибка с кнопкой, отправляем хотя бы текст
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.answer(text)
    else:
        logger.info(f"[BOT] No source_url, sending message without link")
        # Удаляем сообщение "Обрабатываю..." и отправляем результат
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(text)


@router.message(Command("ai_log"))
async def cmd_ai_log(message: types.Message) -> None:
    """
    Логируем приём пищи с помощью AI.

    Формат:
    /ai_log съел тарелку борща, два кусочка чёрного хлеба и чай без сахара

    Бот:
    - отправляет текст в /ai/parse_meal (LLM оценивает КБЖУ),
    - создаёт MealEntry в backend,
    - показывает оценку + сводку за день.
    """
    if not message.text:
        await message.answer(
            "Не понял сообщение. Пример использования:\n"
            "/ai_log съел тарелку борща, два кусочка чёрного хлеба и чай без сахара"
        )
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Нужно добавить описание после команды.\n\n"
            "Пример:\n"
            "/ai_log съел тарелку борща, два кусочка чёрного хлеба и чай без сахара"
        )
        return

    raw_text = parts[1].strip()
    if not raw_text:
        await message.answer(
            "Описание пустое. Пример:\n"
            "/ai_log съел тарелку борща, два кусочка чёрного хлеба и чай без сахара"
        )
        return

    # 1) Гарантируем, что пользователь есть в backend
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Не удалось связаться с backend'ом. Попробуй позже 🙏")
        return

    user_id = user["id"]

    # Отправляем немедленный ответ, что запрос получен
    processing_msg = await message.answer("⏳ Обрабатываю запрос, это может занять несколько секунд...")

    # 2) Просим backend/LLM оценить КБЖУ
    parsed = await ai_parse_meal(raw_text)
    if parsed is None:
        # Удаляем сообщение "Обрабатываю..." перед отправкой ошибки
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(
            "Не получилось получить оценку КБЖУ от AI. Попробуй чуть позже 🙏"
        )
        return

    description = parsed.get("description", "").strip() or "Описание не указано"
    calories = float(parsed.get("calories", 0) or 0)
    protein_g = float(parsed.get("protein_g", 0) or 0)
    fat_g = float(parsed.get("fat_g", 0) or 0)
    carbs_g = float(parsed.get("carbs_g", 0) or 0)
    accuracy_level = str(parsed.get("accuracy_level", "ESTIMATE")).upper()
    notes = parsed.get("notes", "")
    source_url = parsed.get("source_url")
    
    # Логируем для отладки
    logger.info(f"[BOT /ai_log] source_url received: {source_url}, type: {type(source_url)}")

    # Округляем значения для отображения
    calories = round(calories)
    protein_g = round(protein_g, 1)
    fat_g = round(fat_g, 1)
    carbs_g = round(carbs_g, 1)

    # 3) Записываем это как MealEntry на сегодня
    today = date_type.today()

    meal = await create_meal(
        user_id=user_id,
        day=today,
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
    )

    if meal is None:
        await message.answer("Не получилось записать приём пищи. Попробуй позже 🙏")
        return

    # 4) Получаем сводку за день
    summary = await get_day_summary(user_id=user_id, day=today)

    # 5) Формируем ответ пользователю
    text_lines = [
        "✅ Записал приём пищи (оценка с помощью AI):",
        f"• {description}",
        f"• Калории: {calories}",
        f"• Белки: {protein_g} г",
        f"• Жиры: {fat_g} г",
        f"• Углеводы: {carbs_g} г",
        "",
        f"Уровень точности: {accuracy_level}",
    ]

    if notes:
        text_lines.append(f"Примечание: {notes}")

    if summary:
        # Округляем значения сводки
        total_calories = round(summary.get('total_calories', 0))
        total_protein = round(summary.get('total_protein_g', 0), 1)
        total_fat = round(summary.get('total_fat_g', 0), 1)
        total_carbs = round(summary.get('total_carbs_g', 0), 1)
        
        text_lines.append("")
        text_lines.append("Сводка за сегодня:")
        text_lines.append(f"• Калории: {total_calories}")
        text_lines.append(f"• Белки: {total_protein} г")
        text_lines.append(f"• Жиры: {total_fat} г")
        text_lines.append(f"• Углеводы: {total_carbs} г")

    # Формируем финальный текст
    text = "\n".join(text_lines)
    
    # Добавляем ссылку на источник в текст и кнопку, если есть
    logger.info(f"[BOT] Checking source_url: {source_url}, type: {type(source_url)}")
    if source_url and str(source_url).strip():
        logger.info(f"[BOT] source_url is not empty, checking if valid URL...")
        # Проверяем, что это валидный URL
        if not (source_url.startswith("http://") or source_url.startswith("https://")):
            # Если URL без протокола, добавляем https://
            if source_url.startswith("www."):
                source_url = "https://" + source_url
            elif not source_url.startswith("http"):
                source_url = "https://" + source_url
        
        logger.info(f"[BOT] Final source_url: {source_url}")
        
        # Добавляем кнопку для удобства (ссылка только в кнопке, не в тексте)
        try:
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="🔗 Источник",
                            url=source_url
                        )
                    ]
                ]
            )
            logger.info(f"[BOT] Sending message with keyboard")
            # Удаляем сообщение "Обрабатываю..." и отправляем результат
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.answer(text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"[BOT] Error creating keyboard: {e}")
            # Если ошибка с кнопкой, отправляем хотя бы текст
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.answer(text)
    else:
        logger.info(f"[BOT] No source_url, sending message without link")
        # Удаляем сообщение "Обрабатываю..." и отправляем результат
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(text)


@router.message(Command("eatout"))
async def cmd_eatout(message: types.Message) -> None:
    """
    Обработка /eatout <свободный текст>
    Записывает блюдо из ресторана/кафе/доставки.
    Примеры: /eatout сырники из кофемании, /eatout паста карбонара в vapiano
    """
    # Парсим команду: /eatout <свободный текст>
    text = message.text or ""
    parts = text.split(maxsplit=1)
    
    if len(parts) < 2:
        await message.answer(
            "Использование: /eatout <описание блюда>\n"
            "Примеры:\n"
            "• /eatout сырники из кофемании\n"
            "• /eatout паста карбонара в vapiano"
        )
        return
    
    raw_text = parts[1].strip()
    
    if not raw_text:
        await message.answer(
            "Укажи описание блюда:\n"
            "Пример: /eatout сырники из кофемании"
        )
        return
    
    # 1) Гарантируем, что пользователь есть в backend
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Не удалось связаться с backend'ом. Попробуй позже 🙏")
        return
    
    user_id = user["id"]
    
    # Отправляем немедленный ответ, что запрос получен
    processing_msg = await message.answer("⏳ Обрабатываю запрос, это может занять несколько секунд...")
    
    # 2) Просим backend найти блюдо из ресторана по свободному тексту
    parsed = await restaurant_parse_text(text=raw_text)
    if parsed is None:
        # Удаляем сообщение "Обрабатываю..." перед отправкой ошибки
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(
            "Не удалось связаться с backend'ом. Попробуй позже 🙏"
        )
        return
    
    description = parsed.get("description", "") or raw_text
    calories = float(parsed.get("calories", 0) or 0)
    protein_g = float(parsed.get("protein_g", 0) or 0)
    fat_g = float(parsed.get("fat_g", 0) or 0)
    carbs_g = float(parsed.get("carbs_g", 0) or 0)
    accuracy_level = parsed.get("accuracy_level", "ESTIMATE")
    notes = parsed.get("notes", "")
    source_provider = parsed.get("source_provider", "LLM_RESTAURANT_ESTIMATE")
    source_url = parsed.get("source_url")
    
    # Округляем значения для отображения
    calories = round(calories)
    protein_g = round(protein_g, 1)
    fat_g = round(fat_g, 1)
    carbs_g = round(carbs_g, 1)
    
    # 3) Записываем это как MealEntry на сегодня
    today = date_type.today()
    meal = await create_meal(
        user_id=user_id,
        day=today,
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        accuracy_level=accuracy_level,
    )
    
    if meal is None:
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer("Не получилось записать приём пищи. Попробуй позже 🙏")
        return
    
    # 4) Получаем сводку за день
    summary = await get_day_summary(user_id=user_id, day=today)
    
    # 5) Формируем ответ пользователю
    base_text = f"✅ Записал: {description}"
    macros_text = (
        f"\n\nКБЖУ:\n"
        f"• Калории: {calories}\n"
        f"• Белки: {protein_g} г\n"
        f"• Жиры: {fat_g} г\n"
        f"• Углеводы: {carbs_g} г\n"
        f"Точность: {accuracy_level}"
    )
    
    if notes:
        macros_text += f"\nПримечание: {notes}"
    
    summary_text = ""
    if summary:
        # Округляем значения сводки
        total_calories = round(summary.get('total_calories', 0))
        total_protein = round(summary.get('total_protein_g', 0), 1)
        total_fat = round(summary.get('total_fat_g', 0), 1)
        total_carbs = round(summary.get('total_carbs_g', 0), 1)
        
        summary_text = (
            "\n\nСводка за сегодня:\n"
            f"• Калории: {total_calories}\n"
            f"• Белки: {total_protein} г\n"
            f"• Жиры: {total_fat} г\n"
            f"• Углеводы: {total_carbs} г"
        )
    
    # Формируем финальный текст
    text = base_text + macros_text + summary_text
    
    # Добавляем ссылку на источник в кнопку, если есть
    logger.info(f"[BOT] Checking source_url: {source_url}, type: {type(source_url)}")
    if source_url and str(source_url).strip():
        logger.info(f"[BOT] source_url is not empty, checking if valid URL...")
        # Проверяем, что это валидный URL
        if not (source_url.startswith("http://") or source_url.startswith("https://")):
            # Если URL без протокола, добавляем https://
            if source_url.startswith("www."):
                source_url = "https://" + source_url
            elif not source_url.startswith("http"):
                source_url = "https://" + source_url
        
        logger.info(f"[BOT] Final source_url: {source_url}")
        
        # Добавляем кнопку для удобства (ссылка только в кнопке, не в тексте)
        try:
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="🔗 Источник",
                            url=source_url
                        )
                    ]
                ]
            )
            logger.info(f"[BOT] Sending message with keyboard")
            # Удаляем сообщение "Обрабатываю..." и отправляем результат
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.answer(text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"[BOT] Error creating keyboard: {e}")
            # Если ошибка с кнопкой, отправляем хотя бы текст
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.answer(text)
    else:
        logger.info(f"[BOT] No source_url, sending message without link")
        # Удаляем сообщение "Обрабатываю..." и отправляем результат
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(text)


@router.message(Command("eatoutA"))
async def cmd_eatout_a(message: types.Message) -> None:
    """
    EXPERIMENTAL: Обработка /eatoutA <свободный текст>
    Записывает блюдо из ресторана/кафе/доставки через OpenAI Responses API с web_search (Path A).
    Примеры: /eatoutA сырники из кофемании, /eatoutA паста карбонара в vapiano
    """
    # Парсим команду: /eatoutA <свободный текст>
    text = message.text or ""
    parts = text.split(maxsplit=1)
    
    if len(parts) < 2:
        await message.answer(
            "Использование: /eatoutA <описание блюда>\n"
            "Примеры:\n"
            "• /eatoutA сырники из кофемании\n"
            "• /eatoutA паста карбонара в vapiano\n\n"
            "⚠️ Это экспериментальная версия через OpenAI web search"
        )
        return
    
    raw_text = parts[1].strip()
    
    if not raw_text:
        await message.answer(
            "Укажи описание блюда:\n"
            "Пример: /eatoutA сырники из кофемании"
        )
        return
    
    # 1) Гарантируем, что пользователь есть в backend
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Не удалось связаться с backend'ом. Попробуй позже 🙏")
        return
    
    user_id = user["id"]
    
    # Отправляем немедленный ответ, что запрос получен
    processing_msg = await message.answer("⏳ Обрабатываю запрос через OpenAI web search, это может занять несколько секунд...")
    
    # 2) Просим backend найти блюдо из ресторана через OpenAI web search
    parsed = await restaurant_parse_text_openai(text=raw_text)
    if parsed is None:
        # Удаляем сообщение "Обрабатываю..." перед отправкой ошибки
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(
            "Не удалось связаться с backend'ом. Попробуй позже 🙏"
        )
        return
    
    description = parsed.get("description", "") or raw_text
    calories = float(parsed.get("calories", 0) or 0)
    protein_g = float(parsed.get("protein_g", 0) or 0)
    fat_g = float(parsed.get("fat_g", 0) or 0)
    carbs_g = float(parsed.get("carbs_g", 0) or 0)
    accuracy_level = parsed.get("accuracy_level", "ESTIMATE")
    notes = parsed.get("notes", "")
    source_provider = parsed.get("source_provider", "OPENAI_WEB_SEARCH")
    source_url = parsed.get("source_url")
    
    # Округляем значения для отображения
    calories = round(calories)
    protein_g = round(protein_g, 1)
    fat_g = round(fat_g, 1)
    carbs_g = round(carbs_g, 1)
    
    # 3) Записываем это как MealEntry на сегодня
    today = date_type.today()
    meal = await create_meal(
        user_id=user_id,
        day=today,
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        accuracy_level=accuracy_level,
        source_provider=source_provider,
    )
    
    if meal is None:
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer("Не получилось записать приём пищи. Попробуй позже 🙏")
        return
    
    # 4) Получаем сводку за день
    summary = await get_day_summary(user_id=user_id, day=today)
    
    # 5) Формируем ответ пользователю
    base_text = f"✅ Записал: {description}"
    macros_text = (
        f"\n\nКБЖУ:\n"
        f"• Калории: {calories}\n"
        f"• Белки: {protein_g} г\n"
        f"• Жиры: {fat_g} г\n"
        f"• Углеводы: {carbs_g} г"
    )
    
    if accuracy_level:
        macros_text += f"\n\nТочность: {accuracy_level}"
    
    if notes:
        macros_text += f"\n\nПримечание: {notes}"
    
    summary_text = ""
    if summary:
        # Округляем значения сводки
        total_calories = round(summary.get('total_calories', 0))
        total_protein = round(summary.get('total_protein_g', 0), 1)
        total_fat = round(summary.get('total_fat_g', 0), 1)
        total_carbs = round(summary.get('total_carbs_g', 0), 1)
        summary_text = (
            "\n\nСводка за сегодня:\n"
            f"• Калории: {total_calories}\n"
            f"• Белки: {total_protein} г\n"
            f"• Жиры: {total_fat} г\n"
            f"• Углеводы: {total_carbs} г"
        )
    
    # Формируем финальный текст
    text = base_text + macros_text + summary_text
    
    # Добавляем ссылку на источник в текст и кнопку, если есть
    logger.info(f"[BOT /eatoutA] Checking source_url: {source_url}, type: {type(source_url)}")
    if source_url and str(source_url).strip():
        logger.info(f"[BOT /eatoutA] source_url is not empty, checking if valid URL...")
        # Проверяем, что это валидный URL
        if not (source_url.startswith("http://") or source_url.startswith("https://")):
            # Если URL без протокола, добавляем https://
            if source_url.startswith("www."):
                source_url = "https://" + source_url
            elif not source_url.startswith("http"):
                source_url = "https://" + source_url
        
        logger.info(f"[BOT /eatoutA] Final source_url: {source_url}")
        
        # Добавляем кнопку для удобства (ссылка только в кнопке, не в тексте)
        try:
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="🔗 Источник",
                            url=source_url
                        )
                    ]
                ]
            )
            logger.info(f"[BOT /eatoutA] Sending message with keyboard")
            # Удаляем сообщение "Обрабатываю..." и отправляем результат
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.answer(text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"[BOT /eatoutA] Error creating keyboard: {e}")
            # Если ошибка с кнопкой, отправляем хотя бы текст
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.answer(text)
    else:
        logger.info(f"[BOT /eatoutA] No source_url, sending message without link")
        # Удаляем сообщение "Обрабатываю..." и отправляем результат
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(text)


@router.message(Command("today"))
async def cmd_today(message: types.Message) -> None:
    """
    Сводка за сегодня.
    """
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Не удалось связаться с backend'ом. Попробуй позже 🙏")
        return

    user_id = user["id"]
    today = date_type.today()

    summary = await get_day_summary(user_id=user_id, day=today)
    if summary is None:
        await message.answer("За сегодня пока нет записей 🥗")
        return

    date_str = today.strftime("%d.%m.%Y")

    # Округляем значения
    total_calories = round(summary.get('total_calories', 0))
    total_protein = round(summary.get('total_protein_g', 0), 1)
    total_fat = round(summary.get('total_fat_g', 0), 1)
    total_carbs = round(summary.get('total_carbs_g', 0), 1)
    
    text_lines = [
        f"📅 Сводка за сегодня ({date_str}):",
        f"• Калории: {total_calories}",
        f"• Белки: {total_protein} г",
        f"• Жиры: {total_fat} г",
        f"• Углеводы: {total_carbs} г",
    ]

    await message.answer("\n".join(text_lines))

@router.message(Command("week"))
async def cmd_week(message: types.Message) -> None:
    """
    Сводка за последние 7 дней (включая сегодня).
    """
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Не удалось связаться с backend'ом. Попробуй позже 🙏")
        return

    user_id = user["id"]
    today = date_type.today()
    start_date = today - timedelta(days=6)

    total_calories = 0.0
    total_protein_g = 0.0
    total_fat_g = 0.0
    total_carbs_g = 0.0

    days_with_data = []

    # Проходим по всем дням недели
    for offset in range(7):
        day = start_date + timedelta(days=offset)
        summary = await get_day_summary(user_id=user_id, day=day)
        if summary is None:
            continue

        # Округляем значения перед суммированием
        total_calories += round(summary.get("total_calories", 0))
        total_protein_g += round(summary.get("total_protein_g", 0), 1)
        total_fat_g += round(summary.get("total_fat_g", 0), 1)
        total_carbs_g += round(summary.get("total_carbs_g", 0), 1)

        days_with_data.append((day, summary))

    if not days_with_data:
        await message.answer("За эту неделю записей пока нет 🌱")
        return

    start_str = start_date.strftime("%d.%m.%Y")
    end_str = today.strftime("%d.%m.%Y")

    # Округляем итоговые значения
    total_calories = round(total_calories)
    total_protein_g = round(total_protein_g, 1)
    total_fat_g = round(total_fat_g, 1)
    total_carbs_g = round(total_carbs_g, 1)
    
    text_lines = [
        f"📊 Сводка за неделю ({start_str} — {end_str}):",
        f"• Калории: {total_calories}",
        f"• Белки: {total_protein_g} г",
        f"• Жиры: {total_fat_g} г",
        f"• Углеводы: {total_carbs_g} г",
        "",
        "По дням:",
    ]

    for day, summary in days_with_data:
        d_str = day.strftime("%d.%m")
        text_lines.append(
            f"{d_str}: {round(summary.get('total_calories', 0))} ккал, "
            f"Б {round(summary.get('total_protein_g', 0), 1)} / "
            f"Ж {round(summary.get('total_fat_g', 0), 1)} / "
            f"У {round(summary.get('total_carbs_g', 0), 1)}"
        )

    await message.answer("\n".join(text_lines))


@router.message(F.voice)
async def handle_voice(message: types.Message) -> None:
    """
    Обработка голосовых сообщений.
    Скачивает voice, отправляет на backend для STT и парсинга, логирует приём пищи.
    """
    # 1) Гарантируем, что пользователь есть в backend
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Не удалось связаться с backend'ом. Попробуй позже 🙏")
        return

    user_id = user["id"]

    # 2) Скачиваем голосовое сообщение
    try:
        file = await message.bot.get_file(message.voice.file_id)
        bio = await message.bot.download_file(file.file_path)
        audio_bytes = bio.read()
    except Exception as e:
        logger.error(f"[VOICE] Error downloading voice: {e}")
        await message.answer("Не удалось скачать голосовое сообщение. Попробуй ещё раз 🙏")
        return

    if not audio_bytes:
        await message.answer("Голосовое сообщение пустое. Попробуй ещё раз 🙏")
        return

    # 3) Отправляем сообщение о начале обработки
    await message.answer("🎙 Секунду, распознаю голос и считаю КБЖУ...")

    # 4) Отправляем на backend для STT и парсинга
    parsed = await voice_parse_meal(audio_bytes)
    if parsed is None:
        await message.answer("Не удалось обработать голос. Попробуй ещё раз 🙏")
        return

    transcript = parsed.get("transcript", "")
    description = parsed.get("description", "") or "Описание не указано"
    calories = float(parsed.get("calories", 0) or 0)
    protein_g = float(parsed.get("protein_g", 0) or 0)
    fat_g = float(parsed.get("fat_g", 0) or 0)
    carbs_g = float(parsed.get("carbs_g", 0) or 0)
    
    # Извлекаем accuracy_level и source_provider из ответа
    raw_accuracy = parsed.get("accuracy_level", "ESTIMATE")
    accuracy_level = str(raw_accuracy or "ESTIMATE").upper()
    source_provider = parsed.get("source_provider") or "LLM_ESTIMATE"
    source_url = parsed.get("source_url")
    
    notes = parsed.get("notes", "") or ""
    
    # Добавляем source_provider в notes, если он есть и отличается от LLM_ESTIMATE
    if source_provider and source_provider != "LLM_ESTIMATE":
        if notes:
            notes = f"[{source_provider}] {notes}"
        else:
            notes = f"[{source_provider}]"

    # Округляем значения для отображения
    calories = round(calories)
    protein_g = round(protein_g, 1)
    fat_g = round(fat_g, 1)
    carbs_g = round(carbs_g, 1)

    # 5) Логируем приём пищи
    today = date_type.today()
    meal = await create_meal(
        user_id=user_id,
        day=today,
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        accuracy_level=accuracy_level,
    )

    if meal is None:
        await message.answer("Не получилось записать приём пищи. Попробуй позже 🙏")
        return

    # 6) Получаем сводку за день
    summary = await get_day_summary(user_id=user_id, day=today)

    # 7) Формируем ответ пользователю
    lines = [
        "✅ Записал приём пищи по голосу.",
    ]
    if transcript.strip():
        lines += ["", f"Распознал: \"{transcript.strip()}\""]
    lines += [
        "",
        f"• {description}",
        f"• Калории: {calories}",
        f"• Белки: {protein_g} г",
        f"• Жиры: {fat_g} г",
        f"• Углеводы: {carbs_g} г",
        "",
        f"Точность: {accuracy_level}",
    ]
    if notes:
        lines += ["", f"Примечание: {notes}"]
    if summary:
        # Округляем значения сводки
        total_calories = round(summary.get('total_calories', 0))
        total_protein = round(summary.get('total_protein_g', 0), 1)
        total_fat = round(summary.get('total_fat_g', 0), 1)
        total_carbs = round(summary.get('total_carbs_g', 0), 1)
        
        lines += [
            "",
            "Сводка за сегодня:",
            f"• Калории: {total_calories}",
            f"• Белки: {total_protein} г",
            f"• Жиры: {total_fat} г",
            f"• Углеводы: {total_carbs} г",
        ]

    # Формируем финальный текст
    text = "\n".join(lines)
    
    # Добавляем ссылку на источник в кнопку, если есть
    logger.info(f"[BOT] Checking source_url: {source_url}, type: {type(source_url)}")
    if source_url and str(source_url).strip():
        logger.info(f"[BOT] source_url is not empty, checking if valid URL...")
        # Проверяем, что это валидный URL
        if not (source_url.startswith("http://") or source_url.startswith("https://")):
            # Если URL без протокола, добавляем https://
            if source_url.startswith("www."):
                source_url = "https://" + source_url
            elif not source_url.startswith("http"):
                source_url = "https://" + source_url
        
        logger.info(f"[BOT] Final source_url: {source_url}")
        
        # Добавляем кнопку для удобства (ссылка только в кнопке, не в тексте)
        try:
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="🔗 Источник",
                            url=source_url
                        )
                    ]
                ]
            )
            logger.info(f"[BOT] Sending message with keyboard")
            await message.answer(text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"[BOT] Error creating keyboard: {e}")
            # Если ошибка с кнопкой, отправляем хотя бы текст
            await message.answer(text)
    else:
        logger.info(f"[BOT] No source_url, sending message without link")
        await message.answer(text)


@router.message(Command("agent"))
async def cmd_agent(message: types.Message) -> None:
    """
    Agent command that uses /agent/run endpoint.
    Takes free text after /agent command.
    """
    tg_id = str(message.from_user.id)
    text = message.text or ""
    
    # Extract text after /agent command
    if text.startswith("/agent"):
        text = text[6:].strip()  # Remove "/agent" prefix
    
    # If no text, show usage hint
    if not text:
        await message.answer("Использование: /agent <ваш запрос>\n\nПример: /agent сырники из кофемании")
        return
    
    # Send processing message
    processing_msg = await message.answer("⏳ Обрабатываю запрос...")
    
    try:
        # Call agent/run endpoint
        logger.info(f"[BOT /agent] Calling agent_run_workflow for telegram_id={tg_id}, text={text[:50]}...")
        result = await agent_run_workflow(telegram_id=tg_id, text=text)
        
        if result is None:
            logger.warning(f"[BOT /agent] agent_run_workflow returned None for telegram_id={tg_id}")
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.answer("Сервис временно недоступен, попробуй позже.")
            return
        
        # Extract result fields
        intent = result.get("intent", "unknown")
        message_text = result.get("message_text", "Ошибка обработки")
        confidence = result.get("confidence")
        source_url = result.get("source_url")
        has_source_url = source_url is not None and source_url != ""
        
        # Log result
        logger.info(
            f"[BOT /agent] telegram_id={tg_id} intent={intent} "
            f"confidence={confidence} source_url_present={has_source_url} "
            f"message_text_length={len(message_text) if message_text else 0}"
        )
        
        # Log full result structure for debugging eatout issues
        if intent == "eatout":
            logger.info(
                f"[BOT /agent] eatout result details: "
                f"totals={result.get('totals')}, "
                f"items_count={len(result.get('items', []))}, "
                f"source_url={source_url}"
            )
        
        # Delete processing message
        try:
            await processing_msg.delete()
        except Exception:
            pass
        
        # Build reply with optional source URL button
        reply_markup = None
        if has_source_url:
            try:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                reply_markup = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="Источник", url=source_url)]]
                )
            except Exception as e:
                logger.error(f"[BOT /agent] Error creating reply_markup: {e}", exc_info=True)
                # Continue without button if there's an error
        
        # Send the message
        try:
            await message.answer(message_text, reply_markup=reply_markup)
            logger.info(f"[BOT /agent] Successfully sent message for telegram_id={tg_id}, intent={intent}")
        except Exception as send_error:
            logger.error(
                f"[BOT /agent] Error sending message: {send_error}, "
                f"message_text_length={len(message_text) if message_text else 0}",
                exc_info=True
            )
            # Try to send a simpler message
            try:
                await message.answer("Получен ответ, но возникла ошибка при отправке. Попробуй ещё раз.")
            except Exception:
                pass
        
    except Exception as e:
        logger.error(f"[BOT /agent] Error: {e}", exc_info=True)
        try:
            await processing_msg.delete()
        except Exception:
            pass
        try:
            await message.answer("Сервис временно недоступен, попробуй позже.")
        except Exception:
            pass


@router.message(AgentClarification.waiting_for_clarification)
async def handle_agent_clarification(message: types.Message, state: FSMContext) -> None:
    """
    Handle user response to agent clarification question.
    For MVP, treat as a regular /agent command.
    """
    logger.info(f"[BOT] Handling clarification response: {message.text}")
    # Clear state and treat as regular command
    await state.clear()
    await cmd_agent(message)


@router.message(F.text)
async def handle_plain_text(message: types.Message) -> None:
    """
    Fallback handler for plain text messages (not commands).
    For MVP, send every plain text message through /agent/run.
    """
    tg_id = str(message.from_user.id)
    text = message.text or ""
    
    # Skip commands (they are handled by specific command handlers)
    if text.startswith("/"):
        return
    
    if not text.strip():
        return  # Skip empty messages
    
    # Send processing message
    processing_msg = await message.answer("⏳ Обрабатываю запрос...")
    
    try:
        # Call agent/run endpoint
        logger.info(f"[BOT plain_text] Calling agent_run_workflow for telegram_id={tg_id}, text={text[:50]}...")
        result = await agent_run_workflow(telegram_id=tg_id, text=text)
        
        if result is None:
            logger.warning(f"[BOT plain_text] agent_run_workflow returned None for telegram_id={tg_id}")
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.answer("Сервис временно недоступен, попробуй позже.")
            return
        
        # Extract result fields
        intent = result.get("intent", "unknown")
        message_text = result.get("message_text", "Ошибка обработки")
        confidence = result.get("confidence")
        source_url = result.get("source_url")
        has_source_url = source_url is not None and source_url != ""
        
        # Log result
        logger.info(
            f"[BOT plain_text] telegram_id={tg_id} intent={intent} "
            f"confidence={confidence} source_url_present={has_source_url} "
            f"message_text_length={len(message_text) if message_text else 0}"
        )
        
        # Log full result structure for debugging eatout issues
        if intent == "eatout":
            logger.info(
                f"[BOT plain_text] eatout result details: "
                f"totals={result.get('totals')}, "
                f"items_count={len(result.get('items', []))}, "
                f"source_url={source_url}"
            )
        
        # Delete processing message
        try:
            await processing_msg.delete()
        except Exception:
            pass
        
        # Build reply with optional source URL button
        reply_markup = None
        if has_source_url:
            try:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                reply_markup = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="Источник", url=source_url)]]
                )
            except Exception as e:
                logger.error(f"[BOT plain_text] Error creating reply_markup: {e}", exc_info=True)
                # Continue without button if there's an error
        
        # Send the message
        try:
            await message.answer(message_text, reply_markup=reply_markup)
            logger.info(f"[BOT plain_text] Successfully sent message for telegram_id={tg_id}, intent={intent}")
        except Exception as send_error:
            logger.error(
                f"[BOT plain_text] Error sending message: {send_error}, "
                f"message_text_length={len(message_text) if message_text else 0}",
                exc_info=True
            )
            # Try to send a simpler message
            try:
                await message.answer("Получен ответ, но возникла ошибка при отправке. Попробуй ещё раз.")
            except Exception:
                pass
        
    except Exception as e:
        logger.error(f"[BOT plain_text] Error: {e}", exc_info=True)
        try:
            await processing_msg.delete()
        except Exception:
            pass
        try:
            await message.answer("Сервис временно недоступен, попробуй позже.")
        except Exception:
            pass


async def main() -> None:
    bot = Bot(token=settings.telegram_bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
