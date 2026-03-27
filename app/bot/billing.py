"""
Billing handlers: paywall, Telegram Stars payments, Gumroad checkout,
trial, access guard, and post-purchase return flow.
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
from app.i18n import DEFAULT_LANG, tr
from app.bot.api_client import (
    get_billing_status,
    start_trial,
    record_payment_success,
    cancel_subscription,
    get_gumroad_checkout_url,
    get_paddle_checkout_url,
)

logger = logging.getLogger(__name__)

router = Router()
LANG = DEFAULT_LANG

# ---------------------------------------------------------------------------
# Paywall display
# ---------------------------------------------------------------------------

PAYWALL_TRIAL_TEXT = (
    tr("billing.paywall_trial", LANG)
)

PAYWALL_EXPIRED_TEXT = (
    tr("billing.paywall_trial_expired", LANG)
)

PAYWALL_SUB_EXPIRED_TEXT = (
    tr("billing.paywall_sub_expired", LANG)
)


def _build_plans_text_stars() -> str:
    """Stars-only pricing for the separate Stars message."""
    plans = get_plans()
    lines = []
    for plan in plans.values():
        usd_hint = f" ({plan.approx_usd})" if plan.approx_usd else ""
        if plan.is_recurring:
            lines.append(
                f"<b>{plan.name_en}</b> — {plan.price_xtr} Stars/mo{usd_hint}"
            )
        else:
            lines.append(
                f"<b>{plan.name_en}</b> — {plan.price_xtr} Stars/year{usd_hint}"
            )
    return "\n".join(lines)


def _build_plans_text_card() -> str:
    """Card-only pricing for the main paywall message."""
    plans = get_plans()
    lines = []
    for plan in plans.values():
        usd_price = f"${plan.gumroad_price_cents / 100:.2f}" if plan.gumroad_price_cents else plan.approx_usd
        if plan.is_recurring:
            lines.append(f"<b>{plan.name_en}</b> — {usd_price}/mo")
        else:
            lines.append(f"<b>{plan.name_en}</b> — {usd_price}/year")
    return "\n".join(lines)


def _card_payments_enabled() -> bool:
    """True if any card payment provider (Paddle or Gumroad) is enabled."""
    return settings.paddle_enabled or settings.gumroad_enabled


async def _create_plan_button(bot, plan, tg_id: int) -> types.InlineKeyboardButton:
    """Create an invoice-link button for a plan (one-click payment)."""
    payload = f"sub:{plan.id}:{tg_id}"

    if plan.is_recurring:
        description = f"Monthly subscription ({plan.period_days}-day auto-renew)"
    else:
        description = f"Full access for {plan.period_days} days (one-time payment)"

    kwargs = dict(
        title=f"YumYummy — {plan.name_en}",
        description=description,
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=plan.name_en, amount=plan.price_xtr)],
    )
    if plan.subscription_period_seconds:
        kwargs["subscription_period"] = plan.subscription_period_seconds

    invoice_link = await bot.create_invoice_link(**kwargs)

    usd_hint = f" {plan.approx_usd}" if plan.approx_usd else ""
    if plan.is_recurring:
        label = f"⭐ {plan.name_en} — {plan.price_xtr} Stars/mo{usd_hint}"
    else:
        label = f"⭐ {plan.name_en} — {plan.price_xtr} Stars{usd_hint}"
    return types.InlineKeyboardButton(text=label, url=invoice_link)


async def _build_paywall_keyboard(
    bot, tg_id: int, show_trial: bool,
) -> types.InlineKeyboardMarkup:
    buttons = []
    if show_trial:
        buttons.append([
            types.InlineKeyboardButton(
                text=tr("billing.start_trial_btn", LANG),
                callback_data="billing:start_trial",
            )
        ])

    plans = get_plans()

    if _card_payments_enabled():
        for plan in plans.values():
            if not plan.is_active:
                continue

            checkout_url = None

            # Paddle first, then Gumroad fallback
            if settings.paddle_enabled:
                result = await get_paddle_checkout_url(tg_id, plan.id)
                if result and "checkout_url" in result:
                    checkout_url = result["checkout_url"]

            if checkout_url is None and settings.gumroad_enabled:
                result = await get_gumroad_checkout_url(tg_id, plan.id)
                if result and "checkout_url" in result:
                    checkout_url = result["checkout_url"]

            if checkout_url:
                usd_price = f"${plan.gumroad_price_cents / 100:.2f}" if plan.gumroad_price_cents else plan.approx_usd
                label = f"💳 {plan.name_en} — {usd_price}"
                if plan.is_recurring:
                    label += "/mo"
                else:
                    label += "/year"
                buttons.append([
                    types.InlineKeyboardButton(
                        text=label,
                        url=checkout_url,
                    )
                ])

        # "Pay with Telegram Stars" callback button
        buttons.append([
            types.InlineKeyboardButton(
                text=tr("billing.show_stars_btn", LANG),
                callback_data="billing:show_stars",
            )
        ])
    else:
        # Stars-only: show invoice buttons directly
        for plan in plans.values():
            if plan.is_active:
                btn = await _create_plan_button(bot, plan, tg_id)
                buttons.append([btn])

    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


async def show_paywall(message: types.Message, billing: Optional[dict] = None) -> None:
    if billing is None:
        billing = await get_billing_status(message.from_user.id)
    status = (billing or {}).get("access_status", "new")

    if _card_payments_enabled():
        plans_text = _build_plans_text_card()
    else:
        plans_text = _build_plans_text_stars()

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
    usage_exceeded = bool(billing.get("usage_exceeded", False))

    if usage_exceeded and status in ("trial", "active"):
        await message.answer(
            tr("billing.usage_cap_reached", LANG),
            parse_mode="HTML",
        )
        return False

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
        await query.message.answer(tr("billing.activate_trial_error", LANG))
        return

    ends_at = result.get("trial_ends_at", "")
    if isinstance(ends_at, str) and ends_at:
        try:
            dt = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
            ends_str = dt.strftime("%d.%m.%Y %H:%M UTC")
        except ValueError:
            ends_str = ends_at
    else:
        ends_str = tr("billing.trial_default_ends", LANG)

    if result.get("already_started"):
        await query.message.answer(
            tr("billing.trial_already", LANG, ends_str=ends_str),
            parse_mode="HTML",
        )
    else:
        await query.message.answer(
            tr("billing.trial_started", LANG, ends_str=ends_str),
            parse_mode="HTML",
        )


# ---------------------------------------------------------------------------
# Show Telegram Stars payment options
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "billing:show_stars")
async def handle_show_stars(query: types.CallbackQuery) -> None:
    await query.answer()
    tg_id = query.from_user.id
    plans = get_plans()

    buttons = []
    for plan in plans.values():
        if plan.is_active:
            btn = await _create_plan_button(query.bot, plan, tg_id)
            buttons.append([btn])

    stars_plans_text = _build_plans_text_stars()
    text = tr("billing.stars_info", LANG, stars_plans_text=stars_plans_text)

    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await query.message.answer(text, reply_markup=kb, parse_mode="HTML")


# ---------------------------------------------------------------------------
# Gumroad checkout callback (legacy, kept for backward compatibility)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("billing:gumroad:"))
async def handle_gumroad_checkout(query: types.CallbackQuery) -> None:
    await query.answer()
    tg_id = query.from_user.id
    plan_id = query.data.split(":")[-1]

    result = await get_gumroad_checkout_url(tg_id, plan_id)
    if result is None or "checkout_url" not in result:
        await query.message.answer(tr("billing.gumroad_error", LANG))
        return

    checkout_url = result["checkout_url"]
    plan = get_active_plan(plan_id)
    plan_name = plan.name_en if plan else plan_id

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text=f"💳 Pay for {plan_name} on Gumroad",
            url=checkout_url,
        )],
        [types.InlineKeyboardButton(
            text=tr("billing.gumroad_check_btn", LANG),
            callback_data="billing:check_payment",
        )],
    ])

    await query.message.answer(
        tr("billing.gumroad_redirect", LANG),
        reply_markup=kb,
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Post-purchase: check payment status
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "billing:check_payment")
async def handle_check_payment(query: types.CallbackQuery) -> None:
    await query.answer()
    tg_id = query.from_user.id
    billing = await get_billing_status(tg_id)
    status = (billing or {}).get("access_status", "expired")

    if status == "active":
        provider = (billing or {}).get("subscription_provider", "")
        provider_label = " via Gumroad" if provider == "gumroad" else ""
        await query.message.answer(
            tr("billing.payment_confirmed", LANG, provider_label=provider_label),
            parse_mode="HTML",
        )
    else:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(
                text=tr("billing.gumroad_check_btn", LANG),
                callback_data="billing:check_payment",
            )],
        ])
        await query.message.answer(
            tr("billing.payment_pending", LANG),
            reply_markup=kb,
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
            tr("billing.payment_record_error", LANG)
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
        await message.answer(tr("billing.payment_already", LANG))
    elif status == "renewed":
        await message.answer(
            tr("billing.payment_renewed", LANG, ends_str=ends_str),
            parse_mode="HTML",
        )
    else:
        period_text = (
            tr("billing.payment_period_recurring", LANG)
            if plan and plan.is_recurring
            else tr("billing.payment_period_fixed", LANG, ends_str=ends_str)
        )
        await message.answer(
            tr("billing.payment_activated", LANG, ends_str=ends_str, period_text=period_text),
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
        tr("billing.paysupport", LANG),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# /terms — required by Telegram for payment bots
# ---------------------------------------------------------------------------

@router.message(Command("terms"))
async def cmd_terms(message: types.Message) -> None:
    await message.answer(
        tr("billing.terms", LANG),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
