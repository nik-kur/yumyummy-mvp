from __future__ import annotations

from typing import Any

DEFAULT_LANG = "en"


MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "onboarding.welcome": """👋 Hi! I'm YumYummy.

Forget manual calorie counting, kitchen scales, and endless spreadsheets.

Just tell me what you ate - I'll do the rest.

🎯 What makes me different:

⚡ Super convenient
Text, voice, or barcode photo - log food instantly

🧠 I understand you like a real nutrition coach
"had borscht with bread" and "a cappuccino at Starbucks" - both work great

🎯 Accurate data
I search official nutrition data for restaurants and products online

🤖 Personal advisor
I'll suggest what to eat right now so you stay within your goals

Let's set everything up for you - takes ~30 seconds.""",
        "onboarding.goal": "What's your main goal?",
        "onboarding.gender": "Select your sex (for accurate metabolism calculation):",
        "onboarding.params": "Send your data in this format:\nAge, Height (cm), Weight (kg)\n\nExample: 28, 175, 72",
        "onboarding.activity": "Your physical activity level:",
        "onboarding.manual_kbju": "✏️ Enter your daily targets in this format:\nCalories, Protein (g), Fat (g), Carbs (g)\n\nExample: 2000, 150, 65, 200",
        "onboarding.timezone_prompt": "🌍 Choose your time zone:",
        "onboarding.timezone_other": "Enter your IANA time zone, for example:\nAsia/Dubai, Asia/Tokyo, Europe/Paris, America/Los_Angeles\n\nFull list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
        "onboarding.timezone_invalid": "Could not recognize time zone '{tz}'. Try again, e.g. Asia/Dubai or Europe/Paris",
        "onboarding.save_error": "Something went wrong while saving. Please try again later.",
        "onboarding.start_needed": "Please complete setup first. Tap /start",
        "onboarding.final": """🎉 Done!

Quick reminder:
📝 Type or say what you ate
📷 Barcode -> precise product data
🏪 Add place/brand -> official data search
🤔 What should I eat? -> smart recommendation
📊 Today / 📈 Week -> your progress

🚀 Try it now!
Tell me what you had for breakfast today.

Good luck! 💪""",
        "onboarding.trial_activated": "🎉 3-day trial activated!",
        "billing.paywall_trial": "🎉 <b>Try YumYummy for free!</b>\n\n3 days of full access - no payment required.\nAfter trial, pick the plan that fits you best.\n\n{plans_text}",
        "billing.paywall_trial_expired": "⏰ <b>Your trial has ended</b>\n\nTo keep using YumYummy, choose a subscription:\n\n{plans_text}",
        "billing.paywall_sub_expired": "⏰ <b>Your subscription has ended</b>\n\nRenew your plan to continue:\n\n{plans_text}",
        "billing.stars_info": "⭐ <b>Pay with Telegram Stars</b>\n\n{stars_plans_text}\n\n<i>These are subscription prices for YumYummy, not the cost of buying Stars themselves. The actual amount you pay for Stars may be higher due to App Store / Google Play and Telegram fees. Please double-check the price before purchasing Stars.</i>",
        "billing.show_stars_btn": "⭐ Pay with Telegram Stars",
        "billing.gumroad_check_hint": "💳 After completing your payment, tap the button below to activate your subscription.",
        "billing.plan_monthly_suffix": "Stars/mo",
        "billing.plan_once_suffix": "Stars/year",
        "billing.start_trial_btn": "🆓 Start 3-day free trial",
        "billing.activate_trial_error": "Could not activate trial. Please try again later.",
        "billing.trial_already": "You already have an active trial until {ends_str}.\nJust tell me what you ate and I'll log it!",
        "billing.trial_started": "🎉 <b>Trial activated!</b>\n\nYou now have 3 days of full access (until {ends_str}).\nType or dictate what you ate, and I'll log everything!",
        "billing.trial_default_ends": "in 3 days",
        "billing.payment_record_error": "⚠️ Payment succeeded, but we couldn't update your subscription. Send /paysupport and we'll fix it.",
        "billing.payment_already": "This payment was already processed. Everything is fine!",
        "billing.payment_renewed": "🔄 <b>Subscription renewed!</b>\nNext renewal: {ends_str}",
        "billing.payment_activated": "✅ <b>Subscription activated!</b>\n\nYou have full YumYummy access until {ends_str}.\n{period_text}\n\nTell me what you ate, and I'll log it!",
        "billing.payment_period_recurring": "Your subscription renews automatically every 30 days.",
        "billing.payment_period_fixed": "Access is active until {ends_str}.",
        "billing.paysupport": "💬 <b>Payment support</b>\n\nIf you have questions or payment issues, message: @nik_kur\n\nWe reply within 24 hours.",
        "billing.terms": "📄 <b>Terms of use</b>\n\n1. YumYummy is a nutrition tracking and macro counting service.\n2. Payments are accepted via Telegram Stars (XTR) or bank card (via Gumroad).\n3. Monthly plan auto-renews every 30 days. Yearly plan is a one-time payment for 365 days.\n4. Telegram Stars subscriptions can be cancelled in Telegram settings. Gumroad subscriptions can be managed from your Gumroad receipt email.\n5. After cancellation, access stays active until the end of the paid period.\n6. Service usage is subject to fair-use limits per billing period. If the limit is reached, contact support for assistance.\n\nDetailed policies: <a href=\"https://yumyummy.ai\">yumyummy.ai</a>",
        "billing.usage_cap_reached": "⚠️ <b>Usage limit reached</b>\n\nYou have reached your AI usage limit for the current billing period.\nPlease contact support: @nik_kur",
        "billing.gumroad_error": "⚠️ Could not generate payment link. Please try again later.",
        "billing.gumroad_redirect": "💳 <b>Pay with card</b>\n\nTap the button below to open the secure checkout page.\nAfter payment, come back here and tap <b>Check payment status</b> — access activates automatically.",
        "billing.gumroad_check_btn": "🔄 Check payment status",
        "billing.payment_confirmed": "✅ <b>Payment confirmed{provider_label}!</b>\n\nYour subscription is now active.\nTell me what you ate, and I'll log it!",
        "billing.payment_pending": "⏳ Payment not received yet.\n\nIf you just paid, please wait a moment and tap the button again.\nIf you haven't paid yet, go back and tap the payment link.",
        "runbot.default_source": "AI estimate based on known average values for listed meals/products",
        "runbot.summary_today": "Today's summary:",
        "runbot.logged": "✅ Logged {description}",
        "runbot.macros_unknown": "ℹ️ Could not estimate calories/macros",
        "runbot.source_link": "🔗 Source: {source_label}",
        "runbot.source_hint": "💡 Source: {source_label}",
        "runbot.note": "Note: {notes}",
        "runbot.no_description": "No description",
        "runbot.by_items": "By items:",
        "runbot.dish": "Dish",
        "runbot.recommendation_title": "🤔 Recommendation:",
        "runbot.recommendation_best": "Best choice",
        "runbot.recommendation_alt1": "Alternative 1",
        "runbot.recommendation_alt2": "Alternative 2",
        "runbot.recommendation_variant": "Option {n}",
        "runbot.save_variant_prompt": "Tap a button below to log the selected option",
        "runbot.save_variant_btn1": "✅ Log option 1",
        "runbot.save_variant_btn2": "✅ Log option 2",
        "runbot.save_variant_btn3": "✅ Log option 3",
        "main.workflow_response_error": "There was an error while processing the response. Please try again later.",
        "main.workflow_not_configured": "Service is temporarily not configured (missing OpenAI key). Please contact admin.",
        "main.workflow_not_connected": "Service is temporarily unavailable. Please try again later.",
        "main.workflow_overloaded": "Service is overloaded or rate limit reached. Please try again soon.",
        "main.workflow_unexpected": "Something went wrong while processing your request. Please try again later.",
    },
    "ru": {
        "onboarding.welcome": """👋 Привет! Я — YumYummy.

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

Давай настроим всё под тебя — это ~30 секунд.""",
        "onboarding.goal": "Какая у тебя главная цель?",
        "onboarding.gender": "Укажи пол (для точного расчёта метаболизма):",
        "onboarding.params": "Отправь свои данные в формате:\nВозраст, Рост (см), Вес (кг)\n\nНапример: 28, 175, 72",
        "onboarding.activity": "Уровень физической активности:",
        "onboarding.manual_kbju": "✏️ Введи свои цели КБЖУ в формате:\nКалории, Белки (г), Жиры (г), Углеводы (г)\n\nНапример: 2000, 150, 65, 200",
        "onboarding.timezone_prompt": "🌍 Выбери свой часовой пояс:",
        "onboarding.timezone_other": "Введи свой часовой пояс в формате IANA, например:\nAsia/Dubai, Asia/Tokyo, Europe/Paris, America/Los_Angeles\n\nПолный список: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
        "onboarding.timezone_invalid": "Не удалось распознать часовой пояс '{tz}'. Попробуй ещё раз, например: Asia/Dubai, Europe/Paris",
        "onboarding.save_error": "Произошла ошибка при сохранении. Попробуй ещё раз позже.",
        "onboarding.start_needed": "Сначала нужно пройти настройку! Нажми /start",
        "onboarding.final": """🎉 Готово!

Краткая памятка:
📝 Пиши или говори что съел
📷 Штрих-код → точные данные
🏪 Укажи место → найду официальные данные
🤔 Что съесть? → умный совет
📊 Сегодня / 📈 Неделя → твой прогресс

🚀 Попробуй прямо сейчас!
Напиши, что ты ел сегодня на завтрак.

Удачи! 💪""",
        "onboarding.trial_activated": "🎉 Пробный период на 3 дня активирован!",
        "billing.usage_cap_reached": "⚠️ <b>Лимит использования достигнут</b>\n\nТы достиг(ла) лимита AI-использования для текущего расчетного периода.\nПожалуйста, напиши в поддержку: @nik_kur",
        "billing.terms": "📄 <b>Условия использования</b>\n\n1. YumYummy — сервис трекинга питания и подсчёта КБЖУ.\n2. Оплата принимается через Telegram Stars (XTR) или банковскую карту (через Gumroad).\n3. Месячный план продлевается автоматически каждые 30 дней. Годовой план — разовый платёж на 365 дней.\n4. Подписку через Stars можно отменить в настройках Telegram. Подписку через Gumroad — через письмо-чек от Gumroad.\n5. После отмены доступ сохраняется до конца оплаченного периода.\n6. Использование сервиса подчиняется fair-use лимитам на расчётный период. Если лимит достигнут, свяжись с поддержкой.\n\nПодробные политики: <a href=\"https://yumyummy.ai\">yumyummy.ai</a>",
    },
}


def tr(key: str, lang: str = DEFAULT_LANG, **kwargs: Any) -> str:
    table = MESSAGES.get(lang) or MESSAGES[DEFAULT_LANG]
    value = table.get(key) or MESSAGES[DEFAULT_LANG].get(key) or key
    if kwargs:
        return value.format(**kwargs)
    return value
