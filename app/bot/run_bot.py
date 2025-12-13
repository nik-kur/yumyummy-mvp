import asyncio
from datetime import date as date_type, timedelta

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import CommandStart, Command

from app.core.config import settings
from app.bot.api_client import (
    ping_backend,
    ensure_user,
    create_meal,
    get_day_summary,
    ai_parse_meal,
    product_parse_meal_by_barcode,
    product_parse_meal_by_name,
)


router = Router()


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
        "/today - показать сводку за сегодня\n"
        "/week - показать сводку за последние 7 дней\n"
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
        summary_text = (
            "\n\nСводка за сегодня:\n"
            f"• Калории: {summary['total_calories']}\n"
            f"• Белки: {summary['total_protein_g']} г\n"
            f"• Жиры: {summary['total_fat_g']} г\n"
            f"• Углеводы: {summary['total_carbs_g']} г"
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

    # 2) Просим backend найти продукт по штрихкоду
    parsed = await product_parse_meal_by_barcode(barcode)
    if parsed is None:
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
        summary_text = (
            "\n\nСводка за сегодня:\n"
            f"• Калории: {summary['total_calories']}\n"
            f"• Белки: {summary['total_protein_g']} г\n"
            f"• Жиры: {summary['total_fat_g']} г\n"
            f"• Углеводы: {summary['total_carbs_g']} г"
        )

    await message.answer(base_text + macros_text + summary_text)


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

    # 2) Просим backend найти продукт по названию
    parsed = await product_parse_meal_by_name(name, brand=brand, store=store)
    if parsed is None:
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
        summary_text = (
            "\n\nСводка за сегодня:\n"
            f"• Калории: {summary['total_calories']}\n"
            f"• Белки: {summary['total_protein_g']} г\n"
            f"• Жиры: {summary['total_fat_g']} г\n"
            f"• Углеводы: {summary['total_carbs_g']} г"
        )

    await message.answer(base_text + macros_text + summary_text)


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

    # 2) Просим backend/LLM оценить КБЖУ
    parsed = await ai_parse_meal(raw_text)
    if parsed is None:
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
        text_lines.append("")
        text_lines.append("Сводка за сегодня:")
        text_lines.append(f"• Калории: {summary['total_calories']}")
        text_lines.append(f"• Белки: {summary['total_protein_g']} г")
        text_lines.append(f"• Жиры: {summary['total_fat_g']} г")
        text_lines.append(f"• Углеводы: {summary['total_carbs_g']} г")

    await message.answer("\n".join(text_lines))

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

    text_lines = [
        f"📅 Сводка за сегодня ({date_str}):",
        f"• Калории: {summary['total_calories']}",
        f"• Белки: {summary['total_protein_g']} г",
        f"• Жиры: {summary['total_fat_g']} г",
        f"• Углеводы: {summary['total_carbs_g']} г",
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

        total_calories += summary["total_calories"]
        total_protein_g += summary["total_protein_g"]
        total_fat_g += summary["total_fat_g"]
        total_carbs_g += summary["total_carbs_g"]

        days_with_data.append((day, summary))

    if not days_with_data:
        await message.answer("За эту неделю записей пока нет 🌱")
        return

    start_str = start_date.strftime("%d.%m.%Y")
    end_str = today.strftime("%d.%m.%Y")

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
            f"{d_str}: {summary['total_calories']} ккал, "
            f"Б {summary['total_protein_g']} / "
            f"Ж {summary['total_fat_g']} / "
            f"У {summary['total_carbs_g']}"
        )

    await message.answer("\n".join(text_lines))


async def main() -> None:
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
