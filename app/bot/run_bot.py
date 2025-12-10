import asyncio
from datetime import date as date_type

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import CommandStart, Command

from app.core.config import settings
from app.bot.api_client import (
    ping_backend,
    ensure_user,
    create_meal,
    get_day_summary,
    ai_parse_meal,
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

async def main() -> None:
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

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
