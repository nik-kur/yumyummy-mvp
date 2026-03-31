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
    get_meal_by_id,
    create_saved_meal,
    get_saved_meals,
    get_saved_meal,
    update_saved_meal,
    delete_saved_meal,
    use_saved_meal,
)
from app.bot.onboarding import router as onboarding_router, start_onboarding, get_main_menu_keyboard, FoodAdviceState
from app.bot.billing import router as billing_router, check_billing_access, show_paywall
from app.bot.api_client import get_billing_status, start_trial
from app.i18n import DEFAULT_LANG, tr


router = Router()
LANG = DEFAULT_LANG

MEAL_LOGGING_INTENTS = {"log_meal", "product", "eatout", "barcode", "photo_meal", "nutrition_label"}

# FSM States for agent clarification
class AgentClarification(StatesGroup):
    waiting_for_clarification = State()


class MealEditState(StatesGroup):
    waiting_for_choice = State()
    waiting_for_name = State()
    waiting_for_macros = State()
    waiting_for_time = State()


class SavedMealStates(StatesGroup):
    waiting_for_save_name = State()
    waiting_for_add_name = State()
    waiting_for_add_macros = State()
    waiting_for_edit_name = State()
    waiting_for_edit_macros = State()



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
        return tr("runbot.default_source", LANG)
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
        tr("runbot.summary_today", LANG),
        f"• Calories: {total_calories}",
        f"• Protein: {total_protein} g",
        f"• Fat: {total_fat} g",
        f"• Carbs: {total_carbs} g",
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
        tr("runbot.logged", LANG, description=description),
        "",
    ]
    if all_zero:
        lines.append(tr("runbot.macros_unknown", LANG))
    else:
        lines.append(f"{calories} kcal · P {protein_g} g · F {fat_g} g · C {carbs_g} g")
    if notes:
        lines.append("")
        lines.append(tr("runbot.note", LANG, notes=notes))
    lines.append("")
    normalized_url = normalize_source_url(source_url)
    if normalized_url:
        lines.append(tr("runbot.source_link", LANG, source_label=source_label))
    else:
        lines.append(tr("runbot.source_hint", LANG, source_label=source_label))
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
        description = message_text or tr("runbot.no_description", LANG)

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

    lines = [base_text, "", "———", "", tr("runbot.by_items", LANG), ""]
    for item in valid_items:
        item_name = item.get("name") or tr("runbot.dish", LANG)
        item_calories = round(float(item.get("calories_kcal") or 0))
        item_protein = round(float(item.get("protein_g") or 0), 1)
        item_fat = round(float(item.get("fat_g") or 0), 1)
        item_carbs = round(float(item.get("carbs_g") or 0), 1)
        item_all_zero = item_calories == 0 and item_protein == 0 and item_fat == 0 and item_carbs == 0
        item_source_url = item.get("source_url")
        item_source_label = format_source_label(item_source_url) if item_source_url else format_source_label(None)
        item_source_line = tr("runbot.source_link", LANG, source_label=item_source_label) if normalize_source_url(item_source_url) else tr("runbot.source_hint", LANG, source_label=item_source_label)
        if item_all_zero:
            lines.extend([
                f"📝 {item_name}:",
                tr("runbot.macros_unknown", LANG),
                item_source_line,
                "",
            ])
        else:
            lines.extend([
                f"📝 {item_name}:",
                f"{item_calories} kcal · P {item_protein} g · F {item_fat} g · C {item_carbs} g",
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
        return message_text or "Could not generate a recommendation."

    lines = [tr("runbot.recommendation_title", LANG), ""]

    labels = [
        tr("runbot.recommendation_best", LANG),
        tr("runbot.recommendation_alt1", LANG),
        tr("runbot.recommendation_alt2", LANG),
    ]
    for idx, item in enumerate(items[:3]):
        item_name = _strip_markdown_bold(item.get("name") or tr("runbot.dish", LANG))
        item_cal = round(float(item.get("calories_kcal") or 0))
        item_prot = round(float(item.get("protein_g") or 0), 1)
        item_fat = round(float(item.get("fat_g") or 0), 1)
        item_carbs = round(float(item.get("carbs_g") or 0), 1)
        label = labels[idx] if idx < len(labels) else tr("runbot.recommendation_variant", LANG, n=idx + 1)
        lines.append(f"{idx + 1}. {label}: {item_name}")
        if item_cal > 0:
            lines.append(f"   {item_cal} kcal · P {item_prot} g · F {item_fat} g · C {item_carbs} g")
        lines.append("")

    if message_text:
        reasoning = _extract_message_text_block(
            message_text,
            ["Why these options"],
            ["How to improve", "Hack", "Tip", "Lifehack"],
        )
        if reasoning:
            heading, _, body = reasoning.partition(":")
            lines.append(f"💬 {heading.strip()}:")
            body = body.strip()
            if body:
                lines.append(body[0].upper() + body[1:])
            lines.append("")

        tip = _extract_message_text_block(
            message_text,
            ["How to improve", "Hack", "Tip", "Lifehack"],
            [],
        )
        if tip:
            heading, _, body = tip.partition(":")
            lines.append(f"💡 {heading.strip()}:")
            body = body.strip()
            if body:
                lines.append(body[0].upper() + body[1:])
            lines.append("")

    lines.append(tr("runbot.save_variant_prompt", LANG))

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def build_food_advice_keyboard(items: list, source_url: Optional[str] = None) -> types.InlineKeyboardMarkup:
    """Build keyboard with 'Log variant N' buttons and optional source links for food advice."""
    rows = []
    labels = [
        tr("runbot.save_variant_btn1", LANG),
        tr("runbot.save_variant_btn2", LANG),
        tr("runbot.save_variant_btn3", LANG),
    ]
    for idx in range(min(len(items), 3)):
        item_name = items[idx].get("name", tr("runbot.dish", LANG)) if isinstance(items[idx], dict) else tr("runbot.dish", LANG)
        short_name = item_name if len(item_name) <= 20 else item_name[:17] + "..."
        rows.append([types.InlineKeyboardButton(
            text=f"{labels[idx]} ({short_name})",
            callback_data=f"advice_log:{idx}",
        )])

    source_buttons = []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        item_url = normalize_source_url(item.get("source_url")) or normalize_source_url(source_url)
        if item_url:
            item_name = _strip_markdown_bold(item.get("name") or tr("runbot.dish", LANG))
            label = item_name if len(item_name) <= 30 else item_name[:27] + "..."
            source_buttons.append([types.InlineKeyboardButton(
                text=tr("runbot.source_link", LANG, source_label=label),
                url=item_url,
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
                text="✏️ Edit",
                callback_data=f"meal_edit:{meal_id}:{day.isoformat()}",
            ),
            types.InlineKeyboardButton(
                text="🗑 Delete",
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
                item_name = item.get("name") or "Product"
                # Truncate long names for button text
                label = item_name if len(item_name) <= 30 else item_name[:27] + "..."
                rows.append([types.InlineKeyboardButton(text=tr("runbot.source_link", LANG, source_label=label), url=item_url)])

    # Fallback: single top-level source button if no per-item sources were added
    if len(rows) == 1:
        url = normalize_source_url(source_url)
        if url:
            rows.append([types.InlineKeyboardButton(text="🔗 Source", url=url)])

    rows.append([types.InlineKeyboardButton(
        text="💾 Save to My Menu",
        callback_data=f"save_meal:{meal_id}",
    )])

    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def build_day_actions_keyboard(day: date_type) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="🍽 View logged meals",
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
                    text="Name",
                    callback_data=f"meal_edit_field:name:{meal_id}:{day.isoformat()}",
                ),
                types.InlineKeyboardButton(
                    text="Macros",
                    callback_data=f"meal_edit_field:macros:{meal_id}:{day.isoformat()}",
                ),
                types.InlineKeyboardButton(
                    text="🕐 Time",
                    callback_data=f"meal_edit_field:time:{meal_id}:{day.isoformat()}",
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="Cancel",
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
            f"📅 Daily summary ({date_str}):",
            f"• Calories: {total_calories}",
            f"• Protein: {total_protein} g",
            f"• Fat: {total_fat} g",
            f"• Carbs: {total_carbs} g",
        ]
    )


def format_meal_entry(meal: Dict[str, Any]) -> str:
    description = meal.get("description_user") or "No description"
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
        f"• Calories: {calories}",
    ]
    if protein_g or fat_g or carbs_g:
        lines.extend(
            [
                f"• Protein: {protein_g} g",
                f"• Fat: {fat_g} g",
                f"• Carbs: {carbs_g} g",
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
    Supports deeplink: /start billing_check — post-purchase return flow.
    """
    tg_id = message.from_user.id

    # Handle post-purchase deeplink return
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].strip() == "billing_check":
        billing = await get_billing_status(tg_id)
        status = (billing or {}).get("access_status", "expired")
        if status == "active":
            provider = (billing or {}).get("subscription_provider", "")
            provider_label = " via Gumroad" if provider == "gumroad" else ""
            await message.answer(
                f"✅ <b>Payment confirmed{provider_label}!</b>\n\nYour subscription is now active.\nTell me what you ate, and I'll log it!\n\n"
                "You can manage your subscription anytime in <b>Profile → Manage subscription</b>.",
                parse_mode="HTML",
            )
            return
        else:
            from app.bot.billing import show_paywall
            await message.answer(
                "⏳ Payment not received yet. If you just paid, please wait a moment and try again.",
            )
            return

    user = await ensure_user(tg_id)

    if user is None:
        await message.answer(
            "Hi! I'm YumYummy 🧃\n\n"
            "Looks like I can't reach the server right now.\n"
            "Please try again a little later 🙏",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    # Проверяем, прошёл ли пользователь онбординг
    if not user.get("onboarding_completed", False):
        await start_onboarding(message, state)
        return

    # Check billing status
    billing = await get_billing_status(tg_id)
    access = (billing or {}).get("access_status", "new")

    if access == "new":
        trial_result = await start_trial(tg_id)
        if trial_result and not trial_result.get("already_started"):
            target_cal = user.get('target_calories') or 2000
            target_prot = user.get('target_protein_g') or 150
            target_fat = user.get('target_fat_g') or 65
            target_carbs = user.get('target_carbs_g') or 200
            text = (
                f"🎉 3-day trial activated!\n\n"
                f"Your daily targets:\n"
                f"• 🔥 {target_cal:.0f} kcal\n"
                f"• 🥩 {target_prot:.0f} g protein\n"
                f"• 🥑 {target_fat:.0f} g fat\n"
                f"• 🍞 {target_carbs:.0f} g carbs\n\n"
                f"Type or dictate what you ate, and I'll log it!"
            )
            await message.answer(text, reply_markup=get_main_menu_keyboard())
            return

    if access in ("trial_expired", "expired"):
        await show_paywall(message, billing)
        return

    # Active trial or subscription — normal welcome
    target_cal = user.get('target_calories') or 2000
    target_prot = user.get('target_protein_g') or 150
    target_fat = user.get('target_fat_g') or 65
    target_carbs = user.get('target_carbs_g') or 200

    extra = ""
    if access == "trial":
        days_left = billing.get("trial_days_remaining", 0) if billing else 0
        extra = f"\n⏳ Trial: {days_left:.0f} days left\n"

    text = (
        f"Welcome back! 👋\n{extra}\n"
        f"Your daily targets:\n"
        f"• 🔥 {target_cal:.0f} kcal\n"
        f"• 🥩 {target_prot:.0f} g protein\n"
        f"• 🥑 {target_fat:.0f} g fat\n"
        f"• 🍞 {target_carbs:.0f} g carbs\n\n"
        f"Type or dictate what you ate, and I'll log it!"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    text = (
        "📝 How to use the bot:\n\n"
        "1️⃣ Log food:\n"
        "• Type what you ate: \"2 eggs and toast\"\n"
        "• Or send a voice message\n"
        "• 📸 Send a food photo - bot estimates calories/macros\n"
        "• 📸 Take a photo of a nutrition label\n"
        "• 📸 Take a product photo with brand\n"
        "• Add context: \"cappuccino at Starbucks\"\n\n"
        "2️⃣ Menu buttons:\n"
        "📊 Today - daily progress\n"
        "📈 Week - 7-day statistics\n"
        "🤔 What should I eat? - smart nutrition advice\n"
        "👤 Profile - your data and goals\n"
        "📤 Export - download all logs to CSV\n"
        "💬 Support - contact developer\n\n"
        "3️⃣ Commands:\n"
        "/start - restart bot\n"
        "/help - this help\n"
        "/ping - check server connection"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard())



@router.message(Command("ping"))
async def cmd_ping(message: types.Message) -> None:
    """
    Проверяем связь с backend'ом через /health.
    """
    health = await ping_backend()
    if health is None:
        await message.answer("❌ Could not connect to YumYummy server.")
        return

    status = health.get("status", "unknown")
    app_name = health.get("app", "unknown")

    await message.answer(
        f"✅ Backend connection is healthy.\n"
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
    if not await check_billing_access(message):
        return
    if not message.text:
        await message.answer("I couldn't parse your message. Example: /log 350 oatmeal with banana")
        return

    # Отделяем команду от аргументов
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "You need to pass parameters.\n\n"
            "Examples:\n"
            "/log 350 oatmeal with banana\n"
            "/log 350 25 10 40 oatmeal with banana"
        )
        return

    args_str = parts[1]
    tokens = args_str.split()

    if not tokens:
        await message.answer(
            "Couldn't parse parameters.\n"
            "Example: /log 350 25 10 40 oatmeal with banana"
        )
        return

    # Парсим калории
    try:
        calories = float(tokens[0])
    except ValueError:
        await message.answer(
            "The first number after /log must be calories.\n"
            "Example: /log 350 oatmeal with banana"
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
        description = "No description"

    # Гарантируем, что пользователь есть в backend
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Could not reach backend. Please try again later 🙏")
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
        await message.answer("Could not log the meal. Please try again later 🙏")
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
            "I couldn't parse your message. Usage example:\n"
            "/barcode 4607025392147"
        )
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Add a barcode after the command.\n\n"
            "Example:\n"
            "/barcode 4607025392147"
        )
        return

    barcode = parts[1].strip()
    if not barcode:
        await message.answer(
            "Barcode is empty. Example:\n"
            "/barcode 4607025392147"
        )
        return

    # 1) Гарантируем, что пользователь есть в backend
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Could not reach backend. Please try again later 🙏")
        return

    user_id = user["id"]

    # Отправляем немедленный ответ, что запрос получен
    processing_msg = await message.answer("⏳ Processing request - this may take 1-2 minutes. I'll send results as soon as they're ready!")

    # 2) Просим backend найти продукт по штрихкоду
    parsed = await product_parse_meal_by_barcode(barcode)
    if parsed is None:
        # Удаляем сообщение "Обрабатываю..." перед отправкой ошибки
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(
            "Could not reach backend. Please try again later 🙏"
        )
        return

    description = parsed.get("description", "Product")
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
        await message.answer("Could not log the meal. Please try again later 🙏")
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
            "I couldn't parse your message. Usage example:\n"
            "/product cottage cheese brand: Epica 6%"
        )
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Add a product name after the command.\n\n"
            "Example:\n"
            "/product cottage cheese brand: Epica 6%"
        )
        return

    text = parts[1].strip()
    if not text:
        await message.answer(
            "Name is empty. Example:\n"
            "/product cottage cheese brand: Epica 6%"
        )
        return

    # Парсим название, бренд и магазин
    name = text
    brand = None
    store = None

    # Supports both EN and RU markers for future multilingual support
    if "brand:" in text.lower() or "бренд:" in text.lower():
        brand_marker = "brand:" if "brand:" in text.lower() else "бренд:"
        parts_brand = text.lower().split(brand_marker)
        if len(parts_brand) == 2:
            name = parts_brand[0].strip()
            rest = parts_brand[1].strip()
            if "store:" in rest.lower() or "магазин:" in rest.lower():
                store_marker = "store:" if "store:" in rest.lower() else "магазин:"
                parts_store = rest.split(store_marker)
                brand = parts_store[0].strip()
                store = parts_store[1].strip() if len(parts_store) > 1 else None
            else:
                brand = rest
    elif "store:" in text.lower() or "магазин:" in text.lower():
        store_marker = "store:" if "store:" in text.lower() else "магазин:"
        parts_store = text.lower().split(store_marker)
        if len(parts_store) == 2:
            name = parts_store[0].strip()
            store = parts_store[1].strip()

    # 1) Гарантируем, что пользователь есть в backend
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Could not reach backend. Please try again later 🙏")
        return

    user_id = user["id"]

    # Отправляем немедленный ответ, что запрос получен
    processing_msg = await message.answer("⏳ Processing request - this may take 1-2 minutes. I'll send results as soon as they're ready!")

    # 2) Просим backend найти продукт по названию
    parsed = await product_parse_meal_by_name(name, brand=brand, store=store)
    if parsed is None:
        # Удаляем сообщение "Обрабатываю..." перед отправкой ошибки
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(
            "Could not reach backend. Please try again later 🙏"
        )
        return

    description = parsed.get("description", "Product")
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
        await message.answer("Could not log the meal. Please try again later 🙏")
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
            "I couldn't parse your message. Usage example:\n"
            "/ai_log had a bowl of borscht, two slices of black bread and tea"
        )
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Add a meal description after the command.\n\n"
            "Example:\n"
            "/ai_log had a bowl of borscht, two slices of black bread and tea"
        )
        return

    raw_text = parts[1].strip()
    if not raw_text:
        await message.answer(
            "Description is empty. Example:\n"
            "/ai_log had a bowl of borscht, two slices of black bread and tea"
        )
        return

    # 1) Гарантируем, что пользователь есть в backend
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Could not reach backend. Please try again later 🙏")
        return

    user_id = user["id"]

    # Отправляем немедленный ответ, что запрос получен
    processing_msg = await message.answer("⏳ Processing request - this may take 1-2 minutes. I'll send results as soon as they're ready!")

    # 2) Просим backend/LLM оценить КБЖУ
    parsed = await ai_parse_meal(raw_text)
    if parsed is None:
        # Удаляем сообщение "Обрабатываю..." перед отправкой ошибки
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(
            "Couldn't get an AI nutrition estimate. Please try again shortly 🙏"
        )
        return

    description = parsed.get("description", "").strip() or "No description provided"
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
        await message.answer("Could not log the meal. Please try again later 🙏")
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
            "Usage: /eatout <dish description>\n"
            "Examples:\n"
            "• /eatout syrniki from Coffeemania\n"
            "• /eatout carbonara pasta at Vapiano"
        )
        return
    
    raw_text = parts[1].strip()
    
    if not raw_text:
        await message.answer(
            "Provide a dish description:\n"
            "Example: /eatout syrniki from Coffeemania"
        )
        return
    
    # 1) Гарантируем, что пользователь есть в backend
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Could not reach backend. Please try again later 🙏")
        return
    
    user_id = user["id"]
    
    # Отправляем немедленный ответ, что запрос получен
    processing_msg = await message.answer("⏳ Processing request - this may take 1-2 minutes. I'll send results as soon as they're ready!")
    
    # 2) Просим backend найти блюдо из ресторана по свободному тексту
    parsed = await restaurant_parse_text(text=raw_text)
    if parsed is None:
        # Удаляем сообщение "Обрабатываю..." перед отправкой ошибки
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(
            "Could not reach backend. Please try again later 🙏"
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
        await message.answer("Could not log the meal. Please try again later 🙏")
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
            "Usage: /eatoutA <dish description>\n"
            "Examples:\n"
            "• /eatoutA syrniki from Coffeemania\n"
            "• /eatoutA carbonara pasta at Vapiano\n\n"
            "⚠️ This is an experimental version powered by OpenAI web search"
        )
        return
    
    raw_text = parts[1].strip()
    
    if not raw_text:
        await message.answer(
            "Provide a dish description:\n"
            "Example: /eatoutA syrniki from Coffeemania"
        )
        return
    
    # 1) Гарантируем, что пользователь есть в backend
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Could not reach backend. Please try again later 🙏")
        return
    
    user_id = user["id"]
    
    # Отправляем немедленный ответ, что запрос получен
    processing_msg = await message.answer("⏳ Processing request - this may take 1-2 minutes. I'll send results as soon as they're ready!")
    
    # 2) Просим backend найти блюдо из ресторана через OpenAI web search
    parsed = await restaurant_parse_text_openai(text=raw_text)
    if parsed is None:
        # Удаляем сообщение "Обрабатываю..." перед отправкой ошибки
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(
            "Could not reach backend. Please try again later 🙏"
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
        await message.answer("Could not log the meal. Please try again later 🙏")
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
        await message.answer("Could not reach backend. Please try again later 🙏")
        return

    user_id = user["id"]
    today = date_type.today()

    summary = await get_day_summary(user_id=user_id, day=today)
    if summary is None:
        await message.answer("No entries for today yet 🥗")
        return

    date_str = today.strftime("%d.%m.%Y")

    # Округляем значения
    total_calories = round(summary.get('total_calories', 0))
    total_protein = round(summary.get('total_protein_g', 0), 1)
    total_fat = round(summary.get('total_fat_g', 0), 1)
    total_carbs = round(summary.get('total_carbs_g', 0), 1)
    
    text_lines = [
        f"📅 Today's summary ({date_str}):",
        f"• Calories: {total_calories}",
        f"• Protein: {total_protein} g",
        f"• Fat: {total_fat} g",
        f"• Carbs: {total_carbs} g",
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
        await message.answer("Could not reach backend. Please try again later 🙏")
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
        await message.answer("No entries this week yet 🌱")
        return

    start_str = start_date.strftime("%d.%m.%Y")
    end_str = today.strftime("%d.%m.%Y")

    # Округляем итоговые значения
    total_calories = round(total_calories)
    total_protein_g = round(total_protein_g, 1)
    total_fat_g = round(total_fat_g, 1)
    total_carbs_g = round(total_carbs_g, 1)
    
    text_lines = [
        f"📊 Weekly summary ({start_str} — {end_str}):",
        f"• Calories: {total_calories}",
        f"• Protein: {total_protein_g} g",
        f"• Fat: {total_fat_g} g",
        f"• Carbs: {total_carbs_g} g",
        "",
        "By day:",
    ]

    for day, summary in days_with_data:
        d_str = day.strftime("%d.%m")
        text_lines.append(
            f"{d_str}: {round(summary.get('total_calories', 0))} kcal, "
            f"P {round(summary.get('total_protein_g', 0), 1)} / "
            f"F {round(summary.get('total_fat_g', 0), 1)} / "
            f"C {round(summary.get('total_carbs_g', 0), 1)}"
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
        await query.message.answer("Could not parse the date. Please try again 🙏")
        return

    tg_id = query.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await query.message.answer("Could not reach backend. Please try again later 🙏")
        return

    user_id = user["id"]
    summary = await get_day_summary(user_id=user_id, day=day)
    if summary is None:
        await query.message.answer("No entries for this day 🌱")
        return

    # Показываем сводку только если пришли НЕ из "Сегодня" (чтобы не дублировать)
    if not skip_summary:
        await query.message.answer(build_day_summary_text(summary, day))

    meals = summary.get("meals", [])
    if not meals:
        await query.message.answer("No meals logged for this day.")
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
        await query.message.answer("Could not open editing.")
        return

    try:
        meal_id = int(parts[1])
        day_str = parts[2]
    except ValueError:
        await query.message.answer("Could not read editing data.")
        return

    await state.update_data(meal_id=meal_id, day=day_str)
    await state.set_state(MealEditState.waiting_for_choice)

    try:
        day = date_type.fromisoformat(day_str)
    except ValueError:
        await query.message.answer("Could not read entry date.")
        return

    reply_markup = build_edit_choice_keyboard(meal_id=meal_id, day=day)
    await query.message.answer(
        "What would you like to edit?", reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("meal_edit_field:"))
async def handle_meal_edit_field(query: types.CallbackQuery, state: FSMContext) -> None:
    await query.answer()

    parts = query.data.split(":", 3)
    if len(parts) < 4:
        await query.message.answer("Could not select edit type.")
        return

    field = parts[1]
    try:
        meal_id = int(parts[2])
        day_str = parts[3]
    except ValueError:
        await query.message.answer("Could not read editing data.")
        return

    if field == "cancel":
        await state.clear()
        await query.message.answer("Okay, editing canceled.")
        return

    await state.update_data(meal_id=meal_id, day=day_str, field=field)

    if field == "name":
        await state.set_state(MealEditState.waiting_for_name)
        await query.message.answer("Send a new meal name.")
    elif field == "macros":
        await state.set_state(MealEditState.waiting_for_macros)
        await query.message.answer(
            "Enter macros in kcal/p/f/c format.\n"
            "Example: 350/25/10/40"
        )
    elif field == "time":
        await state.set_state(MealEditState.waiting_for_time)
        await query.message.answer(
            "Enter meal time in HH:MM format.\n"
            "Example: 14:30"
        )
    else:
        await query.message.answer("I couldn't determine what to edit.")


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
        await message.answer("Could not find an entry for editing.")
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
        await message.answer("Could not update the entry. Please try again later 🙏")
        return

    await state.clear()
    await message.answer("✅ Entry updated.")

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
        await message.answer("Name cannot be empty. Please send it again.")
        return

    await finalize_meal_update(message, state, description=text)


@router.message(MealEditState.waiting_for_macros)
async def handle_meal_edit_macros(message: types.Message, state: FSMContext) -> None:
    text = message.text or ""
    parsed = parse_macros_input(text)
    if parsed is None:
        await message.answer(
            "Invalid format. Enter macros as kcal/p/f/c.\n"
            "Example: 350/25/10/40"
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
            "Invalid format. Enter time as HH:MM.\n"
            "Example: 14:30"
        )
        return

    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        await message.answer("Invalid time. Hours 0-23, minutes 0-59.")
        return

    data = await state.get_data()
    meal_id = data.get("meal_id")
    day_str = data.get("day")

    if not meal_id or not day_str:
        await state.clear()
        await message.answer("Could not find entry for editing.")
        return

    try:
        day = date_type.fromisoformat(day_str)
    except ValueError:
        await state.clear()
        await message.answer("Could not read entry date.")
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
        await message.answer("Could not update time. Please try again later 🙏")
        return

    await state.clear()
    await message.answer(f"✅ Updated time to {hour:02d}:{minute:02d}.")


@router.callback_query(F.data.startswith("meal_delete:"))
async def handle_meal_delete(query: types.CallbackQuery) -> None:
    await query.answer()

    parts = query.data.split(":", 2)
    if len(parts) < 3:
        await query.message.answer("Could not open deletion.")
        return

    try:
        meal_id = int(parts[1])
        day_str = parts[2]
    except ValueError:
        await query.message.answer("Could not read deletion data.")
        return

    confirm_keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="✅ Yes",
                    callback_data=f"meal_delete_confirm:{meal_id}:{day_str}",
                ),
                types.InlineKeyboardButton(
                    text="❌ No",
                    callback_data=f"meal_delete_cancel:{meal_id}:{day_str}",
                ),
            ]
        ]
    )

    await query.message.answer("Delete this entry?", reply_markup=confirm_keyboard)


@router.callback_query(F.data.startswith("meal_delete_confirm:"))
async def handle_meal_delete_confirm(query: types.CallbackQuery) -> None:
    await query.answer()

    parts = query.data.split(":", 2)
    if len(parts) < 3:
        await query.message.answer("Could not delete entry.")
        return

    try:
        meal_id = int(parts[1])
        day_str = parts[2]
    except ValueError:
        await query.message.answer("Could not read deletion data.")
        return

    ok = await delete_meal(meal_id)
    if not ok:
        await query.message.answer("Could not delete entry. Please try again later 🙏")
        return

    await query.message.answer("✅ Entry deleted.")

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
        await query.message.answer("No more entries for this day 🌱")


@router.callback_query(F.data.startswith("meal_delete_cancel:"))
async def handle_meal_delete_cancel(query: types.CallbackQuery) -> None:
    await query.answer("Deletion canceled")


@router.callback_query(F.data.startswith("advice_log:"))
async def handle_advice_log(query: types.CallbackQuery, state: FSMContext) -> None:
    """Log a meal from food advice selection."""
    await query.answer()

    parts = query.data.split(":", 1)
    if len(parts) < 2:
        await query.message.answer("Could not determine selected option.")
        return

    try:
        item_idx = int(parts[1])
    except ValueError:
        await query.message.answer("Could not determine selected option.")
        return

    data = await state.get_data()
    advice_result = data.get("advice_result")
    if not advice_result:
        await query.message.answer("Recommendation data is stale. Request advice again.")
        return

    items = advice_result.get("items") or []
    if item_idx >= len(items):
        await query.message.answer("Option not found.")
        return

    chosen_item = items[item_idx]
    item_name = chosen_item.get("name", "Dish")
    calories = float(chosen_item.get("calories_kcal", 0))
    protein_g = float(chosen_item.get("protein_g", 0))
    fat_g = float(chosen_item.get("fat_g", 0))
    carbs_g = float(chosen_item.get("carbs_g", 0))
    item_source_url = chosen_item.get("source_url") or advice_result.get("source_url")

    # Create meal via API
    tg_id = query.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await query.message.answer("Could not reach backend. Please try again later 🙏")
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
        await query.message.answer("Could not log the meal. Please try again later 🙏")
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
            types.InlineKeyboardButton(text="🔗 Source", url=normalize_source_url(item_source_url)),
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

    processing_msg = await message.answer("🤔 Thinking about the best recommendation - back in 1-2 minutes!")

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
        await message.answer("Service is temporarily unavailable, please try later.")
        return

    try:
        await processing_msg.delete()
    except Exception:
        pass

    if result is None:
        await message.answer("Service is temporarily unavailable, please try later.")
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
        await message.answer("Received a response, but failed to send it. Please try again.")


@router.message(FoodAdviceState.waiting_for_input, F.text)
async def handle_food_advice_text(message: types.Message, state: FSMContext) -> None:
    """Handle text input in food advice mode."""
    text = (message.text or "").strip()
    if not text:
        await message.answer("Please send text options or a menu photo.")
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
        await message.answer("Could not download photo. Please try again.")
        return

    if not photo_bytes:
        await message.answer("Photo is empty. Please try again.")
        return

    b64 = base64.b64encode(photo_bytes).decode("utf-8")
    image_data_uri = f"data:image/jpeg;base64,{b64}"
    text = (message.caption or "").strip() or "Suggest what to choose from options in the photo"

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
        await message.answer("Could not download voice message. Please try again.")
        return

    if not audio_bytes:
        await message.answer("Voice message is empty. Please try again.")
        return

    await message.answer("🎙 One second, transcribing voice...")
    parsed = await voice_parse_meal(audio_bytes)
    if parsed is None:
        await message.answer("Could not process voice. Please try again.")
        return

    transcript = (parsed.get("transcript", "") or "").strip()
    if not transcript:
        await message.answer("Could not recognize speech. Please try again.")
        return

    await message.answer(f"Recognized: \"{transcript}\"")
    await _process_food_advice_input(message, state, text=transcript)


@router.message(FoodAdviceState.waiting_for_input)
async def handle_food_advice_other(message: types.Message, state: FSMContext) -> None:
    """Handle unsupported input types in food advice mode."""
    await message.answer("Send text options, a menu photo, or a voice message.")


# ---------- End Food Advice Input Handlers ----------


# ============ Saved Meals FSM text handlers (MUST be before catch-all F.text/F.voice/F.photo) ============

async def _do_save_meal(
    message: types.Message, state: FSMContext, meal_id: int, name: str
) -> None:
    meal = await get_meal_by_id(meal_id)
    if not meal:
        await message.answer("Entry not found.")
        return

    user = await ensure_user(message.chat.id)
    if not user:
        await message.answer("Could not reach backend. Please try again later.")
        return

    data = await state.get_data()
    raw_items = data.get(f"meal_items_{meal_id}", [])

    items_payload = []
    if raw_items:
        for it in raw_items:
            if not isinstance(it, dict):
                continue
            items_payload.append({
                "name": it.get("name", "Dish"),
                "grams": it.get("grams"),
                "calories_kcal": float(it.get("calories_kcal", 0)),
                "protein_g": float(it.get("protein_g", 0)),
                "fat_g": float(it.get("fat_g", 0)),
                "carbs_g": float(it.get("carbs_g", 0)),
                "source_url": it.get("source_url"),
            })
    else:
        items_payload.append({
            "name": meal.get("description_user", name),
            "grams": None,
            "calories_kcal": float(meal.get("calories", 0)),
            "protein_g": float(meal.get("protein_g", 0)),
            "fat_g": float(meal.get("fat_g", 0)),
            "carbs_g": float(meal.get("carbs_g", 0)),
            "source_url": None,
        })

    result = await create_saved_meal(
        user_id=user["id"],
        name=name,
        total_calories=float(meal.get("calories", 0)),
        total_protein_g=float(meal.get("protein_g", 0)),
        total_fat_g=float(meal.get("fat_g", 0)),
        total_carbs_g=float(meal.get("carbs_g", 0)),
        items=items_payload,
    )

    if result:
        await message.answer(f"✅ " + f"{name}" + " saved to My Menu!")
    else:
        await message.answer("Could not save. Please try again later.")


@router.message(SavedMealStates.waiting_for_save_name)
async def handle_save_name_input(message: types.Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Name cannot be empty. Please try again.")
        return

    data = await state.get_data()
    meal_id = data.get("save_meal_id")
    await state.set_state(None)
    await _do_save_meal(message, state, meal_id, name)


@router.message(SavedMealStates.waiting_for_add_name)
async def handle_add_name(message: types.Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Name cannot be empty. Please try again.")
        return
    await state.update_data(add_name=name)
    await state.set_state(SavedMealStates.waiting_for_add_macros)
    await message.answer(
        "Now enter macros in format: calories protein fat carbs\n"
        "Example: 350 25 10 40"
    )


@router.message(SavedMealStates.waiting_for_add_macros)
async def handle_add_macros(message: types.Message, state: FSMContext) -> None:
    parsed = parse_macros_input(message.text or "")
    if not parsed:
        await message.answer(
            "Invalid format. Enter 4 numbers separated by spaces or '/':\n"
            "Example: 350 25 10 40"
        )
        return

    calories, protein, fat, carbs = parsed
    data = await state.get_data()
    name = data.get("add_name", "Dish")
    await state.clear()

    user = await ensure_user(message.from_user.id)
    if not user:
        await message.answer("Could not reach backend. Please try again later.")
        return

    result = await create_saved_meal(
        user_id=user["id"],
        name=name,
        total_calories=calories,
        total_protein_g=protein,
        total_fat_g=fat,
        total_carbs_g=carbs,
        items=[{
            "name": name,
            "grams": None,
            "calories_kcal": calories,
            "protein_g": protein,
            "fat_g": fat,
            "carbs_g": carbs,
            "source_url": None,
        }],
    )

    if result:
        await message.answer(
            f"✅ " + f"{name}" + " added to My Menu!\n"
            f"{round(calories)} kcal · P {round(protein, 1)} g · F {round(fat, 1)} g · C {round(carbs, 1)} g"
        )
    else:
        await message.answer("Could not save. Please try again later.")


@router.message(SavedMealStates.waiting_for_edit_name)
async def handle_edit_name_input(message: types.Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Name cannot be empty. Please try again.")
        return

    data = await state.get_data()
    saved_id = data.get("edit_saved_id")
    await state.clear()

    result = await update_saved_meal(saved_id, name=name)
    if result:
        await message.answer(f"✅ Name updated to " + f"{name}")
    else:
        await message.answer("Could not update. Please try again later.")


@router.message(SavedMealStates.waiting_for_edit_macros)
async def handle_edit_macros_input(message: types.Message, state: FSMContext) -> None:
    parsed = parse_macros_input(message.text or "")
    if not parsed:
        await message.answer(
            "Invalid format. Enter 4 numbers separated by spaces or '/':\n"
            "Example: 350 25 10 40"
        )
        return

    calories, protein, fat, carbs = parsed
    data = await state.get_data()
    saved_id = data.get("edit_saved_id")
    await state.clear()

    result = await update_saved_meal(
        saved_id,
        total_calories=calories,
        total_protein_g=protein,
        total_fat_g=fat,
        total_carbs_g=carbs,
    )
    if result:
        await message.answer(
            f"✅ Macros updated:\n"
            f"{round(calories)} kcal · P {round(protein, 1)} g · F {round(fat, 1)} g · C {round(carbs, 1)} g"
        )
    else:
        await message.answer("Could not update. Please try again later.")


# ============ End Saved Meals FSM text handlers ============


@router.message(F.voice)
async def handle_voice(message: types.Message, state: FSMContext) -> None:
    """
    Обработка голосовых сообщений.
    Скачивает voice, отправляет на backend для STT и парсинга, логирует приём пищи.
    """
    if not await check_billing_access(message):
        return
    # 1) Гарантируем, что пользователь есть в backend
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Could not reach backend. Please try again later 🙏")
        return

    user_id = user["id"]

    # 2) Скачиваем голосовое сообщение
    try:
        file = await message.bot.get_file(message.voice.file_id)
        bio = await message.bot.download_file(file.file_path)
        audio_bytes = bio.read()
    except Exception as e:
        logger.error(f"[VOICE] Error downloading voice: {e}")
        await message.answer("Could not download voice message. Please try again 🙏")
        return

    if not audio_bytes:
        await message.answer("Voice message is empty. Please try again 🙏")
        return

    # 3) Отправляем сообщение о начале обработки
    await message.answer("🎙 One second, transcribing voice and estimating macros...")

    # 4) Отправляем на backend для STT и парсинга
    parsed = await voice_parse_meal(audio_bytes)
    if parsed is None:
        await message.answer("Could not process voice. Please try again 🙏")
        return

    transcript = (parsed.get("transcript", "") or "").strip()
    if not transcript:
        await message.answer("Could not recognize speech. Please try again 🙏")
        return

    processing_msg = await message.answer("⏳ Processing request - this may take 1-2 minutes. I'll send results as soon as they're ready!")

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
        await message.answer("Service is temporarily unavailable, please try later.")
        return

    if result is None:
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer("Service is temporarily unavailable, please try later.")
        return

    try:
        await processing_msg.delete()
    except Exception:
        pass

    intent = result.get("intent", "unknown")
    message_text = result.get("message_text", "Processing error")
    source_url = result.get("source_url")
    agent_items = result.get("items") or []
    has_source_url = source_url is not None and source_url != ""
    has_item_sources = any(isinstance(it, dict) and it.get("source_url") for it in agent_items)

    await message.answer(f"Recognized: \"{transcript}\"")

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
            if agent_items:
                await state.update_data(**{f"meal_items_{meal_id}": agent_items})

    if reply_markup is None and (has_source_url or has_item_sources):
        source_buttons = []
        for it in agent_items:
            if isinstance(it, dict) and normalize_source_url(it.get("source_url")):
                item_name = it.get("name") or "Product"
                label = item_name if len(item_name) <= 30 else item_name[:27] + "..."
                source_buttons.append([types.InlineKeyboardButton(text=f"🔗 Source: {label}", url=normalize_source_url(it["source_url"]))])
        if not source_buttons and has_source_url:
            source_buttons.append([types.InlineKeyboardButton(text="🔗 Source", url=source_url)])
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
    if not await check_billing_access(message):
        return
    tg_id = message.from_user.id
    user = await ensure_user(tg_id)
    if user is None:
        await message.answer("Could not reach backend. Please try again later 🙏")
        return

    # Download the largest resolution photo
    try:
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        bio = await message.bot.download_file(file.file_path)
        photo_bytes = bio.read()
    except Exception as e:
        logger.error(f"[PHOTO] Error downloading photo: {e}")
        await message.answer("Could not download photo. Please try again 🙏")
        return

    if not photo_bytes:
        await message.answer("Photo is empty. Please try again 🙏")
        return

    # Base64-encode as data URI
    b64 = base64.b64encode(photo_bytes).decode("utf-8")
    image_data_uri = f"data:image/jpeg;base64,{b64}"

    # Use caption as text, or a default prompt
    text = (message.caption or "").strip() or "Identify what's in the photo and estimate macros"

    processing_msg = await message.answer("📸 Analyzing photo - back in 1-2 minutes!")

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
        await message.answer("Service is temporarily unavailable, please try later.")
        return

    if result is None:
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer("Service is temporarily unavailable, please try later.")
        return

    try:
        await processing_msg.delete()
    except Exception:
        pass

    intent = result.get("intent", "unknown")
    message_text = result.get("message_text", "Processing error")
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
            if agent_items:
                await state.update_data(**{f"meal_items_{meal_id}": agent_items})

    if reply_markup is None and (has_source_url or has_item_sources):
        source_buttons = []
        for it in agent_items:
            if isinstance(it, dict) and normalize_source_url(it.get("source_url")):
                item_name = it.get("name") or "Product"
                label = item_name if len(item_name) <= 30 else item_name[:27] + "..."
                source_buttons.append([types.InlineKeyboardButton(text=f"🔗 Source: {label}", url=normalize_source_url(it["source_url"]))])
        if not source_buttons and has_source_url:
            source_buttons.append([types.InlineKeyboardButton(text="🔗 Source", url=source_url)])
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
        await message.answer("Usage: /agent <your request>\n\nExample: /agent syrniki from Coffeemania")
        return
    
    # Send processing message
    processing_msg = await message.answer("⏳ Processing request - this may take 1-2 minutes. I'll send results as soon as they're ready!")
    
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
            await message.answer("Service is temporarily unavailable, please try later.")
            return
        
        # Extract result fields
        intent = result.get("intent", "unknown")
        message_text = result.get("message_text", "Processing error")
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
                if agent_items:
                    await state.update_data(**{f"meal_items_{meal_id}": agent_items})

        if reply_markup is None and (has_source_url or has_item_sources):
            source_buttons = []
            for it in agent_items:
                if isinstance(it, dict) and normalize_source_url(it.get("source_url")):
                    item_name = it.get("name") or "Product"
                    label = item_name if len(item_name) <= 30 else item_name[:27] + "..."
                    source_buttons.append([types.InlineKeyboardButton(text=f"🔗 Source: {label}", url=normalize_source_url(it["source_url"]))])
            if not source_buttons and has_source_url:
                source_buttons.append([types.InlineKeyboardButton(text="🔗 Source", url=source_url)])
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
                await message.answer("Received a response, but failed to send it. Please try again.")
            except Exception:
                pass
        
    except Exception as e:
        logger.error(f"[BOT /agent] Error: {e}", exc_info=True)
        try:
            await processing_msg.delete()
        except Exception:
            pass
        try:
            await message.answer("Service is temporarily unavailable, please try later.")
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

    if not await check_billing_access(message):
        return
    
    # Send processing message
    processing_msg = await message.answer("⏳ Processing request - this may take 1-2 minutes. I'll send results as soon as they're ready!")
    
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
            await message.answer("Service is temporarily unavailable, please try later.")
            return
        
        # Extract result fields
        intent = result.get("intent", "unknown")
        message_text = result.get("message_text", "Processing error")
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
                if agent_items:
                    await state.update_data(**{f"meal_items_{meal_id}": agent_items})

        if reply_markup is None and (has_source_url or has_item_sources):
            source_buttons = []
            for it in agent_items:
                if isinstance(it, dict) and normalize_source_url(it.get("source_url")):
                    item_name = it.get("name") or "Product"
                    label = item_name if len(item_name) <= 30 else item_name[:27] + "..."
                    source_buttons.append([types.InlineKeyboardButton(text=f"🔗 Source: {label}", url=normalize_source_url(it["source_url"]))])
            if not source_buttons and has_source_url:
                source_buttons.append([types.InlineKeyboardButton(text="🔗 Source", url=source_url)])
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
                await message.answer("Received a response, but failed to send it. Please try again.")
            except Exception:
                pass
        
    except Exception as e:
        logger.error(f"[BOT plain_text] Error: {e}", exc_info=True)
        try:
            await processing_msg.delete()
        except Exception:
            pass
        try:
            await message.answer("Service is temporarily unavailable, please try later.")
        except Exception:
            pass


# ============ Saved Meals ("My Menu") handlers ============

SAVED_MEALS_PER_PAGE = 20


def _build_my_menu_keyboard(
    meals: list, page: int, total: int, per_page: int = SAVED_MEALS_PER_PAGE
) -> types.InlineKeyboardMarkup:
    rows = []
    for m in meals:
        name = m.get("name", "Dish")
        cal = round(m.get("total_calories", 0))
        label = f"✅ {name} ({cal} kcal)"
        if len(label) > 50:
            label = f"✅ {name[:40]}… ({cal})"
        rows.append([types.InlineKeyboardButton(
            text=label, callback_data=f"my_menu_log:{m['id']}"
        )])

    total_pages = max(1, (total + per_page - 1) // per_page)
    if total_pages > 1:
        nav = []
        if page > 1:
            nav.append(types.InlineKeyboardButton(text="← Back", callback_data=f"my_menu_page:{page - 1}"))
        if page < total_pages:
            nav.append(types.InlineKeyboardButton(text="Next →", callback_data=f"my_menu_page:{page + 1}"))
        if nav:
            rows.append(nav)

    rows.append([types.InlineKeyboardButton(
        text="⚙️ Edit My Menu", callback_data="my_menu_edit"
    )])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


# --- Save meal from logged entry ---

@router.callback_query(F.data.startswith("save_meal:"))
async def handle_save_meal(query: types.CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    parts = query.data.split(":", 1)
    if len(parts) < 2:
        await query.message.answer("Could not save.")
        return

    try:
        meal_id = int(parts[1])
    except ValueError:
        await query.message.answer("Could not read data.")
        return

    meal = await get_meal_by_id(meal_id)
    if not meal:
        await query.message.answer("Entry not found.")
        return

    suggested_name = meal.get("description_user", "Dish")
    await state.update_data(save_meal_id=meal_id, save_suggested_name=suggested_name)
    await state.set_state(SavedMealStates.waiting_for_save_name)

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text=f"✅ Save as \"{suggested_name[:35]}\"",
            callback_data=f"save_confirm:{meal_id}",
        )],
    ])
    await query.message.answer(
        "What name should I use to save this in My Menu?\n\n"
        "Tap the button below or type your own name:",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("save_confirm:"))
async def handle_save_confirm(query: types.CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    data = await state.get_data()
    meal_id = data.get("save_meal_id")
    name = data.get("save_suggested_name", "Dish")
    await state.set_state(None)
    await _do_save_meal(query.message, state, meal_id, name)


# --- Quick log from My Menu ---

@router.callback_query(F.data.startswith("my_menu_log:"))
async def handle_my_menu_log(query: types.CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    parts = query.data.split(":", 1)
    if len(parts) < 2:
        await query.message.answer("Error.")
        return

    try:
        saved_meal_id = int(parts[1])
    except ValueError:
        await query.message.answer("Data error.")
        return

    saved = await get_saved_meal(saved_meal_id)
    if not saved:
        await query.message.answer("Saved meal not found.")
        return

    tg_id = query.from_user.id
    user = await ensure_user(tg_id)
    if not user:
        await query.message.answer("Could not reach backend. Please try again later.")
        return

    today = date_type.today()
    meal_result = await create_meal(
        user_id=user["id"],
        day=today,
        description=saved["name"],
        calories=saved["total_calories"],
        protein_g=saved["total_protein_g"],
        fat_g=saved["total_fat_g"],
        carbs_g=saved["total_carbs_g"],
        accuracy_level="EXACT",
    )
    if not meal_result:
        await query.message.answer("Could not log the meal. Please try again later.")
        return

    await use_saved_meal(saved_meal_id)

    cal = round(saved["total_calories"])
    prot = round(saved["total_protein_g"], 1)
    fat = round(saved["total_fat_g"], 1)
    carbs = round(saved["total_carbs_g"], 1)

    lines = [f"✅ Logged \"{saved['name']}\"", ""]
    lines.append(f"{cal} kcal · P {prot} g · F {fat} g · C {carbs} g")

    saved_items = saved.get("items", [])
    if len(saved_items) > 1:
        lines.extend(["", "———", "", "By items:", ""])
        for si in saved_items:
            si_name = si.get("name", "Dish")
            si_cal = round(float(si.get("calories_kcal", 0)))
            si_p = round(float(si.get("protein_g", 0)), 1)
            si_f = round(float(si.get("fat_g", 0)), 1)
            si_c = round(float(si.get("carbs_g", 0)), 1)
            lines.append(f"📝 {si_name}:")
            lines.append(f"{si_cal} kcal · P {si_p} g · F {si_f} g · C {si_c} g")
            lines.append("")

    summary = await get_day_summary(user_id=user["id"], day=today)
    if summary:
        lines.append("")
        lines.extend(build_summary_lines(summary))

    meal_id = meal_result.get("id")
    reply_markup = None
    if meal_id:
        reply_markup = build_meal_keyboard(meal_id=meal_id, day=today)

    await query.message.answer("\n".join(lines), reply_markup=reply_markup)


# --- My Menu pagination ---

@router.callback_query(F.data.startswith("my_menu_page:"))
async def handle_my_menu_page(query: types.CallbackQuery) -> None:
    await query.answer()
    parts = query.data.split(":", 1)
    try:
        page = int(parts[1])
    except (IndexError, ValueError):
        page = 1

    tg_id = query.from_user.id
    data = await get_saved_meals(tg_id, page=page, per_page=SAVED_MEALS_PER_PAGE)
    if not data or not data.get("items"):
        await query.message.answer("My Menu is empty.")
        return

    keyboard = _build_my_menu_keyboard(
        data["items"], data["page"], data["total"], data["per_page"]
    )
    try:
        await query.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        await query.message.answer(
            "🍽 My Menu\n\n"
            "Tap a meal to log it instantly:",
            reply_markup=keyboard,
        )


# --- Edit My Menu ---

@router.callback_query(F.data == "my_menu_edit")
async def handle_my_menu_edit(query: types.CallbackQuery) -> None:
    await query.answer()
    tg_id = query.from_user.id
    data = await get_saved_meals(tg_id, page=1, per_page=100)

    rows = [[types.InlineKeyboardButton(
        text="➕ Add new meal", callback_data="my_menu_add"
    )]]

    if data and data.get("items"):
        for m in data["items"]:
            name = m.get("name", "Dish")
            label = name if len(name) <= 45 else name[:42] + "..."
            rows.append([types.InlineKeyboardButton(
                text=label, callback_data=f"sme_item:{m['id']}"
            )])

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=rows)
    await query.message.answer(
        "⚙️ Edit My Menu\n\n"
        "Tap a meal to edit or delete it:",
        reply_markup=keyboard,
    )


# --- Add new saved meal manually ---

@router.callback_query(F.data == "my_menu_add")
async def handle_my_menu_add(query: types.CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    await state.set_state(SavedMealStates.waiting_for_add_name)
    await query.message.answer("Enter meal name:")


# --- Edit specific saved meal ---

@router.callback_query(F.data.startswith("sme_item:"))
async def handle_sme_item(query: types.CallbackQuery) -> None:
    await query.answer()
    parts = query.data.split(":", 1)
    try:
        saved_id = int(parts[1])
    except (IndexError, ValueError):
        await query.message.answer("Data error.")
        return

    saved = await get_saved_meal(saved_id)
    if not saved:
        await query.message.answer("Meal not found.")
        return

    name = saved.get("name", "Dish")
    cal = round(saved.get("total_calories", 0))
    prot = round(saved.get("total_protein_g", 0), 1)
    fat = round(saved.get("total_fat_g", 0), 1)
    carbs = round(saved.get("total_carbs_g", 0), 1)

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="✏️ Edit name", callback_data=f"sme_name:{saved_id}"
        )],
        [types.InlineKeyboardButton(
            text="📊 Edit macros", callback_data=f"sme_macros:{saved_id}"
        )],
        [types.InlineKeyboardButton(
            text="🗑 Delete", callback_data=f"sme_del:{saved_id}"
        )],
        [types.InlineKeyboardButton(
            text="← Back", callback_data="my_menu_edit"
        )],
    ])

    await query.message.answer(
        f"\"{name}\"\n{cal} kcal · P {prot} g · F {fat} g · C {carbs} g",
        reply_markup=keyboard,
    )


# --- Edit name ---

@router.callback_query(F.data.startswith("sme_name:"))
async def handle_sme_name(query: types.CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    parts = query.data.split(":", 1)
    try:
        saved_id = int(parts[1])
    except (IndexError, ValueError):
        await query.message.answer("Data error.")
        return

    await state.update_data(edit_saved_id=saved_id)
    await state.set_state(SavedMealStates.waiting_for_edit_name)
    await query.message.answer("Enter new name:")


# --- Edit macros ---

@router.callback_query(F.data.startswith("sme_macros:"))
async def handle_sme_macros(query: types.CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    parts = query.data.split(":", 1)
    try:
        saved_id = int(parts[1])
    except (IndexError, ValueError):
        await query.message.answer("Data error.")
        return

    await state.update_data(edit_saved_id=saved_id)
    await state.set_state(SavedMealStates.waiting_for_edit_macros)
    await query.message.answer(
        "Enter new macros in format: calories protein fat carbs\n"
        "Example: 350 25 10 40"
    )


# --- Delete saved meal ---

@router.callback_query(F.data.startswith("sme_del:"))
async def handle_sme_delete(query: types.CallbackQuery) -> None:
    await query.answer()
    parts = query.data.split(":", 1)
    try:
        saved_id = int(parts[1])
    except (IndexError, ValueError):
        await query.message.answer("Data error.")
        return

    saved = await get_saved_meal(saved_id)
    name = saved.get("name", "Dish") if saved else "Dish"

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text="✅ Yes", callback_data=f"sme_del_yes:{saved_id}"
            ),
            types.InlineKeyboardButton(
                text="❌ No", callback_data="my_menu_edit"
            ),
        ]
    ])
    await query.message.answer(
        f"Delete \"{name}\" from My Menu?", reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("sme_del_yes:"))
async def handle_sme_delete_confirm(query: types.CallbackQuery) -> None:
    await query.answer()
    parts = query.data.split(":", 1)
    try:
        saved_id = int(parts[1])
    except (IndexError, ValueError):
        await query.message.answer("Data error.")
        return

    ok = await delete_saved_meal(saved_id)
    if ok:
        await query.message.answer("✅ Meal deleted from My Menu.")
    else:
        await query.message.answer("Could not delete. Please try again later.")


async def main() -> None:
    bot = Bot(token=settings.telegram_bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # billing_router first: handles pre_checkout_query and successful_payment
    dp.include_router(billing_router)
    # onboarding_router: menu button handlers during onboarding
    dp.include_router(onboarding_router)
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
