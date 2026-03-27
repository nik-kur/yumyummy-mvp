"""
Paddle Billing checkout endpoint.

Generates a URL to docs/pay.html with query params that Paddle.js
uses to open the overlay checkout.
"""

import logging
from urllib.parse import urlencode

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
