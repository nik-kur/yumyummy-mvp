"""
Paddle Billing checkout and portal endpoints.

- POST /billing/paddle/checkout — generates a URL to docs/pay.html with
  query params that Paddle.js uses to open the overlay checkout.
- GET  /billing/paddle/portal/{telegram_id} — returns the Paddle customer
  portal URL (cancel / update payment method) for an existing subscriber.
"""

import logging
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.deps import get_db
from app.models.user import User
from app.billing.plans import get_active_plan
from app.billing.claim_token import create_claim_token
from app.schemas.billing import PaddleCheckoutRequest, PaddleCheckoutResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/paddle/checkout", response_model=PaddleCheckoutResponse)
def generate_paddle_checkout(payload: PaddleCheckoutRequest, db: Session = Depends(get_db)):
    """Generate a Paddle checkout URL pointing to docs/pay.html."""
    if not settings.paddle_enabled:
        raise HTTPException(status_code=503, detail="Paddle payments not enabled")
    if not settings.paddle_client_side_token:
        raise HTTPException(status_code=503, detail="Paddle client token not configured")

    user = db.query(User).filter(User.telegram_id == payload.telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    plan = get_active_plan(payload.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Plan '{payload.plan_id}' is not active")

    claim_secret = settings.gumroad_claim_secret or settings.paddle_webhook_secret or ""
    token = create_claim_token(
        telegram_id=str(payload.telegram_id),
        plan_id=payload.plan_id,
        secret_key=claim_secret,
        ttl_seconds=3600,
    )

    params = {
        "tid": payload.telegram_id,
        "plan": payload.plan_id,
        "token": token,
        "cst": settings.paddle_client_side_token,
        "env": settings.paddle_environment,
    }
    checkout_url = f"https://yumyummy.ai/pay.html?{urlencode(params)}"

    return PaddleCheckoutResponse(
        checkout_url=checkout_url,
        plan_id=payload.plan_id,
    )


@router.get("/paddle/portal/{telegram_id}")
async def get_paddle_portal(telegram_id: str, db: Session = Depends(get_db)):
    """Return the Paddle customer portal URL for managing a subscription."""
    if not settings.paddle_enabled or not settings.paddle_api_key:
        raise HTTPException(status_code=503, detail="Paddle not enabled")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sub_id = user.subscription_paddle_id
    if not sub_id:
        raise HTTPException(status_code=404, detail="No Paddle subscription found")

    base = "https://sandbox-api.paddle.com" if settings.paddle_environment == "sandbox" else "https://api.paddle.com"
    url = f"{base}/subscriptions/{sub_id}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {settings.paddle_api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error("[PADDLE] Failed to fetch subscription %s: %s", sub_id, e)
        raise HTTPException(status_code=502, detail="Failed to fetch Paddle subscription")

    mgmt = data.get("data", {}).get("management_urls", {})
    cancel_url = mgmt.get("cancel")
    update_url = mgmt.get("update_payment_method")

    return {
        "cancel_url": cancel_url,
        "update_payment_method_url": update_url,
        "subscription_id": sub_id,
    }
