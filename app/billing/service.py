"""
Provider-neutral billing service. Both Telegram Stars and Gumroad
ingestion paths funnel through these functions to update User
entitlement state and write PaymentEvent audit rows.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.payment_event import PaymentEvent
from app.billing.plans import get_active_plan

logger = logging.getLogger(__name__)


class DuplicateEvent(Exception):
    pass


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def apply_subscription_payment(
    db: Session,
    user: User,
    *,
    provider: str,
    plan_id: str,
    provider_event_id: Optional[str] = None,
    telegram_payment_charge_id: Optional[str] = None,
    provider_payment_charge_id: Optional[str] = None,
    gumroad_sale_id: Optional[str] = None,
    gumroad_subscription_id: Optional[str] = None,
    paddle_transaction_id: Optional[str] = None,
    paddle_subscription_id: Optional[str] = None,
    amount_cents: Optional[int] = None,
    amount_xtr: Optional[int] = None,
    currency: str = "USD",
    event_type: str = "purchase",
    is_recurring: bool = False,
    is_first_recurring: bool = False,
    invoice_payload: Optional[str] = None,
    raw_payload: Optional[str] = None,
    subscription_expiration_date: Optional[int] = None,
    period_ends_at: Optional[datetime] = None,
    period_days_override: Optional[int] = None,
    **kwargs,
) -> str:
    """
    Idempotent: activate or renew a subscription for *user*.

    Returns status string: 'activated' | 'renewed' | 'already_processed'.
    Raises DuplicateEvent if the same event was already ingested.

    Source of truth for `subscription_ends_at` (in priority order):
      1. ``period_ends_at`` — explicit datetime from the payment provider
         (e.g. Paddle's ``current_billing_period.ends_at``).
      2. ``subscription_expiration_date`` — unix timestamp (Telegram Stars).
      3. Existing-end + ``period_days`` arithmetic (only used when the provider
         did not supply an exact end date, e.g. Gumroad / Telegram fallback).

    Always trust an authoritative date from the provider over calendar math:
    a Paddle "monthly" cycle is a calendar month (28-31 days), not 30 days.
    """
    if _is_duplicate(db, provider=provider, provider_event_id=provider_event_id,
                     telegram_charge_id=telegram_payment_charge_id,
                     gumroad_sale_id=gumroad_sale_id,
                     paddle_transaction_id=paddle_transaction_id,
                     event_type=event_type):
        raise DuplicateEvent(f"Duplicate {provider} event")

    plan = get_active_plan(plan_id)
    if plan is None:
        raise ValueError(f"Plan '{plan_id}' is not active")

    event = PaymentEvent(
        user_id=user.id,
        provider=provider,
        provider_event_id=provider_event_id,
        telegram_payment_charge_id=telegram_payment_charge_id,
        provider_payment_charge_id=provider_payment_charge_id,
        gumroad_sale_id=gumroad_sale_id,
        gumroad_subscription_id=gumroad_subscription_id,
        paddle_transaction_id=paddle_transaction_id,
        paddle_subscription_id=paddle_subscription_id,
        plan_id=plan_id,
        amount_cents=amount_cents,
        amount_xtr=amount_xtr,
        currency=currency,
        event_type=event_type,
        is_recurring=is_recurring,
        is_first_recurring=is_first_recurring,
        invoice_payload=invoice_payload,
        raw_payload=raw_payload,
    )
    db.add(event)

    now = datetime.now(timezone.utc)
    period_days = period_days_override or plan.period_days

    if period_ends_at is not None:
        sub_ends = _ensure_utc(period_ends_at)
    elif subscription_expiration_date:
        sub_ends = datetime.fromtimestamp(subscription_expiration_date, tz=timezone.utc)
    else:
        existing_ends = _ensure_utc(user.subscription_ends_at)
        base = existing_ends if (existing_ends and existing_ends > now) else now
        sub_ends = base + timedelta(days=period_days)

    is_new = user.subscription_plan_id is None or user.subscription_started_at is None
    if is_new:
        user.subscription_started_at = now

    user.subscription_plan_id = plan_id
    user.subscription_ends_at = sub_ends
    user.subscription_auto_renew = plan.is_recurring
    user.subscription_provider = provider

    if provider == "telegram" and telegram_payment_charge_id:
        user.subscription_telegram_charge_id = telegram_payment_charge_id
    if provider == "gumroad" and gumroad_subscription_id:
        user.subscription_gumroad_id = gumroad_subscription_id
    if provider == "paddle" and paddle_subscription_id:
        user.subscription_paddle_id = paddle_subscription_id

    user.usage_cost_current_period = 0.0
    user.usage_period_start = now

    db.commit()
    db.refresh(user)

    status = "activated" if is_new else "renewed"
    logger.info(
        "[BILLING] Payment %s via %s for user_id=%s, plan=%s, ends_at=%s",
        status, provider, user.id, plan_id, user.subscription_ends_at,
    )
    return status


def sync_subscription_state(
    db: Session,
    user: User,
    *,
    provider: str,
    period_ends_at: Optional[datetime] = None,
    auto_renew: Optional[bool] = None,
    plan_id: Optional[str] = None,
    paddle_subscription_id: Optional[str] = None,
    revoke: bool = False,
) -> str:
    """
    Mirror provider-side state changes onto the local user record.

    Use this for events that aren't payments — e.g. ``subscription.updated``,
    ``subscription.paused``, ``subscription.resumed``, or a periodic
    reconciliation against Paddle's API.

    Only fields with a non-``None`` argument are touched. ``revoke=True`` sets
    ``subscription_ends_at`` to *now* and disables auto-renew (used for
    paused subs that should lose access immediately).

    Returns: 'updated' | 'unchanged' | 'no_subscription'.
    """
    if not user.subscription_plan_id and not paddle_subscription_id:
        return "no_subscription"

    changed = False
    now = datetime.now(timezone.utc)

    if revoke:
        user.subscription_ends_at = now
        user.subscription_auto_renew = False
        changed = True
    else:
        if period_ends_at is not None:
            new_ends = _ensure_utc(period_ends_at)
            existing = _ensure_utc(user.subscription_ends_at)
            if existing != new_ends:
                user.subscription_ends_at = new_ends
                changed = True
        if auto_renew is not None and user.subscription_auto_renew != auto_renew:
            user.subscription_auto_renew = auto_renew
            changed = True

    if plan_id is not None and plan_id != user.subscription_plan_id:
        if get_active_plan(plan_id) is not None:
            user.subscription_plan_id = plan_id
            changed = True

    if paddle_subscription_id and not user.subscription_paddle_id:
        user.subscription_paddle_id = paddle_subscription_id
        changed = True

    if provider and not user.subscription_provider:
        user.subscription_provider = provider
        changed = True

    if not changed:
        return "unchanged"

    db.commit()
    db.refresh(user)
    logger.info(
        "[BILLING] Synced %s state for user_id=%s ends_at=%s auto_renew=%s revoke=%s",
        provider, user.id, user.subscription_ends_at, user.subscription_auto_renew, revoke,
    )
    return "updated"


def apply_cancellation(
    db: Session,
    user: User,
    *,
    provider: str,
    provider_event_id: Optional[str] = None,
    gumroad_subscription_id: Optional[str] = None,
    raw_payload: Optional[str] = None,
) -> str:
    """
    Mark subscription as non-renewing. Access stays until subscription_ends_at.
    Returns: 'cancelled' | 'already_cancelled' | 'no_subscription'.
    """
    if not user.subscription_plan_id:
        return "no_subscription"
    if user.subscription_auto_renew is False:
        return "already_cancelled"

    event = PaymentEvent(
        user_id=user.id,
        provider=provider,
        provider_event_id=provider_event_id,
        gumroad_subscription_id=gumroad_subscription_id,
        plan_id=user.subscription_plan_id or "unknown",
        event_type="cancellation",
        currency="USD",
        raw_payload=raw_payload,
    )
    db.add(event)

    user.subscription_auto_renew = False
    db.commit()
    db.refresh(user)

    logger.info(
        "[BILLING] Subscription cancelled via %s for user_id=%s, access until %s",
        provider, user.id, user.subscription_ends_at,
    )
    return "cancelled"


def apply_refund(
    db: Session,
    user: User,
    *,
    provider: str,
    provider_event_id: Optional[str] = None,
    gumroad_sale_id: Optional[str] = None,
    raw_payload: Optional[str] = None,
) -> str:
    """
    Handle refund: revoke access immediately.
    Returns: 'refunded'.
    """
    event = PaymentEvent(
        user_id=user.id,
        provider=provider,
        provider_event_id=provider_event_id,
        gumroad_sale_id=gumroad_sale_id,
        plan_id=user.subscription_plan_id or "unknown",
        event_type="refund",
        currency="USD",
        raw_payload=raw_payload,
    )
    db.add(event)

    now = datetime.now(timezone.utc)
    user.subscription_ends_at = now
    user.subscription_auto_renew = False
    db.commit()
    db.refresh(user)

    logger.info(
        "[BILLING] Refund via %s for user_id=%s, access revoked",
        provider, user.id,
    )
    return "refunded"


def _is_duplicate(
    db: Session,
    *,
    provider: str,
    provider_event_id: Optional[str],
    telegram_charge_id: Optional[str],
    gumroad_sale_id: Optional[str],
    paddle_transaction_id: Optional[str] = None,
    event_type: str,
) -> bool:
    if provider == "telegram" and telegram_charge_id:
        return db.query(PaymentEvent).filter(
            PaymentEvent.telegram_payment_charge_id == telegram_charge_id,
        ).first() is not None

    if provider == "gumroad" and provider_event_id:
        return db.query(PaymentEvent).filter(
            PaymentEvent.provider == "gumroad",
            PaymentEvent.provider_event_id == provider_event_id,
        ).first() is not None

    if provider == "gumroad" and gumroad_sale_id and event_type == "purchase":
        return db.query(PaymentEvent).filter(
            PaymentEvent.gumroad_sale_id == gumroad_sale_id,
            PaymentEvent.event_type == "purchase",
        ).first() is not None

    if provider == "paddle" and paddle_transaction_id:
        return db.query(PaymentEvent).filter(
            PaymentEvent.paddle_transaction_id == paddle_transaction_id,
            PaymentEvent.event_type == event_type,
        ).first() is not None

    return False
