"""
Admin / reconciliation endpoints for billing.

Protected by internal API token. Use for:
  - manual lookup of payment events
  - force-activating a Gumroad subscription when webhook was missed
  - replaying a Gumroad sale by sale_id
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.deps import get_db
from app.models.user import User
from app.models.payment_event import PaymentEvent
from app.billing.plans import get_active_plan
from app.billing.service import apply_subscription_payment, DuplicateEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/billing", tags=["billing-admin"])


def _require_admin_token(x_admin_token: Optional[str] = Header(None)):
    expected = settings.internal_api_token
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


class ManualActivateRequest(BaseModel):
    telegram_id: str
    plan_id: str
    provider: str = "gumroad"
    gumroad_sale_id: Optional[str] = None
    gumroad_subscription_id: Optional[str] = None
    period_days_override: Optional[int] = None
    note: Optional[str] = None


class ManualActivateResponse(BaseModel):
    status: str
    subscription_ends_at: Optional[datetime] = None


@router.post("/manual-activate", response_model=ManualActivateResponse)
def manual_activate(
    payload: ManualActivateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_admin_token),
):
    """Force-activate a subscription. Use when webhook was missed."""
    user = db.query(User).filter(User.telegram_id == payload.telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    plan = get_active_plan(payload.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Plan '{payload.plan_id}' not active")

    try:
        status = apply_subscription_payment(
            db,
            user,
            provider=payload.provider,
            plan_id=payload.plan_id,
            provider_event_id=f"manual:{payload.gumroad_sale_id or 'admin'}",
            gumroad_sale_id=payload.gumroad_sale_id,
            gumroad_subscription_id=payload.gumroad_subscription_id,
            event_type="manual_activation",
            raw_payload=payload.note,
            period_days_override=payload.period_days_override,
        )
    except DuplicateEvent:
        return ManualActivateResponse(
            status="already_processed",
            subscription_ends_at=user.subscription_ends_at,
        )

    logger.info(
        "[ADMIN] Manual activation for telegram_id=%s plan=%s by admin",
        payload.telegram_id, payload.plan_id,
    )
    return ManualActivateResponse(
        status=status,
        subscription_ends_at=user.subscription_ends_at,
    )


class EventLookupResponse(BaseModel):
    total: int
    events: list


@router.get("/events/{telegram_id}", response_model=EventLookupResponse)
def lookup_events(
    telegram_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(_require_admin_token),
):
    """List all payment events for a user."""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    events = (
        db.query(PaymentEvent)
        .filter(PaymentEvent.user_id == user.id)
        .order_by(PaymentEvent.created_at.desc())
        .limit(50)
        .all()
    )

    results = []
    for e in events:
        results.append({
            "id": e.id,
            "provider": e.provider,
            "event_type": e.event_type,
            "provider_event_id": e.provider_event_id,
            "plan_id": e.plan_id,
            "amount_cents": e.amount_cents,
            "amount_xtr": e.amount_xtr,
            "currency": e.currency,
            "gumroad_sale_id": e.gumroad_sale_id,
            "gumroad_subscription_id": e.gumroad_subscription_id,
            "telegram_payment_charge_id": e.telegram_payment_charge_id,
            "created_at": str(e.created_at) if e.created_at else None,
        })

    return EventLookupResponse(total=len(results), events=results)


class UserBillingResponse(BaseModel):
    telegram_id: str
    subscription_plan_id: Optional[str]
    subscription_provider: Optional[str]
    subscription_starts_at: Optional[datetime]
    subscription_ends_at: Optional[datetime]
    subscription_auto_renew: Optional[bool]
    subscription_gumroad_id: Optional[str]
    trial_started_at: Optional[datetime]
    trial_ends_at: Optional[datetime]


@router.get("/user/{telegram_id}", response_model=UserBillingResponse)
def get_user_billing(
    telegram_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(_require_admin_token),
):
    """Get current billing state for a user."""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserBillingResponse(
        telegram_id=telegram_id,
        subscription_plan_id=user.subscription_plan_id,
        subscription_provider=user.subscription_provider,
        subscription_starts_at=user.subscription_started_at,
        subscription_ends_at=user.subscription_ends_at,
        subscription_auto_renew=user.subscription_auto_renew,
        subscription_gumroad_id=user.subscription_gumroad_id,
        trial_started_at=user.trial_started_at,
        trial_ends_at=user.trial_ends_at,
    )
