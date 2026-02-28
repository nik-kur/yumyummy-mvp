import asyncio
import base64
import json
import logging
from datetime import date as date_type, datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

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
    get_user,
    create_meal,
    get_day_summary,
    update_meal,
    delete_meal,
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
from app.bot.onboarding import router as onboarding_router, start_onboarding, get_main_menu_keyboard, FoodAdviceState


router = Router()

MEAL_LOGGING_INTENTS = {"log_meal", "product", "eatout", "barcode", "photo_meal", "nutrition_label"}

# FSM States for agent clarification
class AgentClarification(StatesGroup):
    waiting_for_clarification = State()


class MealEditState(StatesGroup):
    waiting_for_choice = State()
    waiting_for_name = State()
    waiting_for_macros = State()
    waiting_for_time = State()



def normalize_source_url(source_url: Optional[str]) -> Optional[str]:
    if source_url and str(source_url).strip():
        url = str(source_url).strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            if url.startswith("www."):
                url = "https://" + url
            elif not url.startswith("http"):
                url = "https://" + url
        return url
    return None


def format_accuracy_label(accuracy_level: Optional[str]) -> Optional[str]:
    if not accuracy_level:
        return None
    return str(accuracy_level).upper()


def format_source_label(source_url: Optional[str]) -> str:
    normalized = normalize_source_url(source_url)
    if not normalized:
        return "оценка ИИ на базе средних известных значений для указанных блюд и продуктов"
    try:
        domain = urlparse(normalized).netloc
    except ValueError:
        domain = ""
    return domain or normalized


def build_summary_lines(summary: Dict[str, Any]) -> list[str]:
    total_calories = round(summary.get("total_calories", 0))
    total_protein = round(summary.get("total_protein_g", 0), 1)
    total_fat = round(summary.get("total_fat_g", 0), 1)
    total_carbs = round(summary.get("total_carbs_g", 0), 1)
    return [
        "Сводка за сегодня:",
        f"• Калории: {total_calories}",
        f"• Белки: {total_protein} г",
        f"• Жиры: {total_fat} г",
        f"• Углеводы: {total_carbs} г",
    ]


def build_meal_response_text(
    *,
    description: str,
    calories: float,
    protein_g: float,
    fat_g: float,
    carbs_g: float,
    accuracy_level: Optional[str] = None,
    notes: Optional[str] = None,
    source_url: Optional[str] = None,
    summary: Optional[Dict[str, Any]] = None,
) -> str:
    source_label = format_source_label(source_url)
    all_zero = calories == 0 and protein_g == 0 and fat_g == 0 and carbs_g == 0
    lines = [
        f"✅ Записал {description}",
        "",
    ]
    if all_zero:
        lines.append("ℹ️ КБЖУ не удалось определить")
    else:
        lines.append(f"{calories} ккал · Б {protein_g} г · Ж {fat_g} г · У {carbs_g} г")
    if notes:
        lines.append("")
        lines.append(f"Примечание: {notes}")
    lines.append("")
    normalized_url = normalize_source_url(source_url)
    if normalized_url:
        lines.append(f"🔗 Источник: {source_label}")
    else:
        lines.append(f"💡 Источник: {source_label}")
    if summary:
        lines.append("")
        lines.extend(build_summary_lines(summary))
    return "\n".join(lines)


def build_meal_response_from_agent(
    result: Dict[str, Any],
    *,
    summary: Optional[Dict[str, Any]] = None,
) -> str:
    totals = result.get("totals") or {}
    calories = round(float(totals.get("calories_kcal") or 0))
    protein_g = round(float(totals.get("protein_g") or 0), 1)
    fat_g = round(float(totals.get("fat_g") or 0), 1)
    carbs_g = round(float(totals.get("carbs_g") or 0), 1)
    items = result.get("items") or []
    description_parts = [
        item.get("name") for item in items if isinstance(item, dict) and item.get("name")
    ]
    description = ", ".join(description_parts).strip()
    message_text = (result.get("message_text") or "").strip()
    if not description:
        description = message_text or "Без описания"

    if (
        not description_parts
        and calories == 0
        and protein_g == 0
        and fat_g == 0
        and carbs_g == 0
        and message_text
    ):
        return message_text

    # Derive top-level accuracy/source from items when available
    valid_items = [it for it in items if isinstance(it, dict)]
    items_with_source = [it for it in valid_items if it.get("source_url")]
    if valid_items and len(items_with_source) == len(valid_items):
        # All items have sources -> overall accuracy is HIGH
        derived_accuracy = "HIGH"
        # For single item, use its source; for multiple, use top-level or first item's
        derived_source = result.get("source_url") or items_with_source[0].get("source_url")
    elif items_with_source:
        # Some items have sources -> mixed
        derived_accuracy = result.get("confidence") or "ESTIMATE"
        derived_source = result.get("source_url")
    else:
        derived_accuracy = result.get("confidence")
        derived_source = result.get("source_url")

    base_text = build_meal_response_text(
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        accuracy_level=derived_accuracy,
        source_url=derived_source,
        summary=summary,
    )
    if len(valid_items) <= 1:
        return base_text

    lines = [base_text, "", "———", "", "По блюдам:", ""]
    for item in valid_items:
        item_name = item.get("name") or "Блюдо"
        item_calories = round(float(item.get("calories_kcal") or 0))
        item_protein = round(float(item.get("protein_g") or 0), 1)
        item_fat = round(float(item.get("fat_g") or 0), 1)
        item_carbs = round(float(item.get("carbs_g") or 0), 1)
        item_all_zero = item_calories == 0 and item_protein == 0 and item_fat == 0 and item_carbs == 0
        item_source_url = item.get("source_url")
        item_source_label = format_source_label(item_source_url) if item_source_url else format_source_label(None)
        item_source_line = f"🔗 Источник: {item_source_label}" if normalize_source_url(item_source_url) else f"💡 Источник: {item_source_label}"
        if item_all_zero:
            lines.extend([
                f"📝 {item_name}:",
                "ℹ️ КБЖУ не удалось определить",
                item_source_line,
                "",
            ])
        else:
            lines.extend([
                f"📝 {item_name}:",
                f"{item_calories} ккал · Б {item_protein} г · Ж {item_fat} г · У {item_carbs} г",
                item_source_line,
                "",
            ])
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _strip_markdown_bold(text: str) -> str:
    """Remove **bold** markers that Telegram plain-text mode can't render."""
    return text.replace("**", "")


def _extract_message_text_block(message_text: str, start_keywords: list, stop_keywords: list) -> Optional[str]:
    """Extract a block from message_text starting at one of start_keywords and ending before stop_keywords."""
    text_lower = message_text.lower()
    start_pos = None
    for kw in start_keywords:
        idx = text_lower.find(kw.lower())
        if idx != -1:
            start_pos = idx
            break
    if start_pos is None:
        return None

    end_pos = len(message_text)
    for kw in stop_keywords:
        idx = text_lower.find(kw.lower(), start_pos + 1)
        if idx != -1 and idx < end_pos:
            end_pos = idx

    return message_text[start_pos:end_pos].strip()


def build_food_advice_response(result: Dict[str, Any]) -> str:
    """Format food advice as a recommendation (NOT a logged meal)."""
    items = result.get("items") or []
    message_text = _strip_markdown_bold((result.get("message_text") or "").strip())

    if not items:
        return message_text or "Не удалось сформировать рекомендацию."

    lines = ["🤔 Рекомендация:", ""]

    labels = ["Лучший выбор", "Альтернатива 1", "Альтернатива 2"]
    for idx, item in enumerate(items[:3]):
        item_name = _strip_markdown_bold(item.get("name") or "Блюдо")
        item_cal = round(float(item.get("calories_kcal") or 0))
        item_prot = round(float(item.get("protein_g") or 0), 1)
        item_fat = round(float(item.get("fat_g") or 0), 1)
        item_carbs = round(float(item.get("carbs_g") or 0), 1)
        label = labels[idx] if idx < len(labels) else f"Вариант {idx + 1}"
        lines.append(f"{idx + 1}. {label}: {item_name}")
        if item_cal > 0:
            lines.append(f"   {item_cal} ккал · Б {item_prot} г · Ж {item_fat} г · У {item_carbs} г")
        lines.append("")

    if message_text:
        reasoning = _extract_message_text_block(
            message_text,
            ["Почему эти варианты"],
            ["Как улучшить", "Хак", "Совет", "Лайфхак"],
        )
        if reasoning:
            lines.append("💬 " + reasoning)
            lines.append("")

        tip = _extract_message_text_block(
            message_text,
            ["Как улучшить", "Хак", "Совет", "Лайфхак"],
            [],
        )
        if tip:
            lines.append("💡 " + tip)
            lines.append("")

    lines.append("Нажми кнопку ниже, чтобы записать выбранный вариант")

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def build_food_advice_keyboard(items: list, source_url: Optional[str] = None) -> types.InlineKeyboardMarkup:
    """Build keyboard with 'Log variant N' buttons and optional source links for food advice."""
    rows = []
    labels = ["✅ Записать вариант 1", "✅ Записать вариант 2", "✅ Записать вариант 3"]
    for idx in range(min(len(items), 3)):
        item_name = items[idx].get("name", "Блюдо") if isinstance(items[idx], dict) else "Блюдо"
        short_name = item_name if len(item_name) <= 20 else item_name[:17] + "..."
        rows.append([types.InlineKeyboardButton(
            text=f"{labels[idx]} ({short_name})",
            callback_data=f"advice_log:{idx}",
        )])

    source_buttons = []
    for item in items[:3]:
        if isinstance(item, dict) and normalize_source_url(item.get("source_url")):
            item_name = item.get("name") or "Блюдо"
            label = item_name if len(item_name) <= 30 else item_name[:27] + "..."
            source_buttons.append([types.InlineKeyboardButton(
                text=f"🔗 Источник: {label}",
                url=normalize_source_url(item["source_url"]),
            )])
    if not source_buttons and normalize_source_url(source_url):
        source_buttons.append([types.InlineKeyboardButton(
            text="🔗 Источник",
            url=normalize_source_url(source_url),
        )])
    rows.extend(source_buttons)

    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def build_meal_keyboard(
    meal_id: int,
    day: date_type,
    source_url: Optional[str] = None,
    items: Optional[list] = None,
) -> types.InlineKeyboardMarkup:
    rows = [
        [
            types.InlineKeyboardButton(
                text="✏️ Редактировать",
                callback_data=f"meal_edit:{meal_id}:{day.isoformat()}",
            ),
            types.InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=f"meal_delete:{meal_id}:{day.isoformat()}",
            ),
        ]
    ]

    # Per-item source buttons
    if items:
        for item in items:
            if not isinstance(item, dict):
                continue
            item_url = normalize_source_url(item.get("source_url"))
            if item_url:
                item_name = item.get("name") or "Продукт"
                # Truncate long names for button text
                label = item_name if len(item_name) <= 30 else item_name[:27] + "..."
                rows.append([types.InlineKeyboardButton(text=f"🔗 Источник: {label}", url=item_url)])

    # Fallback: single top-level source button if no per-item sources were added
    if len(rows) == 1:
        url = normalize_source_url(source_url)
        if url:
            rows.append([types.InlineKeyboardButton(text="🔗 Источник", url=url)])

    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def build_day_actions_keyboard(day: date_type) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="🍽 Посмотреть приёмы пищи",
                    callback_data=f"daylist:{day.isoformat()}",
                )
            ]
        ]
    )


def build_week_days_keyboard(days: list[date_type]) -> types.InlineKeyboardMarkup:
    rows = []
    for day in days:
        label = day.strftime("%d.%m")
        rows.append(
            [
                types.InlineKeyboardButton(
                    text=label,
                    callback_data=f"daylist:{day.isoformat()}",
                )
            ]
        )
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def build_edit_choice_keyboard(meal_id: int, day: date_type) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="Название",
                    callback_data=f"meal_edit_field:name:{meal_id}:{day.isoformat()}",
                ),
                types.InlineKeyboardButton(
                    text="КБЖУ",
                    callback_data=f"meal_edit_field:macros:{meal_id}:{day.isoformat()}",
                ),
                types.InlineKeyboardButton(
                    text="🕐 Время",
                    callback_data=f"meal_edit_field:time:{meal_id}:{day.isoformat()}",
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="Отмена",
                    callback_data=f"meal_edit_field:cancel:{meal_id}:{day.isoformat()}",
                )
            ],
        ]
    )


async def get_latest_meal_id_for_today(telegram_id: int) -> Optional[int]:
    user = await ensure_user(telegram_id)
    if user is None:
        return None

    summary = await get_day_summary(user_id=user["id"], day=date_type.today())
    if not summary:
        return None

    meals = summary.get("meals", [])
    if not meals:
        return None

    latest_meal = meals[-1]
    return latest_meal.get("id")


def build_day_summary_text(summary: Dict[str, Any], day: date_type) -> str:
    date_str = day.strftime("%d.%m.%Y")
    total_calories = round(summary.get("total_calories", 0))
    total_protein = round(summary.get("total_protein_g", 0), 1)
    total_fat = round(summary.get("total_fat_g", 0), 1)
    total_carbs = round(summary.get("total_carbs_g", 0), 1)
    return "\n".join(
        [
            f"📅 Сводка за день ({date_str}):",
            f"• Калории: {total_calories}",
            f"• Белки: {total_protein} г",
            f"• Жиры: {total_fat} г",
            f"• Углеводы: {total_carbs} г",
        ]
    )


def format_meal_entry(meal: Dict[str, Any]) -> str:
    description = meal.get("description_user") or "Без описания"
    calories = round(meal.get("calories", 0))
    protein_g = round(meal.get("protein_g", 0), 1)
    fat_g = round(meal.get("fat_g", 0), 1)
    carbs_g = round(meal.get("carbs_g", 0), 1)

    time_str = "??:??"
    eaten_at = meal.get("eaten_at")
    if eaten_at:
        try:
            cleaned = eaten_at.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
            time_str = dt.strftime("%H:%M")
        except ValueError:
            pass

    lines = [
        f"🍽 {time_str} — {description}",
        f"• Калории: {calories}",
    ]
    if protein_g or fat_g or carbs_g:
        lines.extend(
            [
                f"• Белки: {protein_g} г",
                f"• Жиры: {fat_g} г",
                f"• Углеводы: {carbs_g} г",
            ]
        )
    return "\n".join(lines)


def parse_macros_input(text: str) -> Optional[Tuple[float, float, float, float]]:
    cleaned = text.strip()
    if not cleaned:
        return None

    for delimiter in ["/", ","]:
        cleaned = cleaned.replace(delimiter, " ")

    parts = [p for p in cleaned.split() if p]
    if len(parts) != 4:
        return None

    try:
        calories = float(parts[0])
        protein = float(parts[1])
        fat = float(parts[2])
        carbs = float(parts[3])
    except ValueError:
        return None

    return calories, protein, fat, carbs


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    """
    Обработка /start:
    - регистрируем пользователя в backend (POST /users)
    - проверяем, прошёл ли пользователь онбординг
    - если нет — запускаем онбординг
    - если да — показываем приветствие с меню
    """
    tg_id = message.from_user.id

    user = await ensure_user(tg_id)

    if user is None:
        await message.answer(
            "Привет! Я YumYummy 🧃\n\n"
            "Похоже, сейчас не могу связаться с сервером.\n"
            "Попробуй, пожалуйста, чуть позже 🙏",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    # Проверяем, прошёл ли пользователь онбординг
    if not user.get("onboarding_completed", False):
        # Запускаем онбординг
        await start_onboarding(message, state)
        return
    
    # Пользователь уже прошёл онбординг — показываем приветствие с меню
    target_cal = user.get('target_calories') or 2000
    target_prot = user.get('target_protein_g') or 150
    target_fat = user.get('target_fat_g') or 65
    target_carbs = user.get('target_carbs_g') or 200
    
    text = (
        f"С возвращением! 👋\n\n"
        f"Твои цели на день:\n"
        f"• 🔥 {target_cal:.0f} ккал\n"
        f"• 🥩 {target_prot:.0f} г белка\n"
        f"• 🥑 {target_fat:.0f} г жиров\n"
        f"• 🍞 {target_carbs:.0f} г углеводов\n\n"
        f"Напиши или надиктуй, что ты съел, и я всё запишу!"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    text = (
        "📝 Как пользоваться ботом:\n\n"
        "1️⃣ Логирование еды:\n"
        "• Просто напиши что съел: \"2 яйца и тост\"\n"
        "• Или отправь голосовое сообщение\n"
        "• 📸 Отправь фото еды — бот оценит КБЖУ\n"
        "• 📸 Сфотографируй этикетку с КБЖУ\n"
        "• 📸 Сфотографируй продукт с брендом\n"
        "• Укажи место: \"капучино в Старбаксе\"\n\n"
        "2️⃣ Кнопки меню:\n"
        "📊 Сегодня — прогресс за день\n"
        "📈 Неделя — статистика за 7 дней\n"
        "🤔 Что съесть? — умный совет по питанию\n"
        "👤 Профиль — твои данные и цели\n"
        "📤 Экспорт — скачать все записи в CSV\n"
        "💬 Поддержка — связь с разработчиком\n\n"
        "3️⃣ Команды:\n"
        "/start — перезапустить бота\n"
        "/help — эта справка\n"
        "/ping — проверить связь с сервером"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard())



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

    text = build_meal_response_text(
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        accuracy_level="ESTIMATE",
        summary=summary,
    )

    meal_id = meal.get("id")
    reply_markup = (
        build_meal_keyboard(meal_id=meal_id, day=today) if meal_id else None
    )
    await message.answer(text, reply_markup=reply_markup)


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
    processing_msg = await message.answer("⏳ Обрабатываю запрос — это может занять 1–2 минуты. Пришлю сообщение, как только всё будет готово!")

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

    text = build_meal_response_text(
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        accuracy_level=accuracy_level,
        notes=notes,
        source_url=source_url,
        summary=summary,
    )

    meal_id = meal.get("id")
    reply_markup = (
        build_meal_keyboard(meal_id=meal_id, day=today, source_url=source_url)
        if meal_id
        else None
    )

    try:
        await processing_msg.delete()
    except Exception:
        pass
    await message.answer(text, reply_markup=reply_markup)


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
    processing_msg = await message.answer("⏳ Обрабатываю запрос — это может занять 1–2 минуты. Пришлю сообщение, как только всё будет готово!")

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

    text = build_meal_response_text(
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        accuracy_level=accuracy_level,
        notes=notes,
        source_url=source_url,
        summary=summary,
    )

    meal_id = meal.get("id")
    reply_markup = (
        build_meal_keyboard(meal_id=meal_id, day=today, source_url=source_url)
        if meal_id
        else None
    )

    try:
        await processing_msg.delete()
    except Exception:
        pass
    await message.answer(text, reply_markup=reply_markup)


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
    processing_msg = await message.answer("⏳ Обрабатываю запрос — это может занять 1–2 минуты. Пришлю сообщение, как только всё будет готово!")

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

    text = build_meal_response_text(
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        accuracy_level=accuracy_level,
        notes=notes,
        source_url=source_url,
        summary=summary,
    )
    
    meal_id = meal.get("id")
    reply_markup = (
        build_meal_keyboard(meal_id=meal_id, day=today, source_url=source_url)
        if meal_id
        else None
    )

    try:
        await processing_msg.delete()
    except Exception:
        pass
    await message.answer(text, reply_markup=reply_markup)


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
    processing_msg = await message.answer("⏳ Обрабатываю запрос — это может занять 1–2 минуты. Пришлю сообщение, как только всё будет готово!")
    
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
    
    text = build_meal_response_text(
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        accuracy_level=accuracy_level,
        notes=notes,
        source_url=source_url,
        summary=summary,
    )

    meal_id = meal.get("id")
    reply_markup = (
        build_meal_keyboard(meal_id=meal_id, day=today, source_url=source_url)
        if meal_id
        else None
    )

    try:
        await processing_msg.delete()
    except Exception:
        pass
    await message.answer(text, reply_markup=reply_markup)


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
    processing_msg = await message.answer("⏳ Обрабатываю запрос — это может занять 1–2 минуты. Пришлю сообщение, как только всё будет готово!")
    
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
    
    text = build_meal_response_text(
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        accuracy_level=accuracy_level,
        notes=notes,
        source_url=source_url,
        summary=summary,
    )

    meal_id = meal.get("id")
    reply_markup = (
        build_meal_keyboard(meal_id=meal_id, day=today, source_url=source_url)
        if meal_id
        else None
    )

    try:
        await processing_msg.delete()
    except Exception:
        pass
    await message.answer(text, reply_markup=reply_markup)


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

    reply_markup = build_day_actions_keyboard(day=today)
    await message.answer("\n".join(text_lines), reply_markup=reply_markup)

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

    days = [day for day, _summary in days_with_data]
    reply_markup = build_week_days_keyboard(days)
    await message.answer("\n".join(text_lines), reply_markup=reply_markup)


@router.callback_query(F.data.startswith("daylist:"))
async def handle_daylist(query: types.CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    # Сбрасываем состояние при входе в список записей
    await state.clear()

    # Parse callback data: "daylist:{day}" or "daylist:{day}:from_today"
    parts = query.data.split(":", 2)
    day_str = parts[1] if len(parts) >= 2 else ""
    skip_summary = len(parts) >= 3 and parts[2] == "from_today"

    try:
        day = date_type.fromisoformat(day_str)
    except ValueError:
        await query.message.answer("Не понял дату. Попробуй ещё раз 🙏")
        return

    tg_id = query.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await query.message.answer("Не удалось связаться с backend'ом. Попробуй позже 🙏")
        return

    user_id = user["id"]
    summary = await get_day_summary(user_id=user_id, day=day)
    if summary is None:
        await query.message.answer("За этот день нет записей 🌱")
        return

    # Показываем сводку только если пришли НЕ из "Сегодня" (чтобы не дублировать)
    if not skip_summary:
        await query.message.answer(build_day_summary_text(summary, day))

    meals = summary.get("meals", [])
    if not meals:
        await query.message.answer("Приёмов пищи за этот день нет.")
        return

    for meal in meals:
        meal_id = meal.get("id")
        reply_markup = (
            build_meal_keyboard(meal_id=meal_id, day=day) if meal_id else None
        )
        await query.message.answer(
            format_meal_entry(meal), reply_markup=reply_markup
        )


@router.callback_query(F.data.startswith("meal_edit:"))
async def handle_meal_edit(query: types.CallbackQuery, state: FSMContext) -> None:
    await query.answer()

    parts = query.data.split(":", 2)
    if len(parts) < 3:
        await query.message.answer("Не удалось открыть редактирование.")
        return

    try:
        meal_id = int(parts[1])
        day_str = parts[2]
    except ValueError:
        await query.message.answer("Не удалось прочитать данные для редактирования.")
        return

    await state.update_data(meal_id=meal_id, day=day_str)
    await state.set_state(MealEditState.waiting_for_choice)

    try:
        day = date_type.fromisoformat(day_str)
    except ValueError:
        await query.message.answer("Не удалось прочитать дату записи.")
        return

    reply_markup = build_edit_choice_keyboard(meal_id=meal_id, day=day)
    await query.message.answer(
        "Что хочешь отредактировать?", reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("meal_edit_field:"))
async def handle_meal_edit_field(query: types.CallbackQuery, state: FSMContext) -> None:
    await query.answer()

    parts = query.data.split(":", 3)
    if len(parts) < 4:
        await query.message.answer("Не удалось выбрать тип редактирования.")
        return

    field = parts[1]
    try:
        meal_id = int(parts[2])
        day_str = parts[3]
    except ValueError:
        await query.message.answer("Не удалось прочитать данные для редактирования.")
        return

    if field == "cancel":
        await state.clear()
        await query.message.answer("Ок, отменил редактирование.")
        return

    await state.update_data(meal_id=meal_id, day=day_str, field=field)

    if field == "name":
        await state.set_state(MealEditState.waiting_for_name)
        await query.message.answer("Напиши новое название блюда.")
    elif field == "macros":
        await state.set_state(MealEditState.waiting_for_macros)
        await query.message.answer(
            "Введи КБЖУ в формате к/б/ж/у.\n"
            "Пример: 350/25/10/40"
        )
    elif field == "time":
        await state.set_state(MealEditState.waiting_for_time)
        await query.message.answer(
            "Введи время приёма пищи в формате ЧЧ:ММ.\n"
            "Пример: 14:30"
        )
    else:
        await query.message.answer("Не понял, что редактировать.")


async def finalize_meal_update(
    message: types.Message,
    state: FSMContext,
    *,
    description: Optional[str] = None,
    calories: Optional[float] = None,
    protein_g: Optional[float] = None,
    fat_g: Optional[float] = None,
    carbs_g: Optional[float] = None,
) -> None:
    data = await state.get_data()
    meal_id = data.get("meal_id")
    day_str = data.get("day")

    if not meal_id:
        await state.clear()
        await message.answer("Не удалось найти запись для редактирования.")
        return

    updated = await update_meal(
        meal_id=meal_id,
        description=description,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
    )
    if updated is None:
        await message.answer("Не получилось обновить запись. Попробуй позже 🙏")
        return

    await state.clear()
    await message.answer("✅ Обновил запись.")

    reply_markup = None
    if day_str:
        try:
            day = date_type.fromisoformat(day_str)
        except ValueError:
            day = None
        if day:
            reply_markup = build_meal_keyboard(meal_id=meal_id, day=day)

    await message.answer(format_meal_entry(updated), reply_markup=reply_markup)

    if day_str:
        try:
            day = date_type.fromisoformat(day_str)
        except ValueError:
            return

        user = await ensure_user(message.from_user.id)
        if user is None:
            return

        summary = await get_day_summary(user_id=user["id"], day=day)
        if summary:
            await message.answer(build_day_summary_text(summary, day))


@router.message(MealEditState.waiting_for_name)
async def handle_meal_edit_name(message: types.Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Название не должно быть пустым. Напиши ещё раз.")
        return

    await finalize_meal_update(message, state, description=text)


@router.message(MealEditState.waiting_for_macros)
async def handle_meal_edit_macros(message: types.Message, state: FSMContext) -> None:
    text = message.text or ""
    parsed = parse_macros_input(text)
    if parsed is None:
        await message.answer(
            "Не понял формат. Введи КБЖУ как к/б/ж/у.\n"
            "Пример: 350/25/10/40"
        )
        return

    calories, protein_g, fat_g, carbs_g = parsed
    await finalize_meal_update(
        message,
        state,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
    )


@router.message(MealEditState.waiting_for_time)
async def handle_meal_edit_time(message: types.Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    # Parse time in HH:MM format
    import re
    match = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if not match:
        await message.answer(
            "Не понял формат. Введи время как ЧЧ:ММ.\n"
            "Пример: 14:30"
        )
        return

    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        await message.answer("Некорректное время. Часы 0-23, минуты 0-59.")
        return

    data = await state.get_data()
    meal_id = data.get("meal_id")
    day_str = data.get("day")

    if not meal_id or not day_str:
        await state.clear()
        await message.answer("Не удалось найти запись для редактирования.")
        return

    try:
        day = date_type.fromisoformat(day_str)
    except ValueError:
        await state.clear()
        await message.answer("Не удалось прочитать дату записи.")
        return

    # Build datetime with the meal's date and user-specified time
    import pytz
    user_tz_name = "Europe/Moscow"  # default, will be overridden by user's timezone
    user = await get_user(message.from_user.id)
    if user and user.get("timezone"):
        user_tz_name = user["timezone"]
    user_tz = pytz.timezone(user_tz_name)

    naive_dt = datetime(day.year, day.month, day.day, hour, minute)
    local_dt = user_tz.localize(naive_dt)
    eaten_at_iso = local_dt.isoformat()

    updated = await update_meal(meal_id=meal_id, eaten_at=eaten_at_iso)
    if updated is None:
        await message.answer("Не получилось обновить время. Попробуй позже 🙏")
        return

    await state.clear()
    await message.answer(f"✅ Обновил время на {hour:02d}:{minute:02d}.")


@router.callback_query(F.data.startswith("meal_delete:"))
async def handle_meal_delete(query: types.CallbackQuery) -> None:
    await query.answer()

    parts = query.data.split(":", 2)
    if len(parts) < 3:
        await query.message.answer("Не удалось открыть удаление.")
        return

    try:
        meal_id = int(parts[1])
        day_str = parts[2]
    except ValueError:
        await query.message.answer("Не удалось прочитать данные для удаления.")
        return

    confirm_keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="✅ Да",
                    callback_data=f"meal_delete_confirm:{meal_id}:{day_str}",
                ),
                types.InlineKeyboardButton(
                    text="❌ Нет",
                    callback_data=f"meal_delete_cancel:{meal_id}:{day_str}",
                ),
            ]
        ]
    )

    await query.message.answer("Удалить запись?", reply_markup=confirm_keyboard)


@router.callback_query(F.data.startswith("meal_delete_confirm:"))
async def handle_meal_delete_confirm(query: types.CallbackQuery) -> None:
    await query.answer()

    parts = query.data.split(":", 2)
    if len(parts) < 3:
        await query.message.answer("Не удалось удалить запись.")
        return

    try:
        meal_id = int(parts[1])
        day_str = parts[2]
    except ValueError:
        await query.message.answer("Не удалось прочитать данные для удаления.")
        return

    ok = await delete_meal(meal_id)
    if not ok:
        await query.message.answer("Не получилось удалить запись. Попробуй позже 🙏")
        return

    await query.message.answer("✅ Запись удалена.")

    try:
        day = date_type.fromisoformat(day_str)
    except ValueError:
        return

    user = await ensure_user(query.from_user.id)
    if user is None:
        return

    summary = await get_day_summary(user_id=user["id"], day=day)
    if summary:
        await query.message.answer(build_day_summary_text(summary, day))
    else:
        await query.message.answer("За этот день больше нет записей 🌱")


@router.callback_query(F.data.startswith("meal_delete_cancel:"))
async def handle_meal_delete_cancel(query: types.CallbackQuery) -> None:
    await query.answer("Удаление отменено")


@router.callback_query(F.data.startswith("advice_log:"))
async def handle_advice_log(query: types.CallbackQuery, state: FSMContext) -> None:
    """Log a meal from food advice selection."""
    await query.answer()

    parts = query.data.split(":", 1)
    if len(parts) < 2:
        await query.message.answer("Не удалось определить выбранный вариант.")
        return

    try:
        item_idx = int(parts[1])
    except ValueError:
        await query.message.answer("Не удалось определить выбранный вариант.")
        return

    data = await state.get_data()
    advice_result = data.get("advice_result")
    if not advice_result:
        await query.message.answer("Данные рекомендации устарели. Попробуй запросить совет заново.")
        return

    items = advice_result.get("items") or []
    if item_idx >= len(items):
        await query.message.answer("Вариант не найден.")
        return

    chosen_item = items[item_idx]
    item_name = chosen_item.get("name", "Блюдо")
    calories = float(chosen_item.get("calories_kcal", 0))
    protein_g = float(chosen_item.get("protein_g", 0))
    fat_g = float(chosen_item.get("fat_g", 0))
    carbs_g = float(chosen_item.get("carbs_g", 0))
    item_source_url = chosen_item.get("source_url") or advice_result.get("source_url")

    # Create meal via API
    tg_id = query.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await query.message.answer("Не удалось связаться с backend'ом. Попробуй позже 🙏")
        return

    today = date_type.today()
    result = await create_meal(
        user_id=user["id"],
        day=today,
        description=item_name,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        accuracy_level="ESTIMATE",
    )
    if result is None:
        await query.message.answer("Не удалось записать приём пищи. Попробуй позже 🙏")
        return

    await state.clear()

    response_text = build_meal_response_text(
        description=item_name,
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        accuracy_level="ESTIMATE",
        source_url=item_source_url,
    )

    reply_markup = None
    if normalize_source_url(item_source_url):
        reply_markup = types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton(text="🔗 Источник", url=normalize_source_url(item_source_url)),
        ]])

    await query.message.answer(response_text, reply_markup=reply_markup)


# ---------- Food Advice Input Handlers (waiting_for_input state) ----------

async def _process_food_advice_input(
    message: types.Message,
    state: FSMContext,
    text: str,
    image_url: Optional[str] = None,
) -> None:
    """Common logic for processing user input in food advice mode."""
    data = await state.get_data()
    nutrition_context = data.get("nutrition_context")
    tg_id = str(message.from_user.id)

    await state.clear()

    processing_msg = await message.answer("🤔 Думаю, что тебе посоветовать — вернусь через 1–2 минуты!")

    try:
        result = await agent_run_workflow(
            telegram_id=tg_id,
            text=text,
            image_url=image_url,
            force_intent="food_advice",
            nutrition_context=nutrition_context,
        )
    except Exception as e:
        logger.error(f"[FOOD_ADVICE] Error running agent workflow: {e}", exc_info=True)
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer("Сервис временно недоступен, попробуй позже.")
        return

    try:
        await processing_msg.delete()
    except Exception:
        pass

    if result is None:
        await message.answer("Сервис временно недоступен, попробуй позже.")
        return

    agent_items = result.get("items") or []
    source_url = result.get("source_url")
    response_text = build_food_advice_response(result)
    reply_markup = build_food_advice_keyboard(agent_items, source_url=source_url) if agent_items else get_main_menu_keyboard()

    try:
        await message.answer(response_text, reply_markup=reply_markup)
        if agent_items:
            await state.update_data(advice_result=result)
            await state.set_state(FoodAdviceState.waiting_for_choice)
        logger.info(f"[FOOD_ADVICE] Sent food_advice for telegram_id={tg_id}")
    except Exception as send_error:
        logger.error(f"[FOOD_ADVICE] Error sending response: {send_error}", exc_info=True)
        await message.answer("Получен ответ, но возникла ошибка при отправке. Попробуй ещё раз.")


@router.message(FoodAdviceState.waiting_for_input, F.text)
async def handle_food_advice_text(message: types.Message, state: FSMContext) -> None:
    """Handle text input in food advice mode."""
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пожалуйста, отправь текст с вариантами или фото меню.")
        return
    await _process_food_advice_input(message, state, text=text)


@router.message(FoodAdviceState.waiting_for_input, F.photo)
async def handle_food_advice_photo(message: types.Message, state: FSMContext) -> None:
    """Handle photo input in food advice mode (e.g., menu photo)."""
    try:
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        bio = await message.bot.download_file(file.file_path)
        photo_bytes = bio.read()
    except Exception as e:
        logger.error(f"[FOOD_ADVICE] Error downloading photo: {e}")
        await message.answer("Не удалось скачать фото. Попробуй ещё раз.")
        return

    if not photo_bytes:
        await message.answer("Фото пустое. Попробуй ещё раз.")
        return

    b64 = base64.b64encode(photo_bytes).decode("utf-8")
    image_data_uri = f"data:image/jpeg;base64,{b64}"
    text = (message.caption or "").strip() or "Посоветуй что выбрать из вариантов на фото"

    await _process_food_advice_input(message, state, text=text, image_url=image_data_uri)


@router.message(FoodAdviceState.waiting_for_input, F.voice)
async def handle_food_advice_voice(message: types.Message, state: FSMContext) -> None:
    """Handle voice input in food advice mode."""
    try:
        file = await message.bot.get_file(message.voice.file_id)
        bio = await message.bot.download_file(file.file_path)
        audio_bytes = bio.read()
    except Exception as e:
        logger.error(f"[FOOD_ADVICE] Error downloading voice: {e}")
        await message.answer("Не удалось скачать голосовое. Попробуй ещё раз.")
        return

    if not audio_bytes:
        await message.answer("Голосовое пустое. Попробуй ещё раз.")
        return

    await message.answer("🎙 Секунду, распознаю голос...")
    parsed = await voice_parse_meal(audio_bytes)
    if parsed is None:
        await message.answer("Не удалось обработать голос. Попробуй ещё раз.")
        return

    transcript = (parsed.get("transcript", "") or "").strip()
    if not transcript:
        await message.answer("Не удалось распознать речь. Попробуй ещё раз.")
        return

    await message.answer(f"Распознал: \"{transcript}\"")
    await _process_food_advice_input(message, state, text=transcript)


@router.message(FoodAdviceState.waiting_for_input)
async def handle_food_advice_other(message: types.Message, state: FSMContext) -> None:
    """Handle unsupported input types in food advice mode."""
    await message.answer("Отправь текст с вариантами, фото меню или голосовое сообщение.")


# ---------- End Food Advice Input Handlers ----------


@router.message(F.voice)
async def handle_voice(message: types.Message, state: FSMContext) -> None:
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

    transcript = (parsed.get("transcript", "") or "").strip()
    if not transcript:
        await message.answer("Не удалось распознать речь. Попробуй ещё раз 🙏")
        return

    processing_msg = await message.answer("⏳ Обрабатываю запрос — это может занять 1–2 минуты. Пришлю сообщение, как только всё будет готово!")

    try:
        result = await agent_run_workflow(
            telegram_id=str(message.from_user.id),
            text=transcript,
        )
    except Exception as e:
        logger.error(f"[VOICE] Error running agent workflow: {e}", exc_info=True)
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer("Сервис временно недоступен, попробуй позже.")
        return

    if result is None:
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer("Сервис временно недоступен, попробуй позже.")
        return

    try:
        await processing_msg.delete()
    except Exception:
        pass

    intent = result.get("intent", "unknown")
    message_text = result.get("message_text", "Ошибка обработки")
    source_url = result.get("source_url")
    agent_items = result.get("items") or []
    has_source_url = source_url is not None and source_url != ""
    has_item_sources = any(isinstance(it, dict) and it.get("source_url") for it in agent_items)

    await message.answer(f"Распознал: \"{transcript}\"")

    reply_markup = None
    if intent in MEAL_LOGGING_INTENTS:
        meal_id = await get_latest_meal_id_for_today(message.from_user.id)
        if meal_id:
            reply_markup = build_meal_keyboard(
                meal_id=meal_id,
                day=date_type.today(),
                source_url=source_url,
                items=agent_items,
            )

    if reply_markup is None and (has_source_url or has_item_sources):
        source_buttons = []
        for it in agent_items:
            if isinstance(it, dict) and normalize_source_url(it.get("source_url")):
                item_name = it.get("name") or "Продукт"
                label = item_name if len(item_name) <= 30 else item_name[:27] + "..."
                source_buttons.append([types.InlineKeyboardButton(text=f"🔗 Источник: {label}", url=normalize_source_url(it["source_url"]))])
        if not source_buttons and has_source_url:
            source_buttons.append([types.InlineKeyboardButton(text="🔗 Источник", url=source_url)])
        if source_buttons:
            reply_markup = types.InlineKeyboardMarkup(inline_keyboard=source_buttons)

    response_text = message_text
    if intent in MEAL_LOGGING_INTENTS:
        response_text = build_meal_response_from_agent(result)

    await message.answer(response_text, reply_markup=reply_markup)


@router.message(F.photo)
async def handle_photo(message: types.Message, state: FSMContext) -> None:
    """
    Handle photo messages. Downloads the photo, base64-encodes it,
    and sends it through the agent workflow for food recognition.
    """
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Не удалось связаться с backend'ом. Попробуй позже 🙏")
        return

    # Download the largest resolution photo
    try:
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        bio = await message.bot.download_file(file.file_path)
        photo_bytes = bio.read()
    except Exception as e:
        logger.error(f"[PHOTO] Error downloading photo: {e}")
        await message.answer("Не удалось скачать фото. Попробуй ещё раз 🙏")
        return

    if not photo_bytes:
        await message.answer("Фото пустое. Попробуй ещё раз 🙏")
        return

    # Base64-encode as data URI
    b64 = base64.b64encode(photo_bytes).decode("utf-8")
    image_data_uri = f"data:image/jpeg;base64,{b64}"

    # Use caption as text, or a default prompt
    text = (message.caption or "").strip() or "Определи что на фото и посчитай КБЖУ"

    processing_msg = await message.answer("📸 Анализирую фото — вернусь через 1–2 минуты!")

    try:
        result = await agent_run_workflow(
            telegram_id=str(tg_id),
            text=text,
            image_url=image_data_uri,
        )
    except Exception as e:
        logger.error(f"[PHOTO] Error running agent workflow: {e}", exc_info=True)
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer("Сервис временно недоступен, попробуй позже.")
        return

    if result is None:
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer("Сервис временно недоступен, попробуй позже.")
        return

    try:
        await processing_msg.delete()
    except Exception:
        pass

    intent = result.get("intent", "unknown")
    message_text = result.get("message_text", "Ошибка обработки")
    source_url = result.get("source_url")
    agent_items = result.get("items") or []
    has_source_url = source_url is not None and source_url != ""
    has_item_sources = any(isinstance(it, dict) and it.get("source_url") for it in agent_items)

    reply_markup = None
    if intent in MEAL_LOGGING_INTENTS:
        meal_id = await get_latest_meal_id_for_today(message.from_user.id)
        if meal_id:
            reply_markup = build_meal_keyboard(
                meal_id=meal_id,
                day=date_type.today(),
                source_url=source_url,
                items=agent_items,
            )

    if reply_markup is None and (has_source_url or has_item_sources):
        source_buttons = []
        for it in agent_items:
            if isinstance(it, dict) and normalize_source_url(it.get("source_url")):
                item_name = it.get("name") or "Продукт"
                label = item_name if len(item_name) <= 30 else item_name[:27] + "..."
                source_buttons.append([types.InlineKeyboardButton(text=f"🔗 Источник: {label}", url=normalize_source_url(it["source_url"]))])
        if not source_buttons and has_source_url:
            source_buttons.append([types.InlineKeyboardButton(text="🔗 Источник", url=source_url)])
        if source_buttons:
            reply_markup = types.InlineKeyboardMarkup(inline_keyboard=source_buttons)

    response_text = message_text
    if intent in MEAL_LOGGING_INTENTS:
        response_text = build_meal_response_from_agent(result)

    await message.answer(response_text, reply_markup=reply_markup)


@router.message(Command("agent"))
async def cmd_agent(message: types.Message, state: FSMContext) -> None:
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
    processing_msg = await message.answer("⏳ Обрабатываю запрос — это может занять 1–2 минуты. Пришлю сообщение, как только всё будет готово!")
    
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
        agent_items = result.get("items") or []
        has_source_url = source_url is not None and source_url != ""
        has_item_sources = any(isinstance(it, dict) and it.get("source_url") for it in agent_items)
        
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
                f"items_count={len(agent_items)}, "
                f"source_url={source_url}"
            )
        
        # Delete processing message
        try:
            await processing_msg.delete()
        except Exception:
            pass
        
        # Build reply with edit/delete buttons when meal is logged
        reply_markup = None
        if intent in MEAL_LOGGING_INTENTS:
            meal_id = await get_latest_meal_id_for_today(message.from_user.id)
            if meal_id:
                reply_markup = build_meal_keyboard(
                    meal_id=meal_id,
                    day=date_type.today(),
                    source_url=source_url,
                    items=agent_items,
                )

        if reply_markup is None and (has_source_url or has_item_sources):
            source_buttons = []
            for it in agent_items:
                if isinstance(it, dict) and normalize_source_url(it.get("source_url")):
                    item_name = it.get("name") or "Продукт"
                    label = item_name if len(item_name) <= 30 else item_name[:27] + "..."
                    source_buttons.append([types.InlineKeyboardButton(text=f"🔗 Источник: {label}", url=normalize_source_url(it["source_url"]))])
            if not source_buttons and has_source_url:
                source_buttons.append([types.InlineKeyboardButton(text="🔗 Источник", url=source_url)])
            if source_buttons:
                reply_markup = types.InlineKeyboardMarkup(inline_keyboard=source_buttons)
        
        # Send the message
        try:
            response_text = message_text
            if intent in MEAL_LOGGING_INTENTS:
                response_text = build_meal_response_from_agent(result)
            await message.answer(response_text, reply_markup=reply_markup)
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
    await cmd_agent(message, state)


@router.message(F.text)
async def handle_plain_text(message: types.Message, state: FSMContext) -> None:
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
    processing_msg = await message.answer("⏳ Обрабатываю запрос — это может занять 1–2 минуты. Пришлю сообщение, как только всё будет готово!")
    
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
        agent_items = result.get("items") or []
        has_source_url = source_url is not None and source_url != ""
        has_item_sources = any(isinstance(it, dict) and it.get("source_url") for it in agent_items)
        
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
                f"items_count={len(agent_items)}, "
                f"source_url={source_url}"
            )
        
        # Delete processing message
        try:
            await processing_msg.delete()
        except Exception:
            pass
        
        # Build reply with edit/delete buttons when meal is logged
        reply_markup = None
        if intent in MEAL_LOGGING_INTENTS:
            meal_id = await get_latest_meal_id_for_today(message.from_user.id)
            if meal_id:
                reply_markup = build_meal_keyboard(
                    meal_id=meal_id,
                    day=date_type.today(),
                    source_url=source_url,
                    items=agent_items,
                )

        if reply_markup is None and (has_source_url or has_item_sources):
            source_buttons = []
            for it in agent_items:
                if isinstance(it, dict) and normalize_source_url(it.get("source_url")):
                    item_name = it.get("name") or "Продукт"
                    label = item_name if len(item_name) <= 30 else item_name[:27] + "..."
                    source_buttons.append([types.InlineKeyboardButton(text=f"🔗 Источник: {label}", url=normalize_source_url(it["source_url"]))])
            if not source_buttons and has_source_url:
                source_buttons.append([types.InlineKeyboardButton(text="🔗 Источник", url=source_url)])
            if source_buttons:
                reply_markup = types.InlineKeyboardMarkup(inline_keyboard=source_buttons)
        
        # Send the message
        try:
            response_text = message_text
            if intent in MEAL_LOGGING_INTENTS:
                response_text = build_meal_response_from_agent(result)
            await message.answer(response_text, reply_markup=reply_markup)
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
    
    # Важно: onboarding_router должен быть первым для приоритета обработки меню
    dp.include_router(onboarding_router)
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
