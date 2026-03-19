"""
Gumroad webhook (ping) ingestion endpoint.

Gumroad sends form-encoded POST requests for events:
  sale, refund, dispute, cancellation,
  subscription_updated, subscription_ended, subscription_restarted.

The endpoint:
  1. Validates the webhook secret path segment.
  2. Extracts the claim token from url_params to identify the Telegram user.
  3. Maps the event to our internal billing service.
  4. Returns 200 so Gumroad does not retry.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.deps import get_db
from app.models.user import User
from app.billing.claim_token import verify_claim_token
from app.billing.service import (
    apply_subscription_payment,
    apply_cancellation,
    apply_refund,
    DuplicateEvent,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gumroad"])


def _plan_id_from_recurrence(recurrence: Optional[str]) -> str:
    if recurrence and recurrence.lower() in ("yearly", "annually"):
        return "yearly"
    return "monthly"


def _parse_url_params(raw: Optional[str]) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_custom_fields(raw: Optional[str]) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _cents_from_price(price_str: Optional[str]) -> Optional[int]:
    """Convert Gumroad price string like '9.99' or '999' to integer cents."""
    if not price_str:
        return None
    try:
        val = float(str(price_str).replace(",", ""))
        if val > 100:
            return int(val)
        return int(round(val * 100))
    except (ValueError, TypeError):
        return None


def _find_user_by_claim(db: Session, claim_token: Optional[str]) -> Optional[User]:
    """Resolve a Telegram user from the signed claim token."""
    if not claim_token or not settings.gumroad_claim_secret:
        return None
    payload = verify_claim_token(claim_token, settings.gumroad_claim_secret)
    if not payload:
        return None
    telegram_id = payload.get("tid")
    if not telegram_id:
        return None
    return db.query(User).filter(User.telegram_id == str(telegram_id)).first()


def _find_user_by_gumroad_sub(db: Session, subscription_id: Optional[str]) -> Optional[User]:
    """Resolve user by their stored Gumroad subscription ID (for renewals/cancels)."""
    if not subscription_id:
        return None
    return db.query(User).filter(User.subscription_gumroad_id == subscription_id).first()


@router.post("/webhooks/gumroad/{secret}")
async def gumroad_webhook(secret: str, request: Request, db: Session = Depends(get_db)):
    if not settings.gumroad_enabled:
        raise HTTPException(status_code=404, detail="Not found")

    expected_secret = settings.gumroad_webhook_secret or ""
    if secret != expected_secret:
        logger.warning("[GUMROAD] Webhook called with wrong secret")
        raise HTTPException(status_code=403, detail="Forbidden")

    form = await request.form()
    data = dict(form)
    raw_payload = json.dumps(data, default=str)

    resource_name = str(data.get("resource_name", "sale")).lower()
    sale_id = str(data.get("sale_id", "")) or None
    subscription_id = str(data.get("subscription_id", "")) or None
    seller_id = str(data.get("seller_id", ""))
    email = str(data.get("email", ""))
    price = str(data.get("price", ""))
    currency = str(data.get("currency", "usd")).upper()
    recurrence = str(data.get("recurrence", "")) or None
    is_recurring = str(data.get("is_recurring_charge", "")).lower() == "true"
    refunded = str(data.get("refunded", "")).lower() == "true"
    disputed = str(data.get("disputed", "")).lower() == "true"

    url_params = _parse_url_params(data.get("url_params"))
    claim_token = url_params.get("telegram_claim")

    logger.info(
        "[GUMROAD] Webhook received: resource=%s sale_id=%s sub_id=%s email=%s refunded=%s disputed=%s",
        resource_name, sale_id, subscription_id, email, refunded, disputed,
    )

    if settings.gumroad_seller_id and seller_id != settings.gumroad_seller_id:
        logger.warning("[GUMROAD] seller_id mismatch: got %s, expected %s", seller_id, settings.gumroad_seller_id)
        return {"status": "ignored", "reason": "seller_id_mismatch"}

    user = _find_user_by_claim(db, claim_token)
    if user is None and subscription_id:
        user = _find_user_by_gumroad_sub(db, subscription_id)

    if user is None:
        logger.warning(
            "[GUMROAD] Could not resolve user: claim=%s sub_id=%s sale_id=%s email=%s",
            claim_token is not None, subscription_id, sale_id, email,
        )
        return {"status": "unresolved", "reason": "user_not_found", "sale_id": sale_id}

    plan_id = _plan_id_from_recurrence(recurrence)
    if claim_token and settings.gumroad_claim_secret:
        payload = verify_claim_token(claim_token, settings.gumroad_claim_secret)
        if payload and payload.get("pid"):
            plan_id = payload["pid"]

    amount_cents = _cents_from_price(price)
    event_id = f"{resource_name}:{sale_id}" if sale_id else None

    if resource_name in ("sale", "subscription_restarted"):
        if refunded:
            status = _handle_refund(db, user, event_id=event_id, sale_id=sale_id, raw_payload=raw_payload)
        elif disputed:
            status = _handle_refund(db, user, event_id=event_id, sale_id=sale_id, raw_payload=raw_payload)
        else:
            status = _handle_purchase(
                db, user,
                plan_id=plan_id,
                event_id=event_id,
                sale_id=sale_id,
                subscription_id=subscription_id,
                amount_cents=amount_cents,
                currency=currency,
                is_recurring=is_recurring,
                raw_payload=raw_payload,
            )
    elif resource_name == "refund":
        status = _handle_refund(db, user, event_id=event_id, sale_id=sale_id, raw_payload=raw_payload)
    elif resource_name == "dispute":
        status = _handle_refund(db, user, event_id=event_id, sale_id=sale_id, raw_payload=raw_payload)
    elif resource_name in ("cancellation", "subscription_ended"):
        status = _handle_cancel(
            db, user, event_id=event_id, subscription_id=subscription_id, raw_payload=raw_payload,
        )
    elif resource_name == "subscription_updated":
        status = _handle_purchase(
            db, user,
            plan_id=plan_id,
            event_id=event_id,
            sale_id=sale_id,
            subscription_id=subscription_id,
            amount_cents=amount_cents,
            currency=currency,
            is_recurring=is_recurring,
            raw_payload=raw_payload,
        )
    else:
        logger.info("[GUMROAD] Ignoring resource_name=%s", resource_name)
        status = "ignored"

    return {"status": status, "sale_id": sale_id}


def _handle_purchase(
    db: Session,
    user: User,
    *,
    plan_id: str,
    event_id: Optional[str],
    sale_id: Optional[str],
    subscription_id: Optional[str],
    amount_cents: Optional[int],
    currency: str,
    is_recurring: bool,
    raw_payload: str,
) -> str:
    try:
        status = apply_subscription_payment(
            db,
            user,
            provider="gumroad",
            plan_id=plan_id,
            provider_event_id=event_id,
            gumroad_sale_id=sale_id,
            gumroad_subscription_id=subscription_id,
            amount_cents=amount_cents,
            currency=currency,
            event_type="purchase",
            is_recurring=is_recurring,
            raw_payload=raw_payload,
        )
        return status
    except DuplicateEvent:
        logger.info("[GUMROAD] Duplicate purchase event_id=%s", event_id)
        return "already_processed"
    except ValueError as e:
        logger.error("[GUMROAD] Purchase failed: %s", e)
        return "error"


def _handle_cancel(
    db: Session,
    user: User,
    *,
    event_id: Optional[str],
    subscription_id: Optional[str],
    raw_payload: str,
) -> str:
    return apply_cancellation(
        db, user,
        provider="gumroad",
        provider_event_id=event_id,
        gumroad_subscription_id=subscription_id,
        raw_payload=raw_payload,
    )


def _handle_refund(
    db: Session,
    user: User,
    *,
    event_id: Optional[str],
    sale_id: Optional[str],
    raw_payload: str,
) -> str:
    return apply_refund(
        db, user,
        provider="gumroad",
        provider_event_id=event_id,
        gumroad_sale_id=sale_id,
        raw_payload=raw_payload,
    )
