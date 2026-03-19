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
    amount_cents: Optional[int] = None,
    amount_xtr: Optional[int] = None,
    currency: str = "USD",
    event_type: str = "purchase",
    is_recurring: bool = False,
    is_first_recurring: bool = False,
    invoice_payload: Optional[str] = None,
    raw_payload: Optional[str] = None,
    subscription_expiration_date: Optional[int] = None,
    period_days_override: Optional[int] = None,
) -> str:
    """
    Idempotent: activate or renew a subscription for *user*.

    Returns status string: 'activated' | 'renewed' | 'already_processed'.
    Raises DuplicateEvent if the same event was already ingested.
    """
    if _is_duplicate(db, provider=provider, provider_event_id=provider_event_id,
                     telegram_charge_id=telegram_payment_charge_id,
                     gumroad_sale_id=gumroad_sale_id, event_type=event_type):
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

    if subscription_expiration_date:
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

    return False
