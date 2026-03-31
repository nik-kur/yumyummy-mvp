"""
Модуль онбординга и главного меню для Telegram бота.
Содержит FSM состояния, обработчики и клавиатуры.
"""
import json
import re
import logging
from datetime import date as date_type, timedelta
from typing import Optional

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from app.bot.api_client import (
    get_user,
    update_user,
    get_user_export_url,
    get_day_summary,
    get_saved_meals,
    start_trial,
    get_billing_status,
    get_paddle_portal_url,
    submit_churn_survey,
)
from app.bot.billing import check_billing_access
from app.core.config import settings
from app.i18n import DEFAULT_LANG, tr

logger = logging.getLogger(__name__)

router = Router()
LANG = DEFAULT_LANG

# Константы
SUPPORT_USERNAME = "nik_kur"


# ============ FSM States ============

class OnboardingStates(StatesGroup):
    """Состояния для онбординга"""
    waiting_for_start = State()
    waiting_for_goal = State()
    waiting_for_gender = State()
    waiting_for_params = State()
    waiting_for_activity = State()
    waiting_for_goals_confirmation = State()
    waiting_for_manual_kbju = State()
    waiting_for_timezone = State()
    waiting_for_timezone_text = State()
    tutorial_step_1 = State()
    tutorial_step_2 = State()


class ProfileStates(StatesGroup):
    """Состояния для редактирования профиля"""
    waiting_for_manual_kbju = State()


class CancelFlowStates(StatesGroup):
    """Состояния для churn survey перед отменой подписки"""
    waiting_for_reason = State()
    waiting_for_comment = State()


class FoodAdviceState(StatesGroup):
    """Состояния для режима food advice"""
    waiting_for_choice = State()
    waiting_for_input = State()


# ============ KBJU Calculation (Mifflin-St Jeor) ============

def calculate_bmr(gender: str, weight_kg: float, height_cm: int, age: int) -> float:
    """
    Рассчитать базовый метаболизм по формуле Миффлина-Сан Жеора.
    """
    if gender == "male":
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161


def calculate_tdee(bmr: float, activity_level: str) -> float:
    """
    Рассчитать суточный расход энергии с учётом активности.
    """
    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "high": 1.725,
        "very_high": 1.9,
    }
    return bmr * activity_multipliers.get(activity_level, 1.55)


def calculate_targets(
    gender: str,
    weight_kg: float,
    height_cm: int,
    age: int,
    activity_level: str,
    goal_type: str,
) -> dict:
    """
    Рассчитать целевые КБЖУ на основе параметров пользователя.
    """
    bmr = calculate_bmr(gender, weight_kg, height_cm, age)
    tdee = calculate_tdee(bmr, activity_level)
    
    # Корректировка калорий в зависимости от цели
    if goal_type == "lose":
        target_calories = tdee - 500  # Дефицит 500 ккал
    elif goal_type == "gain":
        target_calories = tdee + 300  # Профицит 300 ккал
    else:  # maintain
        target_calories = tdee
    
    # Расчёт БЖУ
    # Белок: 2г на кг веса (для похудения/набора) или 1.6г (поддержание)
    if goal_type == "lose":
        protein_g = weight_kg * 2.0
    elif goal_type == "gain":
        protein_g = weight_kg * 2.2
    else:
        protein_g = weight_kg * 1.6
    
    # Жиры: 25-30% от калорий
    fat_calories = target_calories * 0.28
    fat_g = fat_calories / 9
    
    # Углеводы: остаток калорий
    protein_calories = protein_g * 4
    carbs_calories = target_calories - protein_calories - fat_calories
    carbs_g = carbs_calories / 4
    
    return {
        "target_calories": round(target_calories),
        "target_protein_g": round(protein_g),
        "target_fat_g": round(fat_g),
        "target_carbs_g": round(carbs_g),
    }


# ============ Texts ============

WELCOME_TEXT = tr("onboarding.welcome", LANG)

GOAL_TEXT = tr("onboarding.goal", LANG)

GENDER_TEXT = tr("onboarding.gender", LANG)

PARAMS_TEXT = tr("onboarding.params", LANG)

ACTIVITY_TEXT = tr("onboarding.activity", LANG)

TUTORIAL_STEP1_TEXT = """📝 HOW TO LOG FOOD

Main rule: write or speak naturally. I will understand.

✍️ TEXT:
"Had 2 eggs and avocado toast"
"Oatmeal with banana and a spoon of honey"
"Caesar salad and 200g steak"

🎤 VOICE:
Send a voice message: "For breakfast I had cottage cheese with berries and coffee with milk"

🏪 WITH CONTEXT (more accurate):
If you mention where you bought/ordered it, I'll search official nutrition data:

"Cappuccino and a croissant at Starbucks"
-> I'll find exact calories from the official menu

"Epica 6% cottage cheese from VkusVill"
-> I'll find manufacturer data

"Tom Yum at Tanuki"
-> I'll search the restaurant menu

No context? No problem - I'll estimate from average values.

📷 BARCODE:
For packaged products, just take a photo of the barcode on the package. I'll find the product in the database."""

TUTORIAL_STEP2_TEXT = """🤔 SMART ADVICE - WHAT SHOULD I EAT?

Not sure what to choose? Ask me - I'll suggest the best option based on your remaining calories and macros.

Examples:
• "I'm at McDonald's, what should I order?"
• "I need a snack, I have 300 kcal left"
• "What should I cook for dinner? Need protein"

Tap [🤔 What should I eat?] in the menu or just ask!

📊 TRACK YOUR PROGRESS

[📊 Today] - what you ate and what is left
[📈 Week] - 7-day statistics

Check before meals - planning gets much easier."""

FINAL_TEXT = tr("onboarding.final", LANG)

MANUAL_KBJU_TEXT = tr("onboarding.manual_kbju", LANG)


# ============ Keyboards ============

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Today"), KeyboardButton(text="📈 Week")],
            [KeyboardButton(text="🍽 My Menu"), KeyboardButton(text="🤔 What should I eat?")],
            [KeyboardButton(text="👤 Profile"), KeyboardButton(text="📤 Export")],
            [KeyboardButton(text="💬 Support")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Type what you ate or choose an action...",
    )


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Кнопка начала онбординга"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Start", callback_data="onboarding_start")]
        ]
    )


def get_goal_keyboard() -> InlineKeyboardMarkup:
    """Выбор цели"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔻 Lose weight", callback_data="goal_lose")],
            [InlineKeyboardButton(text="⚖️ Maintain weight", callback_data="goal_maintain")],
            [InlineKeyboardButton(text="💪 Gain muscle", callback_data="goal_gain")],
        ]
    )


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Выбор пола"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👨 Male", callback_data="gender_male"),
                InlineKeyboardButton(text="👩 Female", callback_data="gender_female"),
            ]
        ]
    )


def get_activity_keyboard() -> InlineKeyboardMarkup:
    """Выбор уровня активности"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛋 Minimal - mostly sedentary", callback_data="activity_sedentary")],
            [InlineKeyboardButton(text="🚶 Light - 1-2 workouts/week", callback_data="activity_light")],
            [InlineKeyboardButton(text="🏃 Moderate - 3-4 workouts/week", callback_data="activity_moderate")],
            [InlineKeyboardButton(text="🏋️ High - 5-6 workouts/week", callback_data="activity_high")],
            [InlineKeyboardButton(text="⚡ Very high - daily intense activity", callback_data="activity_very_high")],
        ]
    )


def get_goal_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение целей КБЖУ"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Looks good, continue", callback_data="goals_confirm")],
            [InlineKeyboardButton(text="✏️ Enter my targets manually", callback_data="goals_manual")],
        ]
    )


def get_timezone_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора часового пояса"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇷🇺 Moscow (UTC+3)", callback_data="tz:Europe/Moscow")],
            [InlineKeyboardButton(text="🇷🇺 Yekaterinburg (UTC+5)", callback_data="tz:Asia/Yekaterinburg")],
            [InlineKeyboardButton(text="🇷🇺 Novosibirsk (UTC+7)", callback_data="tz:Asia/Novosibirsk")],
            [InlineKeyboardButton(text="🇷🇺 Vladivostok (UTC+10)", callback_data="tz:Asia/Vladivostok")],
            [InlineKeyboardButton(text="🇪🇺 Berlin (UTC+1)", callback_data="tz:Europe/Berlin")],
            [InlineKeyboardButton(text="🇬🇧 London (UTC+0)", callback_data="tz:Europe/London")],
            [InlineKeyboardButton(text="🇺🇸 New York (UTC-5)", callback_data="tz:America/New_York")],
            [InlineKeyboardButton(text="🇦🇪 Dubai (UTC+4)", callback_data="tz:Asia/Dubai")],
            [InlineKeyboardButton(text="🌍 Other...", callback_data="tz:other")],
        ]
    )


def get_tutorial_next_keyboard() -> InlineKeyboardMarkup:
    """Кнопка продолжения туториала"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👍 Got it, next", callback_data="tutorial_next")]
        ]
    )


def get_tutorial_finish_keyboard() -> InlineKeyboardMarkup:
    """Кнопка завершения туториала"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👍 All clear!", callback_data="tutorial_finish")]
        ]
    )


def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для профиля"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Recalculate targets", callback_data="profile_recalculate")],
            [InlineKeyboardButton(text="✏️ Enter targets manually", callback_data="profile_manual_kbju")],
            [InlineKeyboardButton(text="💳 Manage subscription", callback_data="profile_manage_sub")],
        ]
    )


def get_day_actions_keyboard(day_str: str, from_today: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра приёмов пищи за день"""
    suffix = ":from_today" if from_today else ""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🍽 View logged meals", callback_data=f"daylist:{day_str}{suffix}")]
        ]
    )


def get_week_days_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с днями недели для drill-down"""
    today = date_type.today()
    buttons = []
    
    day_names = {
        0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"
    }
    
    for i in range(7):
        day = today - timedelta(days=6-i)
        day_name = day_names[day.weekday()]
        day_label = f"{day_name} {day.day:02d}.{day.month:02d}"
        if day == today:
            day_label = f"📍 {day_label}"
        buttons.append([InlineKeyboardButton(text=day_label, callback_data=f"daylist:{day.isoformat()}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============ Helper Functions ============

def get_targets_presentation_text(
    target_calories: float,
    target_protein_g: float,
    target_fat_g: float,
    target_carbs_g: float,
) -> str:
    """Формирует красивый текст с целями КБЖУ"""
    return f"""🎯 Your personal targets are ready!

🔥 Calories:  {target_calories:.0f} kcal
🥩 Protein:   {target_protein_g:.0f} g
🥑 Fat:       {target_fat_g:.0f} g
🍞 Carbs:     {target_carbs_g:.0f} g

📐 How is this calculated?

I use the Mifflin-St Jeor equation - a gold standard used by nutrition professionals worldwide.

It takes into account:
• Your basal metabolic rate (how many calories your body burns at rest)
• Your activity level
• Your goal (calorie deficit/surplus)

Result: a science-based nutrition plan, not random numbers from the internet.

You can always adjust your targets in "Profile"."""


async def check_onboarding_completed(message: types.Message) -> bool:
    """Проверяет, прошёл ли пользователь онбординг"""
    user = await get_user(message.from_user.id)
    if not user or not user.get("onboarding_completed", False):
        await message.answer(
            tr("onboarding.start_needed", LANG),
        )
        return False
    return True


def build_progress_bar(current: float, target: float, width: int = 15) -> str:
    """Строит прогресс-бар с процентом"""
    if target <= 0:
        return "░" * width + " 0%"
    
    pct = current / target * 100
    ratio = min(current / target, 1.5)
    filled = int(ratio * width)
    filled = min(filled, width + 5)
    
    if ratio <= 1.0:
        bar = "█" * filled + "░" * (width - filled)
    else:
        bar = "█" * width + "🔴" * min(filled - width, 5)
    
    return f"{bar} {pct:.0f}%"


def format_remaining(current: float, target: float, unit: str = "kcal") -> str:
    """Форматирует остаток: 'осталось X' или 'перебор на X'"""
    diff = target - current
    if diff > 0:
        return f"{diff:.0f} {unit} left"
    elif diff < 0:
        return f"over by {abs(diff):.0f} {unit}"
    else:
        return "right on target!"


# ============ Onboarding Handlers ============

async def start_onboarding(message: types.Message, state: FSMContext) -> None:
    """Начать онбординг для нового пользователя"""
    await state.clear()
    await message.answer(
        WELCOME_TEXT,
        reply_markup=get_start_keyboard()
    )
    await state.set_state(OnboardingStates.waiting_for_start)


@router.callback_query(F.data == "onboarding_start")
async def on_onboarding_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Обработка нажатия кнопки 'Начать'"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    await callback.message.answer(GOAL_TEXT, reply_markup=get_goal_keyboard())
    await state.set_state(OnboardingStates.waiting_for_goal)


@router.callback_query(F.data.startswith("goal_"))
async def on_goal_selected(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора цели"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    goal_type = callback.data.replace("goal_", "")
    await state.update_data(goal_type=goal_type)
    
    await callback.message.answer(GENDER_TEXT, reply_markup=get_gender_keyboard())
    await state.set_state(OnboardingStates.waiting_for_gender)


@router.callback_query(F.data.startswith("gender_"))
async def on_gender_selected(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора пола"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    gender = callback.data.replace("gender_", "")
    await state.update_data(gender=gender)
    
    await callback.message.answer(PARAMS_TEXT)
    await state.set_state(OnboardingStates.waiting_for_params)


@router.message(OnboardingStates.waiting_for_params)
async def on_params_received(message: types.Message, state: FSMContext) -> None:
    """Обработка ввода параметров (возраст, рост, вес)"""
    text = message.text.strip()
    
    # Парсим числа из текста
    numbers = re.findall(r"[\d.]+", text)
    
    if len(numbers) < 3:
        await message.answer(
            "Couldn't parse your data. Please send it in this format:\n"
            "Age, Height (cm), Weight (kg)\n\n"
            "Example: 28, 175, 72"
        )
        return
    
    try:
        age = int(float(numbers[0]))
        height_cm = int(float(numbers[1]))
        weight_kg = float(numbers[2])
        
        # Валидация
        if age < 14 or age > 100:
            raise ValueError("Age must be between 14 and 100")
        if height_cm < 100 or height_cm > 250:
            raise ValueError("Height must be between 100 and 250 cm")
        if weight_kg < 30 or weight_kg > 300:
            raise ValueError("Weight must be between 30 and 300 kg")
            
    except (ValueError, IndexError) as e:
        await message.answer(
            "These values look invalid. Check ranges:\n"
            "• Age: 14-100 years\n"
            "• Height: 100-250 cm\n"
            "• Weight: 30-300 kg\n\n"
            "Try again: 28, 175, 72"
        )
        return
    
    await state.update_data(age=age, height_cm=height_cm, weight_kg=weight_kg)
    
    await message.answer(ACTIVITY_TEXT, reply_markup=get_activity_keyboard())
    await state.set_state(OnboardingStates.waiting_for_activity)


@router.callback_query(F.data.startswith("activity_"))
async def on_activity_selected(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора уровня активности и расчёт КБЖУ"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    activity_level = callback.data.replace("activity_", "")
    await state.update_data(activity_level=activity_level)
    
    # Получаем все данные из state
    data = await state.get_data()
    
    # Рассчитываем КБЖУ
    targets = calculate_targets(
        gender=data["gender"],
        weight_kg=data["weight_kg"],
        height_cm=data["height_cm"],
        age=data["age"],
        activity_level=activity_level,
        goal_type=data["goal_type"],
    )
    
    await state.update_data(**targets)
    
    # Показываем результаты
    presentation_text = get_targets_presentation_text(
        targets["target_calories"],
        targets["target_protein_g"],
        targets["target_fat_g"],
        targets["target_carbs_g"],
    )
    
    await callback.message.answer(
        presentation_text,
        reply_markup=get_goal_confirmation_keyboard()
    )
    await state.set_state(OnboardingStates.waiting_for_goals_confirmation)


@router.callback_query(F.data == "goals_confirm")
async def on_goals_confirmed(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Пользователь подтвердил цели КБЖУ"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Сохраняем данные в backend
    data = await state.get_data()
    telegram_id = callback.from_user.id
    
    result = await update_user(
        telegram_id,
        goal_type=data.get("goal_type"),
        gender=data.get("gender"),
        age=data.get("age"),
        height_cm=data.get("height_cm"),
        weight_kg=data.get("weight_kg"),
        activity_level=data.get("activity_level"),
        target_calories=data.get("target_calories"),
        target_protein_g=data.get("target_protein_g"),
        target_fat_g=data.get("target_fat_g"),
        target_carbs_g=data.get("target_carbs_g"),
    )
    
    if not result:
        await callback.message.answer(tr("onboarding.save_error", LANG))
        return
    
    # Переходим к выбору часового пояса
    await callback.message.answer(
        tr("onboarding.timezone_prompt", LANG),
        reply_markup=get_timezone_keyboard()
    )
    await state.set_state(OnboardingStates.waiting_for_timezone)


@router.callback_query(F.data == "goals_manual")
async def on_goals_manual(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Пользователь хочет ввести свои цели вручную"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    await callback.message.answer(MANUAL_KBJU_TEXT)
    await state.set_state(OnboardingStates.waiting_for_manual_kbju)


@router.message(OnboardingStates.waiting_for_manual_kbju)
async def on_manual_kbju_received(message: types.Message, state: FSMContext) -> None:
    """Обработка ручного ввода КБЖУ в онбординге"""
    text = message.text.strip()
    numbers = re.findall(r"[\d.]+", text)
    
    if len(numbers) < 4:
        await message.answer(
            "Couldn't parse your data. Please send it in this format:\n"
            "Calories, Protein (g), Fat (g), Carbs (g)\n\n"
            "Example: 2000, 150, 65, 200"
        )
        return
    
    try:
        target_calories = float(numbers[0])
        target_protein_g = float(numbers[1])
        target_fat_g = float(numbers[2])
        target_carbs_g = float(numbers[3])
        
        # Валидация
        if target_calories < 1000 or target_calories > 10000:
            raise ValueError("Invalid calories")
        if target_protein_g < 0 or target_protein_g > 500:
            raise ValueError("Invalid protein")
        if target_fat_g < 0 or target_fat_g > 500:
            raise ValueError("Invalid fat")
        if target_carbs_g < 0 or target_carbs_g > 1000:
            raise ValueError("Invalid carbs")
            
    except (ValueError, IndexError):
        await message.answer(
            "These values look invalid. Check ranges:\n"
            "• Calories: 1000-10000\n"
            "• Protein: 0-500 g\n"
            "• Fat: 0-500 g\n"
            "• Carbs: 0-1000 g\n\n"
            "Try again: 2000, 150, 65, 200"
        )
        return
    
    await state.update_data(
        target_calories=target_calories,
        target_protein_g=target_protein_g,
        target_fat_g=target_fat_g,
        target_carbs_g=target_carbs_g,
    )
    
    # Сохраняем данные в backend
    data = await state.get_data()
    telegram_id = message.from_user.id
    
    result = await update_user(
        telegram_id,
        goal_type=data.get("goal_type"),
        gender=data.get("gender"),
        age=data.get("age"),
        height_cm=data.get("height_cm"),
        weight_kg=data.get("weight_kg"),
        activity_level=data.get("activity_level"),
        target_calories=target_calories,
        target_protein_g=target_protein_g,
        target_fat_g=target_fat_g,
        target_carbs_g=target_carbs_g,
    )
    
    if not result:
        await message.answer(tr("onboarding.save_error", LANG))
        return
    
    # Переходим к выбору часового пояса
    await message.answer(
        tr("onboarding.timezone_prompt", LANG),
        reply_markup=get_timezone_keyboard()
    )
    await state.set_state(OnboardingStates.waiting_for_timezone)


@router.callback_query(F.data.startswith("tz:"))
async def on_timezone_selected(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора часового пояса"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    tz_value = callback.data.split(":", 1)[1]
    
    if tz_value == "other":
        await callback.message.answer(
            tr("onboarding.timezone_other", LANG)
        )
        await state.set_state(OnboardingStates.waiting_for_timezone_text)
        return
    
    # Save timezone
    telegram_id = callback.from_user.id
    await update_user(telegram_id, timezone=tz_value)
    
    # Переходим к туториалу
    await callback.message.answer(
        TUTORIAL_STEP1_TEXT,
        reply_markup=get_tutorial_next_keyboard()
    )
    await state.set_state(OnboardingStates.tutorial_step_1)


@router.message(OnboardingStates.waiting_for_timezone_text)
async def on_timezone_text_received(message: types.Message, state: FSMContext) -> None:
    """Обработка ручного ввода часового пояса"""
    import pytz
    tz_text = message.text.strip()
    
    try:
        pytz.timezone(tz_text)
    except pytz.exceptions.UnknownTimeZoneError:
        await message.answer(
            tr("onboarding.timezone_invalid", LANG, tz=tz_text)
        )
        return
    
    telegram_id = message.from_user.id
    await update_user(telegram_id, timezone=tz_text)
    
    await message.answer(
        TUTORIAL_STEP1_TEXT,
        reply_markup=get_tutorial_next_keyboard()
    )
    await state.set_state(OnboardingStates.tutorial_step_1)


@router.callback_query(F.data == "tutorial_next")
async def on_tutorial_step2(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Переход ко второму шагу туториала"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    await callback.message.answer(
        TUTORIAL_STEP2_TEXT,
        reply_markup=get_tutorial_finish_keyboard()
    )
    await state.set_state(OnboardingStates.tutorial_step_2)


@router.callback_query(F.data == "tutorial_finish")
async def on_tutorial_finish(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Завершение туториала и онбординга"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    telegram_id = callback.from_user.id
    
    # Отмечаем онбординг как завершённый
    await update_user(telegram_id, onboarding_completed=True)

    # Auto-start free trial
    await start_trial(telegram_id)
    
    await callback.message.answer(
        FINAL_TEXT + "\n\n" + tr("onboarding.trial_activated", LANG),
        reply_markup=get_main_menu_keyboard()
    )
    await state.clear()


# ============ Menu Button Handlers ============

@router.message(F.text == "📊 Today")
async def on_menu_today(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Сегодня'"""
    await state.clear()
    
    if not await check_onboarding_completed(message):
        return
    if not await check_billing_access(message):
        return
    
    telegram_id = message.from_user.id
    
    user = await get_user(telegram_id)
    if not user:
        await message.answer("Could not find your profile. Try /start")
        return
    
    today = date_type.today()
    day_summary = await get_day_summary(user["id"], today)
    
    # Целевые значения
    target_cal = user.get("target_calories") or 2000
    target_prot = user.get("target_protein_g") or 150
    target_fat = user.get("target_fat_g") or 65
    target_carbs = user.get("target_carbs_g") or 200
    
    if day_summary:
        current_cal = day_summary.get("total_calories", 0)
        current_prot = day_summary.get("total_protein_g", 0)
        current_fat = day_summary.get("total_fat_g", 0)
        current_carbs = day_summary.get("total_carbs_g", 0)
    else:
        current_cal = current_prot = current_fat = current_carbs = 0
    
    # Прогресс-бары
    bar_cal = build_progress_bar(current_cal, target_cal)
    bar_prot = build_progress_bar(current_prot, target_prot)
    bar_fat = build_progress_bar(current_fat, target_fat)
    bar_carbs = build_progress_bar(current_carbs, target_carbs)
    
    # Остаток в читаемом формате
    rem_cal = format_remaining(current_cal, target_cal, "kcal")
    rem_prot = format_remaining(current_prot, target_prot, "g")
    rem_fat = format_remaining(current_fat, target_fat, "g")
    rem_carbs = format_remaining(current_carbs, target_carbs, "g")
    
    # Число приёмов пищи
    meals_count = len(day_summary.get("meals", [])) if day_summary else 0
    
    text = f"""📊 Today, {today.strftime('%d.%m.%Y')}

Calories: {current_cal:.0f} / {target_cal:.0f} kcal
{bar_cal}
<i>{rem_cal}</i>

Protein: {current_prot:.0f} / {target_prot:.0f} g
{bar_prot}
<i>{rem_prot}</i>

Fat: {current_fat:.0f} / {target_fat:.0f} g
{bar_fat}
<i>{rem_fat}</i>

Carbs: {current_carbs:.0f} / {target_carbs:.0f} g
{bar_carbs}
<i>{rem_carbs}</i>

Meals logged: {meals_count}"""
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_day_actions_keyboard(today.isoformat(), from_today=True))


@router.message(F.text == "📈 Week")
async def on_menu_week(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Неделя'"""
    await state.clear()
    
    if not await check_onboarding_completed(message):
        return
    if not await check_billing_access(message):
        return
    
    telegram_id = message.from_user.id
    
    user = await get_user(telegram_id)
    if not user:
        await message.answer("Could not find your profile. Try /start")
        return
    
    # Целевые значения
    target_cal = user.get("target_calories") or 2000
    target_prot = user.get("target_protein_g") or 150
    target_fat = user.get("target_fat_g") or 65
    target_carbs = user.get("target_carbs_g") or 200
    
    today = date_type.today()
    week_data = []
    total_cal = 0
    total_prot = 0
    total_fat = 0
    total_carbs = 0
    days_with_data = 0
    
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    for i in range(7):
        day = today - timedelta(days=6-i)
        day_summary = await get_day_summary(user["id"], day)
        
        day_name = day_names[day.weekday()]
        marker = "📍" if day == today else "  "
        
        if day_summary:
            cal = day_summary.get("total_calories", 0)
            prot = day_summary.get("total_protein_g", 0)
            fat = day_summary.get("total_fat_g", 0)
            carbs = day_summary.get("total_carbs_g", 0)
            total_cal += cal
            total_prot += prot
            total_fat += fat
            total_carbs += carbs
            if cal > 0:
                days_with_data += 1
            
            if cal == 0:
                status = "⚪"
                week_data.append(f"{marker}{status} {day_name} {day.day:02d}.{day.month:02d}: —")
            else:
                pct = cal / target_cal * 100 if target_cal > 0 else 0
                status = "🟢" if cal <= target_cal else "🟡"
                week_data.append(f"{marker}{status} {day_name} {day.day:02d}.{day.month:02d}: {cal:.0f} kcal ({pct:.0f}%)")
        else:
            week_data.append(f"{marker}⚪ {day_name} {day.day:02d}.{day.month:02d}: —")
    
    avg_cal = total_cal / max(days_with_data, 1)
    avg_prot = total_prot / max(days_with_data, 1)
    avg_fat = total_fat / max(days_with_data, 1)
    avg_carbs = total_carbs / max(days_with_data, 1)
    
    legend = "🟢 within target · 🟡 over target"

    text = f"""📈 Weekly stats

{chr(10).join(week_data)}

{legend}

Daily average ({days_with_data} days):
• Calories: {avg_cal:.0f} / {target_cal:.0f} kcal
• Protein: {avg_prot:.0f} / {target_prot:.0f} g
• Fat: {avg_fat:.0f} / {target_fat:.0f} g
• Carbs: {avg_carbs:.0f} / {target_carbs:.0f} g

Tap a day to view details:"""
    
    await message.answer(text, reply_markup=get_week_days_keyboard())


@router.message(F.text == "🍽 My Menu")
async def on_menu_my_meals(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Моё меню'"""
    await state.clear()

    if not await check_onboarding_completed(message):
        return
    if not await check_billing_access(message):
        return

    tg_id = message.from_user.id
    data = await get_saved_meals(tg_id, page=1, per_page=20)

    if not data or not data.get("items"):
        await message.answer(
            "🍽 Your menu is empty for now.\n\n"
            "You can save any meal - just tap "
            "\"💾 Save to My Menu\" after logging."
        )
        return

    meals = data["items"]
    total = data["total"]
    page = data["page"]
    per_page = data["per_page"]

    rows = []
    for m in meals:
        name = m.get("name", "Meal")
        cal = round(m.get("total_calories", 0))
        label = f"✅ {name} ({cal} kcal)"
        if len(label) > 50:
            label = f"✅ {name[:40]}… ({cal})"
        rows.append([InlineKeyboardButton(
            text=label, callback_data=f"my_menu_log:{m['id']}"
        )])

    total_pages = max(1, (total + per_page - 1) // per_page)
    if total_pages > 1:
        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton(text="← Back", callback_data=f"my_menu_page:{page - 1}"))
        if page < total_pages:
            nav.append(InlineKeyboardButton(text="Next →", callback_data=f"my_menu_page:{page + 1}"))
        if nav:
            rows.append(nav)

    rows.append([InlineKeyboardButton(
        text="⚙️ Edit My Menu", callback_data="my_menu_edit"
    )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(
        "🍽 My Menu\n\n"
        "Tap a meal to log it instantly:",
        reply_markup=keyboard,
    )


@router.message(F.text == "🤔 What should I eat?")
async def on_menu_advice(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Что съесть?' -- входит в режим food advice на один запрос."""
    await state.clear()

    if not await check_onboarding_completed(message):
        return
    if not await check_billing_access(message):
        return

    telegram_id = message.from_user.id

    user = await get_user(telegram_id)
    if not user:
        await message.answer("Could not find your profile. Try /start")
        return

    today = date_type.today()
    day_summary = await get_day_summary(user["id"], today)

    target_cal = user.get("target_calories") or 2000
    target_prot = user.get("target_protein_g") or 150
    target_fat = user.get("target_fat_g") or 65
    target_carbs = user.get("target_carbs_g") or 200

    if day_summary:
        current_cal = day_summary.get("total_calories", 0)
        current_prot = day_summary.get("total_protein_g", 0)
        current_fat = day_summary.get("total_fat_g", 0)
        current_carbs = day_summary.get("total_carbs_g", 0)
    else:
        current_cal = current_prot = current_fat = current_carbs = 0

    remaining_cal = max(0, target_cal - current_cal)
    remaining_prot = max(0, target_prot - current_prot)
    remaining_fat = max(0, target_fat - current_fat)
    remaining_carbs = max(0, target_carbs - current_carbs)

    nutrition_context = json.dumps({
        "target_calories": target_cal,
        "target_protein_g": target_prot,
        "target_fat_g": target_fat,
        "target_carbs_g": target_carbs,
        "eaten_calories": current_cal,
        "eaten_protein_g": current_prot,
        "eaten_fat_g": current_fat,
        "eaten_carbs_g": current_carbs,
        "remaining_calories": remaining_cal,
        "remaining_protein_g": remaining_prot,
        "remaining_fat_g": remaining_fat,
        "remaining_carbs_g": remaining_carbs,
    }, ensure_ascii=False)

    await state.update_data(nutrition_context=nutrition_context)
    await state.set_state(FoodAdviceState.waiting_for_input)

    prompt = (
        f"🤔 What should I eat?\n\n"
        f"📊 Remaining today:\n"
        f"• 🔥 {remaining_cal:.0f} kcal\n"
        f"• 🥩 {remaining_prot:.0f} g protein\n"
        f"• 🥑 {remaining_fat:.0f} g fat\n"
        f"• 🍞 {remaining_carbs:.0f} g carbs\n\n"
        f"Send options from a menu (text, photo, or voice), "
        f"and I'll suggest the best pick!"
    )
    await message.answer(prompt)


@router.message(F.text == "👤 Profile")
async def on_menu_profile(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Профиль'"""
    await state.clear()
    
    if not await check_onboarding_completed(message):
        return
    
    telegram_id = message.from_user.id
    
    user = await get_user(telegram_id)
    if not user:
        await message.answer("Could not find your profile. Try /start")
        return
    
    goal_names = {
        "lose": "🔻 Lose weight",
        "maintain": "⚖️ Maintain weight",
        "gain": "💪 Gain muscle",
    }
    
    gender_names = {
        "male": "👨 Male",
        "female": "👩 Female",
    }
    
    activity_names = {
        "sedentary": "🛋 Minimal",
        "light": "🚶 Light",
        "moderate": "🏃 Moderate",
        "high": "🏋️ High",
        "very_high": "⚡ Very high",
    }
    
    goal = goal_names.get(user.get("goal_type"), "Not set")
    gender = gender_names.get(user.get("gender"), "Not set")
    activity = activity_names.get(user.get("activity_level"), "Not set")
    
    age = user.get("age") or "—"
    height = user.get("height_cm") or "—"
    weight = user.get("weight_kg") or "—"
    
    target_cal = user.get("target_calories") or 2000
    target_prot = user.get("target_protein_g") or 150
    target_fat = user.get("target_fat_g") or 65
    target_carbs = user.get("target_carbs_g") or 200
    
    billing = await get_billing_status(telegram_id)
    billing_section = ""
    if billing:
        status = billing.get("access_status", "new")
        if status == "trial":
            days_left = billing.get("trial_days_remaining", 0)
            billing_section = f"\n\n⭐ Subscription: trial ({days_left:.0f} days left)"
        elif status == "active":
            ends = billing.get("subscription_ends_at", "")
            if isinstance(ends, str) and ends:
                try:
                    from datetime import datetime as _dt
                    dt = _dt.fromisoformat(ends.replace("Z", "+00:00"))
                    ends_str = dt.strftime("%d.%m.%Y")
                except ValueError:
                    ends_str = ends
            else:
                ends_str = "—"
            billing_section = f"\n\n⭐ Subscription: active (until {ends_str})"
        elif status == "trial_expired":
            billing_section = "\n\n⭐ Subscription: trial ended\nTap /subscribe to activate"
        elif status == "expired":
            billing_section = "\n\n⭐ Subscription: expired\nTap /subscribe to renew"
        else:
            billing_section = "\n\n⭐ Subscription: none\nTap /subscribe to activate"

    text = f"""👤 Your profile

📋 Data:
• Sex: {gender}
• Age: {age}
• Height: {height} cm
• Weight: {weight} kg
• Activity: {activity}

🎯 Goal: {goal}

📊 Daily targets:
• 🔥 Calories: {target_cal:.0f} kcal
• 🥩 Protein: {target_prot:.0f} g
• 🥑 Fat: {target_fat:.0f} g
• 🍞 Carbs: {target_carbs:.0f} g{billing_section}"""
    
    await message.answer(text, reply_markup=get_profile_keyboard())


@router.callback_query(F.data == "profile_recalculate")
async def on_profile_recalculate(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Пересчитать КБЖУ по формуле"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Запускаем онбординг заново
    await callback.message.answer(GOAL_TEXT, reply_markup=get_goal_keyboard())
    await state.set_state(OnboardingStates.waiting_for_goal)


@router.callback_query(F.data == "profile_manage_sub")
async def on_profile_manage_sub(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show subscription status and management options."""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    telegram_id = callback.from_user.id
    billing = await get_billing_status(telegram_id)
    if not billing:
        await callback.message.answer("Could not load subscription info. Please try again later.")
        return

    status = billing.get("access_status", "new")

    if status == "trial":
        days_left = billing.get("trial_days_remaining", 0)
        text = (
            "💳 <b>Subscription status</b>\n\n"
            f"You are on a <b>free trial</b> — {days_left:.0f} days remaining.\n\n"
            "When your trial ends, subscribe to keep full access."
        )
        await callback.message.answer(text, parse_mode="HTML")
        return

    if status not in ("active",):
        text = (
            "💳 <b>Subscription status</b>\n\n"
            "You don't have an active subscription.\n"
            "Tap /subscribe to choose a plan."
        )
        await callback.message.answer(text, parse_mode="HTML")
        return

    provider = billing.get("subscription_provider", "")
    plan_id = billing.get("subscription_plan_id", "")
    auto_renew = billing.get("subscription_auto_renew")
    ends_at = billing.get("subscription_ends_at", "")

    ends_str = "—"
    if isinstance(ends_at, str) and ends_at:
        try:
            from datetime import datetime as _dt
            dt = _dt.fromisoformat(ends_at.replace("Z", "+00:00"))
            ends_str = dt.strftime("%d.%m.%Y")
        except ValueError:
            ends_str = ends_at

    plan_label = {"monthly": "Monthly", "yearly": "Yearly"}.get(plan_id, plan_id or "—")
    renew_label = "auto-renew" if auto_renew else "expires"

    text = (
        "💳 <b>Subscription status</b>\n\n"
        f"Plan: <b>{plan_label}</b>\n"
        f"Status: <b>active</b> ({renew_label})\n"
        f"Valid until: <b>{ends_str}</b>\n"
    )

    buttons = []

    if provider == "paddle":
        portal = await get_paddle_portal_url(telegram_id)
        if portal:
            update_url = portal.get("update_payment_method_url")
            if update_url:
                buttons.append([InlineKeyboardButton(
                    text="💳 Update payment method", url=update_url,
                )])
        buttons.append([InlineKeyboardButton(
            text="❌ Cancel subscription", callback_data="cancel_sub_start",
        )])
        text += "\nPayment method: card (Paddle)"
    elif provider == "telegram":
        buttons.append([InlineKeyboardButton(
            text="❌ Cancel subscription", callback_data="cancel_sub_start",
        )])
        text += "\nPayment method: Telegram Stars"
    elif provider == "gumroad":
        buttons.append([InlineKeyboardButton(
            text="❌ Cancel subscription", callback_data="cancel_sub_start",
        )])
        text += "\nPayment method: card (Gumroad)"

    if buttons:
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await callback.message.answer(text, parse_mode="HTML")


# ============ Cancel Subscription Flow (Churn Survey) ============

CHURN_REASONS = [
    ("too_expensive", "💰 Too expensive"),
    ("not_using", "📉 I don't use it enough"),
    ("not_accurate", "🎯 Data isn't accurate enough"),
    ("manual_effort", "⏱ Still too much manual effort"),
    ("found_alternative", "🔄 Switched to another app"),
    ("goal_reached", "🏆 I reached my goal"),
    ("temporary", "⏸ Just pausing, will come back"),
    ("other", "💬 Other reason"),
]


def _get_churn_reason_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"churn:{reason_id}")]
        for reason_id, label in CHURN_REASONS
    ]
    buttons.append([InlineKeyboardButton(
        text="↩️ Never mind, keep my subscription",
        callback_data="churn:nevermind",
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "cancel_sub_start")
async def on_cancel_sub_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start the churn survey before cancellation."""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    await callback.message.answer(
        "Before you go — could you tell us why you're cancelling?\n\n"
        "Your feedback helps us improve YumYummy for everyone.",
        reply_markup=_get_churn_reason_keyboard(),
    )
    await state.set_state(CancelFlowStates.waiting_for_reason)


@router.callback_query(CancelFlowStates.waiting_for_reason, F.data == "churn:nevermind")
async def on_churn_nevermind(callback: types.CallbackQuery, state: FSMContext) -> None:
    """User decided not to cancel."""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.clear()
    await callback.message.answer(
        "Great, your subscription stays active! 💪\n"
        "Tell me what you ate, and I'll log it.",
    )


@router.callback_query(CancelFlowStates.waiting_for_reason, F.data.startswith("churn:"))
async def on_churn_reason_selected(callback: types.CallbackQuery, state: FSMContext) -> None:
    """User selected a cancellation reason."""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    reason = callback.data.split(":", 1)[1]
    await state.update_data(churn_reason=reason)

    reason_labels = dict(CHURN_REASONS)
    label = reason_labels.get(reason, reason)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Skip", callback_data="churn_comment:skip")],
    ])
    await callback.message.answer(
        f"Got it: <i>{label}</i>\n\n"
        "Anything else you'd like to share? Type a message below, "
        "or tap <b>Skip</b> to proceed.",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await state.set_state(CancelFlowStates.waiting_for_comment)


@router.callback_query(CancelFlowStates.waiting_for_comment, F.data == "churn_comment:skip")
async def on_churn_comment_skip(callback: types.CallbackQuery, state: FSMContext) -> None:
    """User skipped the free-text comment."""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _finish_churn_survey(callback.from_user.id, state, callback.message)


@router.message(CancelFlowStates.waiting_for_comment)
async def on_churn_comment_received(message: types.Message, state: FSMContext) -> None:
    """User typed a free-text comment."""
    comment = message.text.strip()[:1000] if message.text else None
    await state.update_data(churn_comment=comment)
    await _finish_churn_survey(message.from_user.id, state, message)


async def _finish_churn_survey(
    telegram_id: int,
    state: FSMContext,
    message: types.Message,
) -> None:
    """Save the survey and show the actual cancel link."""
    data = await state.get_data()
    reason = data.get("churn_reason", "other")
    comment = data.get("churn_comment")
    await state.clear()

    await submit_churn_survey(telegram_id, reason, comment)

    billing = await get_billing_status(telegram_id)
    provider = (billing or {}).get("subscription_provider", "")

    buttons = []
    extra_text = ""

    if provider == "paddle":
        portal = await get_paddle_portal_url(telegram_id)
        if portal and portal.get("cancel_url"):
            buttons.append([InlineKeyboardButton(
                text="→ Cancel subscription on Paddle",
                url=portal["cancel_url"],
            )])
        else:
            extra_text = (
                "\nTo cancel, check the receipt email from Paddle "
                "or contact @nik_kur."
            )
    elif provider == "telegram":
        extra_text = (
            "\nTo cancel, go to Telegram Settings → My Stars → "
            "Subscriptions → YumYummy."
        )
    else:
        extra_text = "\nContact @nik_kur and we'll cancel it for you."

    text = (
        "Thank you for your feedback! 🙏\n\n"
        "Tap below to proceed with cancellation."
        + extra_text
    )

    if buttons:
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer(text, reply_markup=kb)
    else:
        await message.answer(text)


@router.callback_query(F.data == "profile_manual_kbju")
async def on_profile_manual_kbju(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Ручной ввод КБЖУ из профиля"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    await state.clear()
    
    await callback.message.answer(MANUAL_KBJU_TEXT)
    await state.set_state(ProfileStates.waiting_for_manual_kbju)


@router.message(ProfileStates.waiting_for_manual_kbju)
async def on_profile_manual_kbju_received(message: types.Message, state: FSMContext) -> None:
    """Обработка ручного ввода КБЖУ из профиля"""
    text = message.text.strip()
    numbers = re.findall(r"[\d.]+", text)
    
    if len(numbers) < 4:
        await message.answer(
            "Couldn't parse your data. Please send it in this format:\n"
            "Calories, Protein (g), Fat (g), Carbs (g)\n\n"
            "Example: 2000, 150, 65, 200"
        )
        return
    
    try:
        target_calories = float(numbers[0])
        target_protein_g = float(numbers[1])
        target_fat_g = float(numbers[2])
        target_carbs_g = float(numbers[3])
        
        # Валидация
        if target_calories < 1000 or target_calories > 10000:
            raise ValueError("Invalid calories")
        if target_protein_g < 0 or target_protein_g > 500:
            raise ValueError("Invalid protein")
        if target_fat_g < 0 or target_fat_g > 500:
            raise ValueError("Invalid fat")
        if target_carbs_g < 0 or target_carbs_g > 1000:
            raise ValueError("Invalid carbs")
            
    except (ValueError, IndexError):
        await message.answer(
            "These values look invalid. Check ranges:\n"
            "• Calories: 1000-10000\n"
            "• Protein: 0-500 g\n"
            "• Fat: 0-500 g\n"
            "• Carbs: 0-1000 g\n\n"
            "Try again: 2000, 150, 65, 200"
        )
        return
    
    telegram_id = message.from_user.id
    
    # Сохраняем данные в backend
    result = await update_user(
        telegram_id,
        target_calories=target_calories,
        target_protein_g=target_protein_g,
        target_fat_g=target_fat_g,
        target_carbs_g=target_carbs_g,
    )
    
    if not result:
        await message.answer(tr("onboarding.save_error", LANG))
        return
    
    await message.answer(
        f"✅ Targets updated!\n\n"
        f"🔥 Calories: {target_calories:.0f} kcal\n"
        f"🥩 Protein: {target_protein_g:.0f} g\n"
        f"🥑 Fat: {target_fat_g:.0f} g\n"
        f"🍞 Carbs: {target_carbs_g:.0f} g",
        reply_markup=get_main_menu_keyboard()
    )
    
    await state.clear()


@router.message(F.text == "📤 Export")
async def on_menu_export(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Экспорт'"""
    await state.clear()
    
    if not await check_onboarding_completed(message):
        return
    if not await check_billing_access(message):
        return
    
    telegram_id = message.from_user.id
    
    user = await get_user(telegram_id)
    if not user:
        await message.answer("Could not find your profile. Try /start")
        return
    
    export_url = await get_user_export_url(telegram_id)
    
    text = f"""📤 Data export

You can download all your nutrition logs as CSV.

This file opens in Excel, Google Sheets, or Numbers.

🔗 Download link:
{export_url}

The link works only for your data."""
    
    await message.answer(text, reply_markup=get_main_menu_keyboard())


@router.message(F.text == "💬 Support")
async def on_menu_support(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Поддержка'"""
    await state.clear()
    
    text = f"""💬 Support

If you have any questions, issues, or ideas - message me directly!

👤 Telegram: @{SUPPORT_USERNAME}

I'll do my best to reply as soon as possible 🙌"""
    
    await message.answer(text, reply_markup=get_main_menu_keyboard())
