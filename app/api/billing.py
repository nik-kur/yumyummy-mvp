import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models.user import User
from app.models.payment_event import PaymentEvent
from app.billing.access import compute_access_status, trial_days_remaining
from app.billing.plans import TRIAL_DAYS, get_active_plan
from app.schemas.billing import (
    BillingStatusResponse,
    TrialStartRequest,
    TrialStartResponse,
    PaymentSuccessRequest,
    PaymentSuccessResponse,
    SubscriptionCancelRequest,
    SubscriptionCancelResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/status/{telegram_id}", response_model=BillingStatusResponse)
def get_billing_status(telegram_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_dict = {
        "trial_started_at": user.trial_started_at,
        "trial_ends_at": user.trial_ends_at,
        "subscription_ends_at": user.subscription_ends_at,
    }
    status = compute_access_status(user_dict)
    remaining = trial_days_remaining(user_dict) if status == "trial" else None

    return BillingStatusResponse(
        telegram_id=telegram_id,
        access_status=status,
        trial_started_at=user.trial_started_at,
        trial_ends_at=user.trial_ends_at,
        trial_days_remaining=round(remaining, 2) if remaining is not None else None,
        subscription_plan_id=user.subscription_plan_id,
        subscription_ends_at=user.subscription_ends_at,
        subscription_auto_renew=user.subscription_auto_renew,
    )


@router.post("/trial/start", response_model=TrialStartResponse)
def start_trial(payload: TrialStartRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == payload.telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.trial_started_at is not None:
        return TrialStartResponse(
            telegram_id=payload.telegram_id,
            trial_started_at=user.trial_started_at,
            trial_ends_at=user.trial_ends_at,
            already_started=True,
        )

    now = datetime.now(timezone.utc)
    user.trial_started_at = now
    user.trial_ends_at = now + timedelta(days=TRIAL_DAYS)
    db.commit()
    db.refresh(user)

    logger.info(f"[BILLING] Trial started for telegram_id={payload.telegram_id}, ends_at={user.trial_ends_at}")

    return TrialStartResponse(
        telegram_id=payload.telegram_id,
        trial_started_at=user.trial_started_at,
        trial_ends_at=user.trial_ends_at,
        already_started=False,
    )


@router.post("/payment/telegram/success", response_model=PaymentSuccessResponse)
def record_payment_success(payload: PaymentSuccessRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == payload.telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (
        db.query(PaymentEvent)
        .filter(PaymentEvent.telegram_payment_charge_id == payload.telegram_payment_charge_id)
        .first()
    )
    if existing:
        logger.warning(
            f"[BILLING] Duplicate payment charge_id={payload.telegram_payment_charge_id} "
            f"for telegram_id={payload.telegram_id}"
        )
        return PaymentSuccessResponse(
            telegram_id=payload.telegram_id,
            status="already_processed",
            subscription_ends_at=user.subscription_ends_at,
            plan_id=payload.plan_id,
        )

    plan = get_active_plan(payload.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Plan '{payload.plan_id}' is not active")

    event = PaymentEvent(
        user_id=user.id,
        telegram_payment_charge_id=payload.telegram_payment_charge_id,
        provider_payment_charge_id=payload.provider_payment_charge_id,
        plan_id=payload.plan_id,
        amount_xtr=payload.amount_xtr,
        currency=payload.currency,
        is_recurring=payload.is_recurring,
        is_first_recurring=payload.is_first_recurring,
        invoice_payload=payload.invoice_payload,
        raw_payload=payload.raw_payload,
    )
    db.add(event)

    now = datetime.now(timezone.utc)

    if payload.subscription_expiration_date:
        sub_ends = datetime.fromtimestamp(payload.subscription_expiration_date, tz=timezone.utc)
    else:
        base = user.subscription_ends_at if (user.subscription_ends_at and user.subscription_ends_at > now) else now
        sub_ends = base + timedelta(days=plan.period_days)

    is_new = user.subscription_plan_id is None or user.subscription_started_at is None
    if is_new:
        user.subscription_started_at = now
    user.subscription_plan_id = payload.plan_id
    user.subscription_ends_at = sub_ends
    user.subscription_auto_renew = True
    user.subscription_telegram_charge_id = payload.telegram_payment_charge_id

    db.commit()
    db.refresh(user)

    status = "activated" if is_new else "renewed"
    logger.info(
        f"[BILLING] Payment {status} for telegram_id={payload.telegram_id}, "
        f"plan={payload.plan_id}, ends_at={user.subscription_ends_at}, "
        f"charge_id={payload.telegram_payment_charge_id}"
    )

    return PaymentSuccessResponse(
        telegram_id=payload.telegram_id,
        status=status,
        subscription_ends_at=user.subscription_ends_at,
        plan_id=payload.plan_id,
    )


@router.post("/subscription/cancel", response_model=SubscriptionCancelResponse)
def cancel_subscription(payload: SubscriptionCancelRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == payload.telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.subscription_plan_id:
        return SubscriptionCancelResponse(
            telegram_id=payload.telegram_id,
            status="no_subscription",
            access_until=None,
        )

    if user.subscription_auto_renew is False:
        return SubscriptionCancelResponse(
            telegram_id=payload.telegram_id,
            status="already_cancelled",
            access_until=user.subscription_ends_at,
        )

    user.subscription_auto_renew = False
    db.commit()
    db.refresh(user)

    logger.info(f"[BILLING] Subscription cancelled for telegram_id={payload.telegram_id}, access until {user.subscription_ends_at}")

    return SubscriptionCancelResponse(
        telegram_id=payload.telegram_id,
        status="cancelled",
        access_until=user.subscription_ends_at,
    )
