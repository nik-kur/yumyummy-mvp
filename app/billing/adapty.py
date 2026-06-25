"""
Apply Adapty (Apple/Google in-app purchase) events to account entitlement.

Adapty is the source of truth for App Store / Play purchases. Its webhook
tells us when a subscription becomes active, renews, is cancelled, expires or
is refunded. We mirror that onto the account's primary ``User`` subscription
columns (the same columns Telegram Stars / Paddle / Gumroad write), so
``account_access`` sees one unified entitlement.

Unlike the Telegram billing path, we deliberately do NOT fire the TikTok/Meta
pixels here — those are tuned to the Telegram/landing-page funnel, and App
Store attribution is handled inside Adapty/Apple.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.payment_event import PaymentEvent

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_duplicate(db: Session, transaction_id: Optional[str], event_type: str) -> bool:
    if not transaction_id:
        return False
    return (
        db.query(PaymentEvent)
        .filter(
            PaymentEvent.provider == "adapty",
            PaymentEvent.provider_event_id == transaction_id,
            PaymentEvent.event_type == event_type,
        )
        .first()
        is not None
    )


def _record_event(db: Session, user: User, *, event_type: str, plan_id: str,
                  transaction_id: Optional[str], raw_payload: Optional[str]) -> None:
    db.add(PaymentEvent(
        user_id=user.id,
        provider="adapty",
        provider_event_id=transaction_id,
        plan_id=plan_id or "unknown",
        event_type=event_type,
        currency="USD",
        is_recurring=True,
        raw_payload=raw_payload,
    ))


def grant_or_extend(db: Session, user: User, *, plan_id: str, expires_at: datetime,
                    auto_renew: bool = True, transaction_id: Optional[str] = None,
                    event_type: str = "purchase", raw_payload: Optional[str] = None) -> str:
    if _is_duplicate(db, transaction_id, event_type):
        return "already_processed"

    now = _now()
    _record_event(db, user, event_type=event_type, plan_id=plan_id,
                  transaction_id=transaction_id, raw_payload=raw_payload)

    if user.subscription_started_at is None:
        user.subscription_started_at = now
    user.subscription_plan_id = plan_id
    user.subscription_ends_at = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    user.subscription_auto_renew = auto_renew
    user.subscription_provider = "adapty"
    user.usage_cost_current_period = 0.0
    user.usage_period_start = now
    db.commit()
    db.refresh(user)
    logger.info("[ADAPTY] entitlement active user_id=%s plan=%s ends=%s", user.id, plan_id, user.subscription_ends_at)
    return "active"


def cancel(db: Session, user: User, *, transaction_id: Optional[str] = None,
           raw_payload: Optional[str] = None) -> str:
    if not user.subscription_plan_id:
        return "no_subscription"
    if not _is_duplicate(db, transaction_id, "cancellation"):
        _record_event(db, user, event_type="cancellation", plan_id=user.subscription_plan_id or "unknown",
                      transaction_id=transaction_id, raw_payload=raw_payload)
    user.subscription_auto_renew = False  # access remains until subscription_ends_at
    db.commit()
    db.refresh(user)
    logger.info("[ADAPTY] cancelled (auto-renew off) user_id=%s until=%s", user.id, user.subscription_ends_at)
    return "cancelled"


def revoke(db: Session, user: User, *, event_type: str = "expiration",
           transaction_id: Optional[str] = None, raw_payload: Optional[str] = None) -> str:
    if not _is_duplicate(db, transaction_id, event_type):
        _record_event(db, user, event_type=event_type, plan_id=user.subscription_plan_id or "unknown",
                      transaction_id=transaction_id, raw_payload=raw_payload)
    user.subscription_ends_at = _now()
    user.subscription_auto_renew = False
    db.commit()
    db.refresh(user)
    logger.info("[ADAPTY] revoked (%s) user_id=%s", event_type, user.id)
    return event_type
