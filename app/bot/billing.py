"""
Billing handlers: paywall, Telegram Stars payments, trial, access guard.
"""
import json
import logging
from datetime import datetime
from typing import Optional

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice

from app.core.config import settings
from app.billing.plans import get_plans, get_active_plan, SUBSCRIPTION_PERIOD_SECONDS
from app.bot.api_client import (
    get_billing_status,
    start_trial,
    record_payment_success,
    cancel_subscription,
)

logger = logging.getLogger(__name__)

router = Router()

# ---------------------------------------------------------------------------
# Paywall display
# ---------------------------------------------------------------------------

PAYWALL_TRIAL_TEXT = (
    "🎉 <b>Попробуй YumYummy бесплатно!</b>\n\n"
    "3 дня полного доступа — без оплаты.\n"
    "После пробного периода выбери подходящий тариф.\n\n"
    "{plans_text}"
)

PAYWALL_EXPIRED_TEXT = (
    "⏰ <b>Пробный период закончился</b>\n\n"
    "Чтобы продолжить пользоваться YumYummy, оформи подписку:\n\n"
    "{plans_text}"
)

PAYWALL_SUB_EXPIRED_TEXT = (
    "⏰ <b>Подписка закончилась</b>\n\n"
    "Оформи подписку, чтобы продолжить:\n\n"
    "{plans_text}"
)


def _build_plans_text() -> str:
    plans = get_plans()
    lines = []
    for plan in plans.values():
        if plan.is_recurring:
            lines.append(f"⭐ <b>{plan.name_ru}</b> — {plan.price_xtr} Stars/мес")
        else:
            lines.append(f"⭐ <b>{plan.name_ru}</b> — {plan.price_xtr} Stars")
    return "\n".join(lines)


async def _create_plan_button(bot, plan, tg_id: int) -> types.InlineKeyboardButton:
    """Create an invoice-link button for a plan (one-click payment)."""
    payload = f"sub:{plan.id}:{tg_id}"

    kwargs = dict(
        title=f"YumYummy — {plan.name_ru}",
        description=(
            f"Подписка на {plan.period_days} дней с автопродлением"
            if plan.is_recurring
            else f"Доступ на {plan.period_days} дней"
        ),
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=plan.name_ru, amount=plan.price_xtr)],
    )
    if plan.subscription_period_seconds:
        kwargs["subscription_period"] = plan.subscription_period_seconds

    invoice_link = await bot.create_invoice_link(**kwargs)

    label = f"⭐ {plan.name_ru} — {plan.price_xtr} Stars"
    return types.InlineKeyboardButton(text=label, url=invoice_link)


async def _build_paywall_keyboard(
    bot, tg_id: int, show_trial: bool,
) -> types.InlineKeyboardMarkup:
    buttons = []
    if show_trial:
        buttons.append([
            types.InlineKeyboardButton(
                text="🆓 Начать бесплатно 3 дня",
                callback_data="billing:start_trial",
            )
        ])

    plans = get_plans()
    for plan in plans.values():
        if plan.is_active:
            btn = await _create_plan_button(bot, plan, tg_id)
            buttons.append([btn])

    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


async def show_paywall(message: types.Message, billing: Optional[dict] = None) -> None:
    if billing is None:
        billing = await get_billing_status(message.from_user.id)
    status = (billing or {}).get("access_status", "new")
    plans_text = _build_plans_text()

    if status == "new":
        text = PAYWALL_TRIAL_TEXT.format(plans_text=plans_text)
        kb = await _build_paywall_keyboard(message.bot, message.from_user.id, show_trial=True)
    elif status == "trial_expired":
        text = PAYWALL_EXPIRED_TEXT.format(plans_text=plans_text)
        kb = await _build_paywall_keyboard(message.bot, message.from_user.id, show_trial=False)
    else:
        text = PAYWALL_SUB_EXPIRED_TEXT.format(plans_text=plans_text)
        kb = await _build_paywall_keyboard(message.bot, message.from_user.id, show_trial=False)

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


# ---------------------------------------------------------------------------
# Access guard (call from other handlers)
# ---------------------------------------------------------------------------

async def check_billing_access(message: types.Message) -> bool:
    """
    Returns True if user has active trial or subscription.
    Shows paywall and returns False otherwise.
    """
    if not settings.billing_paywall_enabled:
        return True

    billing = await get_billing_status(message.from_user.id)
    if billing is None:
        return True  # fail open on backend error

    status = billing.get("access_status", "new")
    if status in ("trial", "active"):
        return True

    await show_paywall(message, billing)
    return False


# ---------------------------------------------------------------------------
# Trial start callback
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "billing:start_trial")
async def handle_start_trial(query: types.CallbackQuery) -> None:
    await query.answer()
    tg_id = query.from_user.id
    result = await start_trial(tg_id)
    if result is None:
        await query.message.answer("Не удалось активировать пробный период. Попробуй позже.")
        return

    ends_at = result.get("trial_ends_at", "")
    if isinstance(ends_at, str) and ends_at:
        try:
            dt = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
            ends_str = dt.strftime("%d.%m.%Y %H:%M UTC")
        except ValueError:
            ends_str = ends_at
    else:
        ends_str = "через 3 дня"

    if result.get("already_started"):
        await query.message.answer(
            f"У тебя уже есть пробный период до {ends_str}.\n"
            "Напиши, что ты съел, и я всё запишу!",
            parse_mode="HTML",
        )
    else:
        await query.message.answer(
            f"🎉 <b>Пробный период активирован!</b>\n\n"
            f"У тебя есть 3 дня полного доступа (до {ends_str}).\n"
            f"Напиши или надиктуй, что ты съел, и я всё запишу!",
            parse_mode="HTML",
        )


# ---------------------------------------------------------------------------
# Payment: pre-checkout
# ---------------------------------------------------------------------------

@router.pre_checkout_query()
async def handle_pre_checkout(pre_checkout_query: types.PreCheckoutQuery) -> None:
    await pre_checkout_query.answer(ok=True)


# ---------------------------------------------------------------------------
# Payment: successful
# ---------------------------------------------------------------------------

@router.message(F.successful_payment)
async def handle_successful_payment(message: types.Message) -> None:
    payment = message.successful_payment
    tg_id = message.from_user.id

    payload_str = payment.invoice_payload or ""
    parts = payload_str.split(":")
    plan_id = parts[1] if len(parts) >= 2 else "monthly"

    raw = json.dumps({
        "currency": payment.currency,
        "total_amount": payment.total_amount,
        "invoice_payload": payment.invoice_payload,
        "telegram_payment_charge_id": payment.telegram_payment_charge_id,
        "provider_payment_charge_id": payment.provider_payment_charge_id,
        "is_recurring": getattr(payment, "is_recurring", False),
        "is_first_recurring": getattr(payment, "is_first_recurring", False),
        "subscription_expiration_date": getattr(payment, "subscription_expiration_date", None),
    }, default=str)

    result = await record_payment_success(
        telegram_id=tg_id,
        telegram_payment_charge_id=payment.telegram_payment_charge_id,
        provider_payment_charge_id=payment.provider_payment_charge_id,
        plan_id=plan_id,
        amount_xtr=payment.total_amount,
        is_recurring=getattr(payment, "is_recurring", False),
        is_first_recurring=getattr(payment, "is_first_recurring", False),
        invoice_payload=payment.invoice_payload,
        raw_payload=raw,
        subscription_expiration_date=getattr(payment, "subscription_expiration_date", None),
    )

    if result is None:
        await message.answer(
            "⚠️ Оплата прошла, но не удалось обновить подписку. "
            "Напиши /paysupport — мы разберёмся."
        )
        logger.error(f"[BILLING] Backend failed to record payment for tg_id={tg_id}")
        return

    sub_ends = result.get("subscription_ends_at", "")
    if isinstance(sub_ends, str) and sub_ends:
        try:
            dt = datetime.fromisoformat(sub_ends.replace("Z", "+00:00"))
            ends_str = dt.strftime("%d.%m.%Y")
        except ValueError:
            ends_str = sub_ends
    else:
        ends_str = ""

    plan = get_active_plan(plan_id)
    status = result.get("status", "activated")
    if status == "already_processed":
        await message.answer("Эта оплата уже была обработана ранее. Всё в порядке!")
    elif status == "renewed":
        await message.answer(
            f"🔄 <b>Подписка продлена!</b>\n"
            f"Следующее продление: {ends_str}",
            parse_mode="HTML",
        )
    else:
        period_text = (
            f"Подписка автоматически продлевается каждые 30 дней."
            if plan and plan.is_recurring
            else f"Доступ активен до {ends_str}."
        )
        await message.answer(
            f"✅ <b>Подписка оформлена!</b>\n\n"
            f"У тебя полный доступ к YumYummy до {ends_str}.\n"
            f"{period_text}\n\n"
            f"Напиши, что ты съел, и я всё запишу!",
            parse_mode="HTML",
        )


# ---------------------------------------------------------------------------
# /subscribe — show paywall explicitly
# ---------------------------------------------------------------------------

@router.message(Command("subscribe"))
async def cmd_subscribe(message: types.Message) -> None:
    await show_paywall(message)


# ---------------------------------------------------------------------------
# /paysupport — required by Telegram for payment bots
# ---------------------------------------------------------------------------

@router.message(Command("paysupport"))
async def cmd_paysupport(message: types.Message) -> None:
    await message.answer(
        "💬 <b>Поддержка по оплате</b>\n\n"
        "Если у тебя возникли вопросы или проблемы с оплатой, "
        "напиши: @nik_kur\n\n"
        "Мы ответим в течение 24 часов.",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# /terms — required by Telegram for payment bots
# ---------------------------------------------------------------------------

@router.message(Command("terms"))
async def cmd_terms(message: types.Message) -> None:
    await message.answer(
        "📄 <b>Условия использования</b>\n\n"
        "1. YumYummy — сервис для трекинга питания и подсчёта КБЖУ.\n"
        "2. Подписка оплачивается через Telegram Stars (XTR).\n"
        "3. Месячная подписка автоматически продлевается каждые 30 дней.\n"
        "4. Отменить подписку можно в любой момент в настройках Telegram.\n"
        "5. После отмены доступ сохраняется до конца оплаченного периода.\n\n"
        'Подробные политики: <a href="https://yumyummy.ai">yumyummy.ai</a>',
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
