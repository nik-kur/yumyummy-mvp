import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models.user import User
from app.billing.access import compute_access_status, trial_days_remaining, check_usage_cap, get_usage_cap_usd
from app.billing.plans import TRIAL_DAYS, get_active_plan
from app.billing.service import apply_subscription_payment, DuplicateEvent
from app.schemas.billing import (
    BillingStatusResponse,
    TrialStartRequest,
    TrialStartResponse,
    PaymentSuccessRequest,
    PaymentSuccessResponse,
    SubscriptionCancelRequest,
    SubscriptionCancelResponse,
    GumroadCheckoutRequest,
    GumroadCheckoutResponse,
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
        "usage_cost_current_period": user.usage_cost_current_period,
    }
    status = compute_access_status(user_dict)
    remaining = trial_days_remaining(user_dict) if status == "trial" else None
    usage_cap_usd = get_usage_cap_usd(user_dict)
    usage_exceeded = not check_usage_cap(user_dict) if usage_cap_usd is not None else False

    return BillingStatusResponse(
        telegram_id=telegram_id,
        access_status=status,
        trial_started_at=user.trial_started_at,
        trial_ends_at=user.trial_ends_at,
        trial_days_remaining=round(remaining, 2) if remaining is not None else None,
        subscription_plan_id=user.subscription_plan_id,
        subscription_ends_at=user.subscription_ends_at,
        subscription_auto_renew=user.subscription_auto_renew,
        subscription_provider=user.subscription_provider,
        usage_cost_current_period=round(float(user.usage_cost_current_period or 0.0), 6),
        usage_cap_usd=usage_cap_usd,
        usage_exceeded=usage_exceeded,
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
    user.usage_cost_current_period = 0.0
    user.usage_period_start = now
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

    try:
        status = apply_subscription_payment(
            db,
            user,
            provider="telegram",
            plan_id=payload.plan_id,
            telegram_payment_charge_id=payload.telegram_payment_charge_id,
            provider_payment_charge_id=payload.provider_payment_charge_id,
            amount_xtr=payload.amount_xtr,
            currency=payload.currency,
            is_recurring=payload.is_recurring,
            is_first_recurring=payload.is_first_recurring,
            invoice_payload=payload.invoice_payload,
            raw_payload=payload.raw_payload,
            subscription_expiration_date=payload.subscription_expiration_date,
        )
    except DuplicateEvent:
        logger.warning(
            "[BILLING] Duplicate Telegram payment charge_id=%s for telegram_id=%s",
            payload.telegram_payment_charge_id, payload.telegram_id,
        )
        return PaymentSuccessResponse(
            telegram_id=payload.telegram_id,
            status="already_processed",
            subscription_ends_at=user.subscription_ends_at,
            plan_id=payload.plan_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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


@router.post("/gumroad/checkout", response_model=GumroadCheckoutResponse)
def generate_gumroad_checkout(payload: GumroadCheckoutRequest, db: Session = Depends(get_db)):
    """Generate a personalised Gumroad checkout URL with a signed claim token."""
    from app.core.config import settings
    from app.billing.claim_token import create_claim_token

    if not settings.gumroad_enabled:
        raise HTTPException(status_code=503, detail="Gumroad payments not enabled")
    if not settings.gumroad_product_permalink:
        raise HTTPException(status_code=503, detail="Gumroad product not configured")
    if not settings.gumroad_claim_secret:
        raise HTTPException(status_code=503, detail="Gumroad claim secret not configured")

    user = db.query(User).filter(User.telegram_id == payload.telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    plan = get_active_plan(payload.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Plan '{payload.plan_id}' is not active")

    ttl = 3600
    token = create_claim_token(
        telegram_id=str(payload.telegram_id),
        plan_id=payload.plan_id,
        secret_key=settings.gumroad_claim_secret,
        ttl_seconds=ttl,
    )

    base_url = f"https://{settings.gumroad_seller_id}.gumroad.com/l/{settings.gumroad_product_permalink}"
    params = f"telegram_claim={token}"
    if plan.gumroad_recurrence:
        params += f"&recurrence={plan.gumroad_recurrence}"

    checkout_url = f"{base_url}?{params}"

    return GumroadCheckoutResponse(
        checkout_url=checkout_url,
        plan_id=payload.plan_id,
        expires_in_seconds=ttl,
    )
