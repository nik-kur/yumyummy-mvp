"""
Модуль онбординга и главного меню для Telegram бота.
Содержит FSM состояния, обработчики и клавиатуры.
"""
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
    agent_run_workflow,
)

logger = logging.getLogger(__name__)

router = Router()

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
    tutorial_step_1 = State()
    tutorial_step_2 = State()


class ProfileStates(StatesGroup):
    """Состояния для редактирования профиля"""
    waiting_for_manual_kbju = State()


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

WELCOME_TEXT = """👋 Привет! Я — YumYummy.

Забудь про ручной подсчёт калорий, взвешивание и бесконечные таблицы.

Просто скажи или напиши, что ты съел — всё остальное сделаю я.

🎯 Что меня отличает:

⚡ Максимально удобно
Текст, голос или фото штрих-кода — логируй еду мгновенно

🧠 Понимаю тебя как настоящий нутрициолог
"поел борща с хлебом" и "капучино в Старбаксе" — одинаково хорошо

🎯 Точные данные
Ищу официальную информацию по ресторанам и продуктам в интернете

🤖 Персональный советник
Подскажу, что лучше съесть прямо сейчас, чтобы не выйти за рамки твоих целей

Давай настроим всё под тебя — это ~30 секунд."""

GOAL_TEXT = """Какая у тебя главная цель?"""

GENDER_TEXT = """Укажи пол (для точного расчёта метаболизма):"""

PARAMS_TEXT = """Отправь свои данные в формате:
Возраст, Рост (см), Вес (кг)

Например: 28, 175, 72"""

ACTIVITY_TEXT = """Уровень физической активности:"""

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
→ Поищу в меню ресторана

Без контекста? Не проблема — посчитаю по средним значениям.

📷 ШТРИХ-КОД:
Для упакованных продуктов — просто сфотографируй штрих-код на упаковке. Я найду продукт в базе данных."""

TUTORIAL_STEP2_TEXT = """🤔 УМНЫЙ СОВЕТ — ЧТО СЪЕСТЬ?

Не знаешь, что выбрать? Спроси — я помогу подобрать лучший вариант под твои оставшиеся калории и БЖУ.

Примеры:
• "Я в Макдональдс, что лучше заказать?"
• "Хочу перекусить, осталось 300 ккал"
• "Что приготовить на ужин? Нужен белок"

Нажми [🤔 Что съесть?] в меню или просто спроси!

📊 СЛЕДИ ЗА ПРОГРЕССОМ

[📊 Сегодня] — что съел, сколько осталось
[📈 Неделя] — статистика за 7 дней

Заглядывай перед едой — так проще планировать!"""

FINAL_TEXT = """🎉 Готово!

Краткая памятка:
📝 Пиши или говори что съел
📷 Штрих-код → точные данные
🏪 Укажи место → найду официальные данные
🤔 Что съесть? → умный совет
📊 Сегодня / 📈 Неделя → твой прогресс

🚀 Попробуй прямо сейчас!
Напиши, что ты ел сегодня на завтрак.

Удачи! 💪"""

MANUAL_KBJU_TEXT = """✏️ Введи свои цели КБЖУ в формате:
Калории, Белки (г), Жиры (г), Углеводы (г)

Например: 2000, 150, 65, 200"""


# ============ Keyboards ============

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню с 5 кнопками"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Сегодня"), KeyboardButton(text="📈 Неделя")],
            [KeyboardButton(text="🤔 Что съесть?"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="📤 Экспорт"), KeyboardButton(text="💬 Поддержка")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напиши что съел или выбери действие...",
    )


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Кнопка начала онбординга"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать", callback_data="onboarding_start")]
        ]
    )


def get_goal_keyboard() -> InlineKeyboardMarkup:
    """Выбор цели"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔻 Похудеть", callback_data="goal_lose")],
            [InlineKeyboardButton(text="⚖️ Поддерживать вес", callback_data="goal_maintain")],
            [InlineKeyboardButton(text="💪 Набрать массу", callback_data="goal_gain")],
        ]
    )


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Выбор пола"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👨 Мужской", callback_data="gender_male"),
                InlineKeyboardButton(text="👩 Женский", callback_data="gender_female"),
            ]
        ]
    )


def get_activity_keyboard() -> InlineKeyboardMarkup:
    """Выбор уровня активности"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛋 Минимальная — сидячая работа", callback_data="activity_sedentary")],
            [InlineKeyboardButton(text="🚶 Лёгкая — 1-2 тренировки/нед", callback_data="activity_light")],
            [InlineKeyboardButton(text="🏃 Средняя — 3-4 тренировки/нед", callback_data="activity_moderate")],
            [InlineKeyboardButton(text="🏋️ Высокая — 5-6 тренировок/нед", callback_data="activity_high")],
            [InlineKeyboardButton(text="⚡ Очень высокая — ежедневные", callback_data="activity_very_high")],
        ]
    )


def get_goal_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение целей КБЖУ"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отлично, продолжить", callback_data="goals_confirm")],
            [InlineKeyboardButton(text="✏️ Ввести свои цели вручную", callback_data="goals_manual")],
        ]
    )


def get_tutorial_next_keyboard() -> InlineKeyboardMarkup:
    """Кнопка продолжения туториала"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👍 Понятно, дальше", callback_data="tutorial_next")]
        ]
    )


def get_tutorial_finish_keyboard() -> InlineKeyboardMarkup:
    """Кнопка завершения туториала"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👍 Всё понятно!", callback_data="tutorial_finish")]
        ]
    )


def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для профиля"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Пересчитать КБЖУ", callback_data="profile_recalculate")],
            [InlineKeyboardButton(text="✏️ Ввести цели вручную", callback_data="profile_manual_kbju")],
        ]
    )


def get_day_actions_keyboard(day_str: str) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра приёмов пищи за день"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🍽 Посмотреть приёмы пищи", callback_data=f"daylist:{day_str}")]
        ]
    )


def get_week_days_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с днями недели для drill-down"""
    today = date_type.today()
    buttons = []
    
    day_names = {
        0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"
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
    return f"""🎯 Твои персональные цели готовы!

🔥 Калории:   {target_calories:.0f} ккал
🥩 Белки:     {target_protein_g:.0f} г
🥑 Жиры:      {target_fat_g:.0f} г
🍞 Углеводы:  {target_carbs_g:.0f} г

📐 Как это рассчитано?

Я использовал формулу Миффлина-Сан Жеора — золотой стандарт в диетологии, который применяют профессиональные нутрициологи по всему миру.

Эта формула учитывает:
• Твой базовый метаболизм (сколько калорий тратит тело в покое)
• Уровень активности
• Твою цель (дефицит/профицит калорий)

Результат — научно обоснованный план питания, а не случайные цифры из интернета.

Ты всегда можешь скорректировать цели в "Профиле"."""


async def check_onboarding_completed(message: types.Message) -> bool:
    """Проверяет, прошёл ли пользователь онбординг"""
    user = await get_user(message.from_user.id)
    if not user or not user.get("onboarding_completed", False):
        await message.answer(
            "Сначала нужно пройти настройку! Нажми /start",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return False
    return True


def build_progress_bar(current: float, target: float, width: int = 10) -> str:
    """Строит прогресс-бар"""
    if target <= 0:
        return "░" * width
    
    ratio = min(current / target, 1.5)  # Максимум 150%
    filled = int(ratio * width)
    filled = min(filled, width + 5)  # Не больше 15 символов
    
    if ratio <= 1.0:
        bar = "█" * filled + "░" * (width - filled)
    else:
        # Превышение — красный индикатор
        bar = "█" * width + "🔴" * (filled - width)
    
    return bar


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
        if age < 14 or age > 100:
            raise ValueError("Возраст должен быть от 14 до 100 лет")
        if height_cm < 100 or height_cm > 250:
            raise ValueError("Рост должен быть от 100 до 250 см")
        if weight_kg < 30 or weight_kg > 300:
            raise ValueError("Вес должен быть от 30 до 300 кг")
            
    except (ValueError, IndexError) as e:
        await message.answer(
            f"Данные выглядят некорректно. Проверь значения:\n"
            f"• Возраст: 14-100 лет\n"
            f"• Рост: 100-250 см\n"
            f"• Вес: 30-300 кг\n\n"
            f"Попробуй ещё раз: 28, 175, 72"
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
        await callback.message.answer("Произошла ошибка при сохранении. Попробуй ещё раз позже.")
        return
    
    # Переходим к туториалу
    await callback.message.answer(
        TUTORIAL_STEP1_TEXT,
        reply_markup=get_tutorial_next_keyboard()
    )
    await state.set_state(OnboardingStates.tutorial_step_1)


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
        await message.answer("Произошла ошибка при сохранении. Попробуй ещё раз позже.")
        return
    
    # Переходим к туториалу
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
    
    await callback.message.answer(
        FINAL_TEXT,
        reply_markup=get_main_menu_keyboard()
    )
    await state.clear()


# ============ Menu Button Handlers ============

@router.message(F.text == "📊 Сегодня")
async def on_menu_today(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Сегодня'"""
    await state.clear()
    
    if not await check_onboarding_completed(message):
        return
    
    telegram_id = message.from_user.id
    
    user = await get_user(telegram_id)
    if not user:
        await message.answer("Не удалось найти твой профиль. Попробуй /start")
        return
    
    today = date_type.today()
    day_summary = await get_day_summary(user["id"], today.isoformat())
    
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
    
    # Остаток
    remaining_cal = target_cal - current_cal
    remaining_prot = target_prot - current_prot
    remaining_fat = target_fat - current_fat
    remaining_carbs = target_carbs - current_carbs
    
    # Прогресс-бары
    bar_cal = build_progress_bar(current_cal, target_cal)
    bar_prot = build_progress_bar(current_prot, target_prot)
    bar_fat = build_progress_bar(current_fat, target_fat)
    bar_carbs = build_progress_bar(current_carbs, target_carbs)
    
    text = f"""📊 Сегодня, {today.strftime('%d.%m.%Y')}

🔥 Калории: {current_cal:.0f} / {target_cal:.0f} ккал
{bar_cal} ({remaining_cal:+.0f})

🥩 Белки: {current_prot:.0f} / {target_prot:.0f} г
{bar_prot} ({remaining_prot:+.0f})

🥑 Жиры: {current_fat:.0f} / {target_fat:.0f} г
{bar_fat} ({remaining_fat:+.0f})

🍞 Углеводы: {current_carbs:.0f} / {target_carbs:.0f} г
{bar_carbs} ({remaining_carbs:+.0f})"""
    
    await message.answer(text, reply_markup=get_day_actions_keyboard(today.isoformat()))


@router.message(F.text == "📈 Неделя")
async def on_menu_week(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Неделя'"""
    await state.clear()
    
    if not await check_onboarding_completed(message):
        return
    
    telegram_id = message.from_user.id
    
    user = await get_user(telegram_id)
    if not user:
        await message.answer("Не удалось найти твой профиль. Попробуй /start")
        return
    
    # Целевые значения
    target_cal = user.get("target_calories") or 2000
    target_prot = user.get("target_protein_g") or 150
    
    today = date_type.today()
    week_data = []
    total_cal = 0
    total_prot = 0
    days_with_data = 0
    
    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    
    for i in range(7):
        day = today - timedelta(days=6-i)
        day_summary = await get_day_summary(user["id"], day.isoformat())
        
        if day_summary:
            cal = day_summary.get("total_calories", 0)
            prot = day_summary.get("total_protein_g", 0)
            total_cal += cal
            total_prot += prot
            if cal > 0:
                days_with_data += 1
            
            # Эмодзи статуса
            if cal == 0:
                status = "⚪"
            elif cal < target_cal * 0.9:
                status = "🟡"  # Недобор
            elif cal > target_cal * 1.1:
                status = "🔴"  # Перебор
            else:
                status = "🟢"  # В норме
            
            day_name = day_names[day.weekday()]
            marker = "📍" if day == today else ""
            week_data.append(f"{marker}{status} {day_name} {day.day:02d}.{day.month:02d}: {cal:.0f} ккал")
        else:
            day_name = day_names[day.weekday()]
            marker = "📍" if day == today else ""
            week_data.append(f"{marker}⚪ {day_name} {day.day:02d}.{day.month:02d}: —")
    
    avg_cal = total_cal / max(days_with_data, 1)
    avg_prot = total_prot / max(days_with_data, 1)
    
    text = f"""📈 Статистика за неделю

{chr(10).join(week_data)}

📊 Средние показатели:
• Калории: {avg_cal:.0f} / {target_cal:.0f} ккал
• Белки: {avg_prot:.0f} / {target_prot:.0f} г

Нажми на день, чтобы посмотреть детали:"""
    
    await message.answer(text, reply_markup=get_week_days_keyboard())


@router.message(F.text == "🤔 Что съесть?")
async def on_menu_advice(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Что съесть?'"""
    await state.clear()
    
    if not await check_onboarding_completed(message):
        return
    
    telegram_id = message.from_user.id
    
    user = await get_user(telegram_id)
    if not user:
        await message.answer("Не удалось найти твой профиль. Попробуй /start")
        return
    
    today = date_type.today()
    day_summary = await get_day_summary(user["id"], today.isoformat())
    
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
    
    remaining_cal = max(0, target_cal - current_cal)
    remaining_prot = max(0, target_prot - current_prot)
    remaining_fat = max(0, target_fat - current_fat)
    remaining_carbs = max(0, target_carbs - current_carbs)
    
    # Формируем запрос к AI
    thinking_msg = await message.answer("🤔 Думаю, что тебе посоветовать...")
    
    advice_prompt = f"Посоветуй что съесть. Осталось: {remaining_cal:.0f} ккал, {remaining_prot:.0f}г белка, {remaining_fat:.0f}г жиров, {remaining_carbs:.0f}г углеводов."
    
    result = await agent_run_workflow(
        user_id=user["id"],
        date_str=today.isoformat(),
        text=advice_prompt,
    )
    
    await thinking_msg.delete()
    
    if result and result.get("message_text"):
        advice_text = result["message_text"]
    else:
        advice_text = """Вот несколько идей:

• Если нужен белок — курица, рыба, творог, яйца
• Мало углеводов — каша, цельнозерновой хлеб, фрукты
• Нужны жиры — орехи, авокадо, оливковое масло
• Легкий перекус — овощи, йогурт, протеиновый батончик

Напиши конкретнее — где ты и какие есть варианты, и я помогу выбрать лучший!"""
    
    header = f"""🤔 Что съесть?

📊 Осталось на сегодня:
• 🔥 {remaining_cal:.0f} ккал
• 🥩 {remaining_prot:.0f} г белка
• 🥑 {remaining_fat:.0f} г жиров
• 🍞 {remaining_carbs:.0f} г углеводов

💡 Мой совет:

"""
    
    await message.answer(header + advice_text, reply_markup=get_main_menu_keyboard())


@router.message(F.text == "👤 Профиль")
async def on_menu_profile(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Профиль'"""
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
    
    age = user.get("age") or "—"
    height = user.get("height_cm") or "—"
    weight = user.get("weight_kg") or "—"
    
    target_cal = user.get("target_calories") or 2000
    target_prot = user.get("target_protein_g") or 150
    target_fat = user.get("target_fat_g") or 65
    target_carbs = user.get("target_carbs_g") or 200
    
    text = f"""👤 Твой профиль

📋 Данные:
• Пол: {gender}
• Возраст: {age}
• Рост: {height} см
• Вес: {weight} кг
• Активность: {activity}

🎯 Цель: {goal}

📊 Дневные цели КБЖУ:
• 🔥 Калории: {target_cal:.0f} ккал
• 🥩 Белок: {target_prot:.0f} г
• 🥑 Жиры: {target_fat:.0f} г
• 🍞 Углеводы: {target_carbs:.0f} г"""
    
    await message.answer(text, reply_markup=get_profile_keyboard())


@router.callback_query(F.data == "profile_recalculate")
async def on_profile_recalculate(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Пересчитать КБЖУ по формуле"""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Запускаем онбординг заново
    await callback.message.answer(GOAL_TEXT, reply_markup=get_goal_keyboard())
    await state.set_state(OnboardingStates.waiting_for_goal)


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
    await state.clear()
    
    if not await check_onboarding_completed(message):
        return
    
    telegram_id = message.from_user.id
    
    user = await get_user(telegram_id)
    if not user:
        await message.answer("Не удалось найти твой профиль. Попробуй /start")
        return
    
    export_url = await get_user_export_url(telegram_id)
    
    text = f"""📤 Экспорт данных

Ты можешь скачать все свои записи о питании в формате CSV.

Этот файл откроется в Excel, Google Sheets или Numbers.

🔗 Ссылка для скачивания:
{export_url}

Ссылка работает только для твоих данных."""
    
    await message.answer(text, reply_markup=get_main_menu_keyboard())


@router.message(F.text == "💬 Поддержка")
async def on_menu_support(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Поддержка'"""
    await state.clear()
    
    text = f"""💬 Поддержка

Если у тебя возникли вопросы, проблемы или предложения — напиши мне напрямую!

👤 Telegram: @{SUPPORT_USERNAME}

Постараюсь ответить как можно скорее 🙌"""
    
    await message.answer(text, reply_markup=get_main_menu_keyboard())
