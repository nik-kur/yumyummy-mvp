"""
Онбординг и обработчики меню для YumYummy бота.
"""
import logging
import re
from datetime import date as date_type, timedelta
from typing import Optional

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

from app.bot.api_client import (
    ensure_user,
    get_user,
    update_user,
    get_day_summary,
    get_user_export_url,
)

logger = logging.getLogger(__name__)

router = Router()

# Константа для поддержки
SUPPORT_USERNAME = "nik_kur"


# ============ FSM States ============

class OnboardingStates(StatesGroup):
    waiting_for_goal = State()
    waiting_for_gender = State()
    waiting_for_params = State()
    waiting_for_activity = State()
    waiting_for_goal_confirmation = State()
    waiting_for_manual_kbju = State()  # Новое состояние для ручного ввода КБЖУ


class ProfileStates(StatesGroup):
    waiting_for_manual_kbju = State()  # Для ручного ввода из профиля


# ============ Константы ============

ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "high": 1.725,
    "very_high": 1.9,
}

GOAL_ADJUSTMENTS = {
    "lose": -500,      # дефицит калорий
    "maintain": 0,     # поддержание
    "gain": 300,       # профицит
}


# ============ Клавиатуры ============

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Основная клавиатура меню"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Сегодня"),
                KeyboardButton(text="📈 Неделя"),
            ],
            [
                KeyboardButton(text="🤔 Что съесть?"),
                KeyboardButton(text="👤 Профиль"),
            ],
            [
                KeyboardButton(text="📤 Экспорт"),
                KeyboardButton(text="💬 Поддержка"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напиши что съел или выбери действие...",
    )


def get_goal_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора цели"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔻 Похудеть", callback_data="goal_lose")],
            [InlineKeyboardButton(text="⚖️ Поддерживать вес", callback_data="goal_maintain")],
            [InlineKeyboardButton(text="💪 Набрать массу", callback_data="goal_gain")],
        ]
    )


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора пола"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👨 Мужской", callback_data="gender_male"),
                InlineKeyboardButton(text="👩 Женский", callback_data="gender_female"),
            ]
        ]
    )


def get_activity_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора активности"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛋 Минимальная — сидячая работа, без спорта", callback_data="activity_sedentary")],
            [InlineKeyboardButton(text="🚶 Лёгкая — прогулки, 1-2 тренировки/неделю", callback_data="activity_light")],
            [InlineKeyboardButton(text="🏃 Средняя — 3-4 тренировки/неделю", callback_data="activity_moderate")],
            [InlineKeyboardButton(text="🏋️ Высокая — 5-6 тренировок/неделю", callback_data="activity_high")],
            [InlineKeyboardButton(text="⚡ Очень высокая — ежедневные интенсивные", callback_data="activity_very_high")],
        ]
    )


def get_goal_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения целей"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отлично, продолжить", callback_data="goals_confirm")],
            [InlineKeyboardButton(text="✏️ Ввести свои цели вручную", callback_data="goals_manual")],
        ]
    )


def get_tutorial_next_keyboard(step: int) -> InlineKeyboardMarkup:
    """Клавиатура для перехода к следующему шагу туториала"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👍 Понятно, дальше", callback_data=f"tutorial_{step}")],
        ]
    )


def get_tutorial_finish_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура завершения туториала"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👍 Всё понятно!", callback_data="tutorial_finish")],
        ]
    )


def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура профиля с кнопками изменения целей"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Пересчитать по формуле Миффлина", callback_data="profile_recalculate")],
            [InlineKeyboardButton(text="✏️ Ввести цели вручную", callback_data="profile_manual_kbju")],
        ]
    )


def get_day_actions_keyboard(day_str: str) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра приёмов пищи за день (использует формат run_bot.py)"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🍽 Посмотреть приёмы пищи", 
                callback_data=f"daylist:{day_str}"
            )]
        ]
    )


def get_week_days_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с днями недели для просмотра (использует формат run_bot.py)"""
    today = date_type.today()
    buttons = []
    for i in range(7):
        day = today - timedelta(days=i)
        day_label = day.strftime("%d.%m")
        buttons.append([
            InlineKeyboardButton(text=f"📅 {day_label}", callback_data=f"daylist:{day.isoformat()}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============ Расчёт КБЖУ ============

def calculate_bmr(gender: str, weight_kg: float, height_cm: int, age: int) -> float:
    """
    Расчёт базового метаболизма по формуле Миффлина-Сан Жеора.
    """
    if gender == "male":
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161


def calculate_tdee(bmr: float, activity_level: str) -> float:
    """
    Расчёт суточного расхода калорий с учётом активности.
    """
    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, 1.55)
    return bmr * multiplier


def calculate_targets(
    gender: str, 
    weight_kg: float, 
    height_cm: int, 
    age: int, 
    activity_level: str, 
    goal_type: str
) -> dict:
    """
    Расчёт целевых значений КБЖУ.
    """
    bmr = calculate_bmr(gender, weight_kg, height_cm, age)
    tdee = calculate_tdee(bmr, activity_level)
    
    # Корректировка по цели
    adjustment = GOAL_ADJUSTMENTS.get(goal_type, 0)
    target_calories = max(1200, tdee + adjustment)  # минимум 1200 ккал
    
    # Расчёт макросов
    # Белок: 1.6-2.2 г/кг (больше при похудении)
    protein_per_kg = 2.0 if goal_type == "lose" else 1.8
    target_protein = weight_kg * protein_per_kg
    
    # Жиры: 25-30% от калорий
    fat_calories = target_calories * 0.25
    target_fat = fat_calories / 9  # 9 ккал на грамм жира
    
    # Углеводы: остаток
    protein_calories = target_protein * 4  # 4 ккал на грамм белка
    carbs_calories = target_calories - protein_calories - fat_calories
    target_carbs = carbs_calories / 4  # 4 ккал на грамм углеводов
    
    return {
        "target_calories": round(target_calories),
        "target_protein_g": round(target_protein),
        "target_fat_g": round(target_fat),
        "target_carbs_g": round(target_carbs),
    }


# ============ Тексты онбординга ============

WELCOME_TEXT = """👋 Привет! Я — YumYummy.

Забудь про ручной подсчёт калорий, взвешивание и бесконечные таблицы.

Просто скажи или напиши, что ты съел — всё остальное сделаю я.

🎯 Что меня отличает:

⚡ Максимально удобно
Текст, голос или фото штрих-кода — логируй еду так, как тебе комфортно

🧠 Понимаю тебя как настоящий нутрициолог
"Поел борща с хлебом" и "капучино в Старбаксе" — я пойму одинаково хорошо

🎯 Точные данные
Ищу официальную информацию по ресторанам и продуктам в интернете

🤖 Персональный советник
Подскажу, что лучше съесть прямо сейчас, чтобы не выйти за рамки твоих целей

Давай настроим всё под тебя — это ~30 секунд."""

GOAL_TEXT = "Какая у тебя главная цель?"

GENDER_TEXT = "Укажи пол (для точного расчёта метаболизма):"

PARAMS_TEXT = """Отправь свои данные в формате:
Возраст, Рост (см), Вес (кг)

Например: 28, 175, 72"""

ACTIVITY_TEXT = "Уровень физической активности:"

MANUAL_KBJU_TEXT = """✏️ Введи свои цели КБЖУ в формате:
Калории, Белки (г), Жиры (г), Углеводы (г)

Например: 2000, 150, 65, 200"""


def get_targets_presentation_text(targets: dict, goal_type: str) -> str:
    """Текст презентации рассчитанных целей"""
    goal_names = {
        "lose": "похудения",
        "maintain": "поддержания веса",
        "gain": "набора массы",
    }
    goal_name = goal_names.get(goal_type, "")
    
    return f"""🎯 Твои персональные цели готовы!

🔥 Калории: {targets['target_calories']} ккал
🥩 Белки: {targets['target_protein_g']} г
🥑 Жиры: {targets['target_fat_g']} г
🍞 Углеводы: {targets['target_carbs_g']} г

📐 Как это рассчитано?

Я использовал формулу Миффлина-Сан Жеора — золотой стандарт в диетологии, который применяют профессиональные нутрициологи по всему миру.

Эта формула учитывает:
• Твой базовый метаболизм (сколько калорий тратит тело в покое)
• Уровень активности
• Твою цель ({goal_name})

Результат — научно обоснованный план питания, а не случайные цифры из интернета."""


TUTORIAL_STEP1_TEXT = """📝 КАК ЗАПИСЫВАТЬ ЕДУ

Главное правило: пиши или говори своими словами. Я пойму.

✍️ ТЕКСТОМ:
"Съел 2 яйца и тост с авокадо"
"Овсянка с бананом и ложкой мёда"
"Салат цезарь и стейк 200г"

🎤 ГОЛОСОМ:
Запиши голосовое: "На завтрак съел творог с ягодами и выпил кофе с молоком"

🏪 С КОНТЕКСТОМ (для точности):
Если укажешь, где ты это купил или заказал — я поищу официальные данные в интернете:

"Капучино и круассан в Starbucks"
→ Найду точные калории из официального меню

"Творог Epica 6% из Вкусвилла"
→ Найду данные производителя

"Том ям в Тануки"
→ Поищу в меню ресторана или на сайтах доставки

Без контекста? Не проблема — посчитаю по средним значениям.

📷 ШТРИХ-КОД:
Для упакованных продуктов — просто сфотографируй штрих-код на упаковке. Я найду продукт в базе данных и запишу точные значения."""


TUTORIAL_STEP2_TEXT = """🤔 УМНЫЙ СОВЕТ — ЧТО СЪЕСТЬ?

Не знаешь, что выбрать? Спроси — я помогу подобрать лучший вариант под твои оставшиеся калории и БЖУ.

Примеры:
• "Я в Макдональдс, что лучше заказать?"
• "Хочу перекусить, осталось 300 ккал"
• "Что приготовить на ужин? Нужен белок"

Нажми 🤔 Что съесть? в меню или просто спроси!

📊 СЛЕДИ ЗА ПРОГРЕССОМ

📊 Сегодня — что съел, сколько осталось
📈 Неделя — статистика за 7 дней

Заглядывай перед едой — так проще планировать!"""


TUTORIAL_FINISH_TEXT = """🎉 Готово!

Краткая памятка:
📝 Пиши или говори что съел
📷 Штрих-код → точные данные
🏪 Укажи место → найду официальные данные
🤔 Что съесть? → умный совет
📊 Сегодня / 📈 Неделя → твой прогресс

🚀 Попробуй прямо сейчас!
Напиши, что ты ел сегодня на завтрак.

Удачи! 💪"""


# ============ Обработчики онбординга ============

async def start_onboarding(message: types.Message, state: FSMContext) -> None:
    """Начать онбординг"""
    await state.clear()
    
    # Отправляем приветствие
    start_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать", callback_data="onboarding_start")],
        ]
    )
    await message.answer(WELCOME_TEXT, reply_markup=start_keyboard)


@router.callback_query(F.data == "onboarding_start")
async def on_onboarding_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Начало онбординга — выбор цели"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    await callback.message.answer(GOAL_TEXT, reply_markup=get_goal_keyboard())
    await state.set_state(OnboardingStates.waiting_for_goal)


@router.callback_query(F.data.startswith("goal_"), OnboardingStates.waiting_for_goal)
async def on_goal_selected(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора цели"""
    await callback.answer()
    
    goal_type = callback.data.replace("goal_", "")
    await state.update_data(goal_type=goal_type)
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(GENDER_TEXT, reply_markup=get_gender_keyboard())
    await state.set_state(OnboardingStates.waiting_for_gender)


@router.callback_query(F.data.startswith("gender_"), OnboardingStates.waiting_for_gender)
async def on_gender_selected(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора пола"""
    await callback.answer()
    
    gender = callback.data.replace("gender_", "")
    await state.update_data(gender=gender)
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(PARAMS_TEXT)
    await state.set_state(OnboardingStates.waiting_for_params)


@router.message(OnboardingStates.waiting_for_params)
async def on_params_received(message: types.Message, state: FSMContext) -> None:
    """Обработка параметров (возраст, рост, вес)"""
    text = message.text.strip()
    
    # Парсим параметры
    # Поддерживаем форматы: "28, 175, 72" или "28 175 72"
    numbers = re.findall(r"[\d.]+", text)
    
    if len(numbers) < 3:
        await message.answer(
            "Не удалось разобрать данные. Пожалуйста, отправь в формате:\n"
            "Возраст, Рост (см), Вес (кг)\n\n"
            "Например: 28, 175, 72"
        )
        return
    
    try:
        age = int(float(numbers[0]))
        height_cm = int(float(numbers[1]))
        weight_kg = float(numbers[2])
        
        # Валидация
        if age < 10 or age > 120:
            raise ValueError("Некорректный возраст")
        if height_cm < 100 or height_cm > 250:
            raise ValueError("Некорректный рост")
        if weight_kg < 30 or weight_kg > 300:
            raise ValueError("Некорректный вес")
            
    except (ValueError, IndexError) as e:
        await message.answer(
            "Данные выглядят некорректно. Проверь значения:\n"
            "• Возраст: 10-120 лет\n"
            "• Рост: 100-250 см\n"
            "• Вес: 30-300 кг\n\n"
            "Попробуй ещё раз: 28, 175, 72"
        )
        return
    
    await state.update_data(age=age, height_cm=height_cm, weight_kg=weight_kg)
    
    await message.answer(ACTIVITY_TEXT, reply_markup=get_activity_keyboard())
    await state.set_state(OnboardingStates.waiting_for_activity)


@router.callback_query(F.data.startswith("activity_"), OnboardingStates.waiting_for_activity)
async def on_activity_selected(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора активности и расчёт целей"""
    await callback.answer()
    
    activity_level = callback.data.replace("activity_", "")
    await state.update_data(activity_level=activity_level)
    
    # Получаем все данные
    data = await state.get_data()
    
    # Рассчитываем цели
    targets = calculate_targets(
        gender=data["gender"],
        weight_kg=data["weight_kg"],
        height_cm=data["height_cm"],
        age=data["age"],
        activity_level=activity_level,
        goal_type=data["goal_type"],
    )
    
    await state.update_data(**targets)
    
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Показываем результаты
    text = get_targets_presentation_text(targets, data["goal_type"])
    await callback.message.answer(text, reply_markup=get_goal_confirmation_keyboard())
    await state.set_state(OnboardingStates.waiting_for_goal_confirmation)


@router.callback_query(F.data == "goals_confirm", OnboardingStates.waiting_for_goal_confirmation)
async def on_goals_confirmed(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Подтверждение целей — сохраняем и показываем туториал"""
    await callback.answer()
    
    data = await state.get_data()
    telegram_id = callback.from_user.id
    
    # Сохраняем данные в backend
    result = await update_user(
        telegram_id,
        goal_type=data.get("goal_type"),
        gender=data.get("gender"),
        age=data.get("age"),
        height_cm=data.get("height_cm"),
        weight_kg=data.get("weight_kg"),
        activity_level=data.get("activity_level"),
        target_calories=data["target_calories"],
        target_protein_g=data["target_protein_g"],
        target_fat_g=data["target_fat_g"],
        target_carbs_g=data["target_carbs_g"],
    )
    
    if not result:
        await callback.message.answer(
            "Произошла ошибка при сохранении. Попробуй ещё раз позже."
        )
        return
    
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Показываем первый шаг туториала
    await callback.message.answer(
        TUTORIAL_STEP1_TEXT, 
        reply_markup=get_tutorial_next_keyboard(2)
    )


@router.callback_query(F.data == "goals_manual", OnboardingStates.waiting_for_goal_confirmation)
async def on_goals_manual(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Ручной ввод КБЖУ целей"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    await callback.message.answer(MANUAL_KBJU_TEXT)
    await state.set_state(OnboardingStates.waiting_for_manual_kbju)


@router.message(OnboardingStates.waiting_for_manual_kbju)
async def on_manual_kbju_received(message: types.Message, state: FSMContext) -> None:
    """Обработка ручного ввода КБЖУ"""
    text = message.text.strip()
    numbers = re.findall(r"[\d.]+", text)
    
    if len(numbers) < 4:
        await message.answer(
            "Не удалось разобрать данные. Пожалуйста, отправь в формате:\n"
            "Калории, Белки (г), Жиры (г), Углеводы (г)\n\n"
            "Например: 2000, 150, 65, 200"
        )
        return
    
    try:
        target_calories = float(numbers[0])
        target_protein_g = float(numbers[1])
        target_fat_g = float(numbers[2])
        target_carbs_g = float(numbers[3])
        
        # Валидация
        if target_calories < 1000 or target_calories > 10000:
            raise ValueError("Некорректные калории")
        if target_protein_g < 0 or target_protein_g > 500:
            raise ValueError("Некорректные белки")
        if target_fat_g < 0 or target_fat_g > 500:
            raise ValueError("Некорректные жиры")
        if target_carbs_g < 0 or target_carbs_g > 1000:
            raise ValueError("Некорректные углеводы")
            
    except (ValueError, IndexError):
        await message.answer(
            "Данные выглядят некорректно. Проверь значения:\n"
            "• Калории: 1000-10000\n"
            "• Белки: 0-500 г\n"
            "• Жиры: 0-500 г\n"
            "• Углеводы: 0-1000 г\n\n"
            "Попробуй ещё раз: 2000, 150, 65, 200"
        )
        return
    
    telegram_id = message.from_user.id
    data = await state.get_data()
    
    # Сохраняем данные в backend
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
        await message.answer("Произошла ошибка при сохранении. Попробуй ещё раз позже.")
        return
    
    await message.answer(
        f"✅ Цели сохранены!\n\n"
        f"🔥 Калории: {target_calories:.0f} ккал\n"
        f"🥩 Белки: {target_protein_g:.0f} г\n"
        f"🥑 Жиры: {target_fat_g:.0f} г\n"
        f"🍞 Углеводы: {target_carbs_g:.0f} г"
    )
    
    # Показываем первый шаг туториала
    await message.answer(
        TUTORIAL_STEP1_TEXT, 
        reply_markup=get_tutorial_next_keyboard(2)
    )


@router.callback_query(F.data == "tutorial_2")
async def on_tutorial_step2(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Второй шаг туториала"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    await callback.message.answer(
        TUTORIAL_STEP2_TEXT, 
        reply_markup=get_tutorial_finish_keyboard()
    )


@router.callback_query(F.data == "tutorial_finish")
async def on_tutorial_finish(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Завершение туториала"""
    await callback.answer()
    
    telegram_id = callback.from_user.id
    
    # Отмечаем онбординг как завершённый
    await update_user(telegram_id, onboarding_completed=True)
    
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Показываем финальное сообщение с основной клавиатурой
    await callback.message.answer(
        TUTORIAL_FINISH_TEXT, 
        reply_markup=get_main_menu_keyboard()
    )
    
    await state.clear()


# ============ Проверка онбординга ============

async def check_onboarding_completed(message: types.Message) -> bool:
    """Проверяет, завершён ли онбординг. Если нет — предлагает пройти."""
    telegram_id = message.from_user.id
    user = await get_user(telegram_id)
    
    if not user:
        await message.answer(
            "Похоже, ты ещё не зарегистрирован. Нажми /start чтобы начать!"
        )
        return False
    
    if not user.get("onboarding_completed", False):
        await message.answer(
            "Сначала давай настроим твои цели! 🎯\n"
            "Нажми /start чтобы пройти быструю настройку (~30 сек)."
        )
        return False
    
    return True


# ============ Обработчики меню ============

@router.message(F.text == "📊 Сегодня")
async def on_menu_today(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Сегодня'"""
    # Сбрасываем любое предыдущее состояние
    await state.clear()
    
    if not await check_onboarding_completed(message):
        return
    
    telegram_id = message.from_user.id
    
    # Получаем данные пользователя
    user = await get_user(telegram_id)
    if not user:
        await message.answer("Не удалось найти твой профиль. Попробуй /start")
        return
    
    today = date_type.today()
    summary = await get_day_summary(user["id"], today)
    
    # Форматируем ответ
    meals = []
    if not summary:
        total_cal = 0
        total_prot = 0
        total_fat = 0
        total_carbs = 0
        meals_text = "Пока пусто. Напиши, что ты съел!"
    else:
        total_cal = summary.get("total_calories", 0)
        total_prot = summary.get("total_protein_g", 0)
        total_fat = summary.get("total_fat_g", 0)
        total_carbs = summary.get("total_carbs_g", 0)
        
        meals = summary.get("meals", [])
        if meals:
            meals_lines = []
            for m in meals:
                time_str = m.get("eaten_at", "")[:16].split("T")[1] if "T" in m.get("eaten_at", "") else ""
                meals_lines.append(f"• {time_str} {m.get('description_user', '')} — {m.get('calories', 0):.0f} ккал")
            meals_text = "\n".join(meals_lines)
        else:
            meals_text = "Пока пусто. Напиши, что ты съел!"
    
    # Цели пользователя
    target_cal = user.get("target_calories") or 2000
    target_prot = user.get("target_protein_g") or 150
    target_fat = user.get("target_fat_g") or 65
    target_carbs = user.get("target_carbs_g") or 200
    
    # Прогресс-бары
    def progress_bar(current, target, width=20):
        if target <= 0:
            return "░" * width
        pct = min(current / target, 1.0)
        filled = int(pct * width)
        return "█" * filled + "░" * (width - filled)
    
    cal_pct = int(min(total_cal / target_cal * 100, 100)) if target_cal > 0 else 0
    prot_pct = int(min(total_prot / target_prot * 100, 100)) if target_prot > 0 else 0
    fat_pct = int(min(total_fat / target_fat * 100, 100)) if target_fat > 0 else 0
    carbs_pct = int(min(total_carbs / target_carbs * 100, 100)) if target_carbs > 0 else 0
    
    text = f"""📊 Сегодня ({today.strftime('%d.%m')})

🔥 Калории: {total_cal:.0f} / {target_cal:.0f} ккал
[{progress_bar(total_cal, target_cal)}] {cal_pct}%

🥩 Белок: {total_prot:.0f} / {target_prot:.0f} г
[{progress_bar(total_prot, target_prot)}] {prot_pct}%

🥑 Жиры: {total_fat:.0f} / {target_fat:.0f} г
[{progress_bar(total_fat, target_fat)}] {fat_pct}%

🍞 Углеводы: {total_carbs:.0f} / {target_carbs:.0f} г
[{progress_bar(total_carbs, target_carbs)}] {carbs_pct}%

📋 Приёмы пищи:
{meals_text}"""
    
    # Добавляем кнопку для просмотра/редактирования приёмов пищи
    keyboard = get_day_actions_keyboard(today.isoformat()) if meals else None
    await message.answer(text, reply_markup=keyboard)


@router.message(F.text == "📈 Неделя")
async def on_menu_week(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Неделя'"""
    # Сбрасываем любое предыдущее состояние
    await state.clear()
    
    if not await check_onboarding_completed(message):
        return
    
    telegram_id = message.from_user.id
    
    user = await get_user(telegram_id)
    if not user:
        await message.answer("Не удалось найти твой профиль. Попробуй /start")
        return
    
    today = date_type.today()
    
    # Собираем данные за 7 дней
    days_data = []
    total_cal = 0
    total_prot = 0
    total_fat = 0
    total_carbs = 0
    days_with_data = 0
    
    for i in range(7):
        day = today - timedelta(days=i)
        summary = await get_day_summary(user["id"], day)
        
        if summary:
            cal = summary.get("total_calories", 0)
            prot = summary.get("total_protein_g", 0)
            fat = summary.get("total_fat_g", 0)
            carbs = summary.get("total_carbs_g", 0)
            
            total_cal += cal
            total_prot += prot
            total_fat += fat
            total_carbs += carbs
            days_with_data += 1
            
            days_data.append(f"• {day.strftime('%d.%m')} — {cal:.0f} ккал")
        else:
            days_data.append(f"• {day.strftime('%d.%m')} — нет данных")
    
    # Средние значения
    if days_with_data > 0:
        avg_cal = total_cal / days_with_data
        avg_prot = total_prot / days_with_data
        avg_fat = total_fat / days_with_data
        avg_carbs = total_carbs / days_with_data
    else:
        avg_cal = avg_prot = avg_fat = avg_carbs = 0
    
    target_cal = user.get("target_calories") or 2000
    
    text = f"""📈 Статистика за 7 дней

📊 Всего за неделю:
• 🔥 Калории: {total_cal:.0f} ккал
• 🥩 Белок: {total_prot:.0f} г
• 🥑 Жиры: {total_fat:.0f} г
• 🍞 Углеводы: {total_carbs:.0f} г

📉 В среднем за день:
• 🔥 {avg_cal:.0f} ккал (цель: {target_cal:.0f})
• 🥩 {avg_prot:.0f} г белка
• 🥑 {avg_fat:.0f} г жиров
• 🍞 {avg_carbs:.0f} г углеводов

📅 По дням (нажми для деталей):
{chr(10).join(days_data)}"""
    
    # Используем кнопки в формате run_bot.py (daylist:YYYY-MM-DD)
    await message.answer(text, reply_markup=get_week_days_keyboard())


@router.message(F.text == "🤔 Что съесть?")
async def on_menu_advice(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Что съесть?'"""
    # Сбрасываем любое предыдущее состояние
    await state.clear()
    
    if not await check_onboarding_completed(message):
        return
    
    telegram_id = message.from_user.id
    
    user = await get_user(telegram_id)
    if not user:
        await message.answer("Не удалось найти твой профиль. Попробуй /start")
        return
    
    today = date_type.today()
    summary = await get_day_summary(user["id"], today)
    
    # Считаем остаток
    if summary:
        eaten_cal = summary.get("total_calories", 0)
        eaten_prot = summary.get("total_protein_g", 0)
        eaten_fat = summary.get("total_fat_g", 0)
        eaten_carbs = summary.get("total_carbs_g", 0)
    else:
        eaten_cal = eaten_prot = eaten_fat = eaten_carbs = 0
    
    target_cal = user.get("target_calories") or 2000
    target_prot = user.get("target_protein_g") or 150
    target_fat = user.get("target_fat_g") or 65
    target_carbs = user.get("target_carbs_g") or 200
    
    remaining_cal = max(0, target_cal - eaten_cal)
    remaining_prot = max(0, target_prot - eaten_prot)
    remaining_fat = max(0, target_fat - eaten_fat)
    remaining_carbs = max(0, target_carbs - eaten_carbs)
    
    text = f"""🤔 Помогу выбрать, что съесть!

📊 Твой остаток на сегодня:
• 🔥 {remaining_cal:.0f} ккал
• 🥩 {remaining_prot:.0f} г белка
• 🥑 {remaining_fat:.0f} г жиров
• 🍞 {remaining_carbs:.0f} г углеводов

Напиши мне:
• Где ты сейчас (ресторан, кафе, дом)
• Какие варианты рассматриваешь
• Или просто спроси "что приготовить на ужин?"

Примеры:
• "Я в Макдональдс, что взять?"
• "Хочу заказать пиццу, какую лучше?"
• "Что перекусить на 300 ккал?"

Я подскажу лучший вариант под твои цели! 🎯"""
    
    await message.answer(text)


@router.message(F.text == "👤 Профиль")
async def on_menu_profile(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Профиль'"""
    # Сбрасываем любое предыдущее состояние
    await state.clear()
    
    if not await check_onboarding_completed(message):
        return
    
    telegram_id = message.from_user.id
    
    user = await get_user(telegram_id)
    if not user:
        await message.answer("Не удалось найти твой профиль. Попробуй /start")
        return
    
    goal_names = {
        "lose": "🔻 Похудеть",
        "maintain": "⚖️ Поддерживать вес",
        "gain": "💪 Набрать массу",
    }
    
    gender_names = {
        "male": "👨 Мужской",
        "female": "👩 Женский",
    }
    
    activity_names = {
        "sedentary": "🛋 Минимальная",
        "light": "🚶 Лёгкая",
        "moderate": "🏃 Средняя",
        "high": "🏋️ Высокая",
        "very_high": "⚡ Очень высокая",
    }
    
    goal = goal_names.get(user.get("goal_type"), "Не указана")
    gender = gender_names.get(user.get("gender"), "Не указан")
    activity = activity_names.get(user.get("activity_level"), "Не указана")
    
    text = f"""👤 Твой профиль

📋 Данные:
• Пол: {gender}
• Возраст: {user.get('age') or 'Не указан'}
• Рост: {user.get('height_cm') or 'Не указан'} см
• Вес: {user.get('weight_kg') or 'Не указан'} кг
• Активность: {activity}

🎯 Цель: {goal}

📊 Дневные цели КБЖУ:
• 🔥 Калории: {user.get('target_calories') or 'Не установлено'} ккал
• 🥩 Белок: {user.get('target_protein_g') or 'Не установлено'} г
• 🥑 Жиры: {user.get('target_fat_g') or 'Не установлено'} г
• 🍞 Углеводы: {user.get('target_carbs_g') or 'Не установлено'} г"""
    
    await message.answer(text, reply_markup=get_profile_keyboard())


@router.callback_query(F.data == "profile_recalculate")
async def on_profile_recalculate(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Пересчёт КБЖУ по формуле"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    await callback.message.answer(
        "Давай пересчитаем твои цели по формуле Миффлина-Сан Жеора.\n\n"
        "Выбери свою цель:",
        reply_markup=get_goal_keyboard()
    )
    await state.set_state(OnboardingStates.waiting_for_goal)


@router.callback_query(F.data == "profile_manual_kbju")
async def on_profile_manual_kbju(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Ручной ввод КБЖУ из профиля"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Сбрасываем любое предыдущее состояние перед установкой нового
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
            "Не удалось разобрать данные. Пожалуйста, отправь в формате:\n"
            "Калории, Белки (г), Жиры (г), Углеводы (г)\n\n"
            "Например: 2000, 150, 65, 200"
        )
        return
    
    try:
        target_calories = float(numbers[0])
        target_protein_g = float(numbers[1])
        target_fat_g = float(numbers[2])
        target_carbs_g = float(numbers[3])
        
        # Валидация
        if target_calories < 1000 or target_calories > 10000:
            raise ValueError("Некорректные калории")
        if target_protein_g < 0 or target_protein_g > 500:
            raise ValueError("Некорректные белки")
        if target_fat_g < 0 or target_fat_g > 500:
            raise ValueError("Некорректные жиры")
        if target_carbs_g < 0 or target_carbs_g > 1000:
            raise ValueError("Некорректные углеводы")
            
    except (ValueError, IndexError):
        await message.answer(
            "Данные выглядят некорректно. Проверь значения:\n"
            "• Калории: 1000-10000\n"
            "• Белки: 0-500 г\n"
            "• Жиры: 0-500 г\n"
            "• Углеводы: 0-1000 г\n\n"
            "Попробуй ещё раз: 2000, 150, 65, 200"
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
        await message.answer("Произошла ошибка при сохранении. Попробуй ещё раз позже.")
        return
    
    await message.answer(
        f"✅ Цели обновлены!\n\n"
        f"🔥 Калории: {target_calories:.0f} ккал\n"
        f"🥩 Белки: {target_protein_g:.0f} г\n"
        f"🥑 Жиры: {target_fat_g:.0f} г\n"
        f"🍞 Углеводы: {target_carbs_g:.0f} г",
        reply_markup=get_main_menu_keyboard()
    )
    
    await state.clear()


@router.message(F.text == "📤 Экспорт")
async def on_menu_export(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Экспорт'"""
    # Сбрасываем любое предыдущее состояние
    await state.clear()
    
    telegram_id = message.from_user.id
    
    user = await get_user(telegram_id)
    if not user:
        await message.answer("Не удалось найти твой профиль. Попробуй /start")
        return
    
    export_url = await get_user_export_url(telegram_id)
    
    text = f"""📤 Экспорт данных

Твои данные о питании можно скачать в формате CSV.

CSV файл содержит:
• Дата и время
• Описание еды
• Калории, белки, жиры, углеводы
• Уровень точности данных

📥 Скачать: {export_url}

💡 CSV открывается в Excel, Google Sheets и других таблицах."""
    
    await message.answer(text)


@router.message(F.text == "💬 Поддержка")
async def on_menu_support(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Поддержка'"""
    # Сбрасываем любое предыдущее состояние
    await state.clear()
    text = f"""💬 Поддержка

Если у тебя возникли вопросы, проблемы или предложения — напиши мне напрямую!

👤 Telegram: @{SUPPORT_USERNAME}

Буду рад помочь! 🙌"""
    
    await message.answer(text)
