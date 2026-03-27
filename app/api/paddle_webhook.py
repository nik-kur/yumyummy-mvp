"""
Paddle Billing webhook handler.

Paddle sends JSON POST requests signed with Paddle-Signature header.
Events handled:
  - transaction.completed  → activate / renew subscription
  - subscription.activated → store paddle subscription ID
  - subscription.canceled  → mark auto_renew = False
  - subscription.updated   → update plan if changed
  - transaction.refunded (adjustment.created with action=refund) → revoke access

Signature verification uses HMAC-SHA256 with the webhook secret (h1= scheme).
"""

import hashlib
import hmac
import json
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.deps import get_db
from app.models.user import User
from app.billing.service import (
    apply_subscription_payment,
    apply_cancellation,
    apply_refund,
    DuplicateEvent,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["paddle"])


def _verify_paddle_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """
    Verify Paddle webhook signature.
    Header format: ts=<timestamp>;h1=<hmac_hex>
    Signed payload: timestamp + ":" + raw_body
    """
    parts = {}
    for segment in signature_header.split(";"):
        if "=" in segment:
            key, _, value = segment.partition("=")
            parts[key.strip()] = value.strip()

    ts = parts.get("ts", "")
    h1 = parts.get("h1", "")
    if not ts or not h1:
        return False

    signed_payload = f"{ts}:{raw_body.decode('utf-8')}"
    expected = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, h1)


def _extract_telegram_id(data: dict) -> Optional[str]:
    """Extract telegram_id from custom_data in the event payload."""
    custom = data.get("data", {}).get("custom_data") or {}
    if isinstance(custom, str):
        try:
            custom = json.loads(custom)
        except (json.JSONDecodeError, TypeError):
            custom = {}
    return custom.get("telegram_id")


def _extract_plan_id(data: dict) -> str:
    """Determine plan_id from the Paddle price ID in the event."""
    items = data.get("data", {}).get("items", [])
    if not items:
        return "monthly"

    price_id = items[0].get("price", {}).get("id", "")
    if price_id == settings.paddle_price_id_yearly:
        return "yearly"
    return "monthly"


def _extract_amount_cents(data: dict) -> Optional[int]:
    details = data.get("data", {}).get("details", {})
    totals = details.get("totals", {})
    total_str = totals.get("total")
    if total_str is not None:
        try:
            return int(total_str)
        except (ValueError, TypeError):
            pass
    return None


def _extract_currency(data: dict) -> str:
    return data.get("data", {}).get("currency_code", "USD")


def _find_user(db: Session, data: dict) -> Optional[User]:
    """Resolve user by telegram_id from custom_data or by stored paddle subscription ID."""
    tid = _extract_telegram_id(data)
    if tid:
        user = db.query(User).filter(User.telegram_id == str(tid)).first()
        if user:
            return user

    sub_id = data.get("data", {}).get("subscription_id") or data.get("data", {}).get("id")
    if sub_id:
        user = db.query(User).filter(User.subscription_paddle_id == sub_id).first()
        if user:
            return user

    return None


async def _notify_user(telegram_id: str, text: str) -> None:
    """Send a proactive Telegram message after Paddle payment events."""
    token = settings.telegram_bot_token
    if not token:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": telegram_id, "text": text, "parse_mode": "HTML"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("[PADDLE] Notified user %s", telegram_id)
            else:
                logger.warning("[PADDLE] Notify failed for %s: %s", telegram_id, resp.text[:200])
    except Exception as e:
        logger.warning("[PADDLE] Notify error for %s: %s", telegram_id, e)


@router.post("/webhooks/paddle")
async def paddle_webhook(request: Request, db: Session = Depends(get_db)):
    if not settings.paddle_enabled:
        raise HTTPException(status_code=404, detail="Not found")

    raw_body = await request.body()
    sig_header = request.headers.get("Paddle-Signature", "")

    if not settings.paddle_webhook_secret:
        logger.error("[PADDLE] Webhook secret not configured")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    if not _verify_paddle_signature(raw_body, sig_header, settings.paddle_webhook_secret):
        logger.warning("[PADDLE] Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = data.get("event_type", "")
    event_id = data.get("event_id", "")
    raw_payload = raw_body.decode("utf-8")

    logger.info("[PADDLE] Webhook: event_type=%s event_id=%s", event_type, event_id)

    user = _find_user(db, data)
    if user is None:
        logger.warning("[PADDLE] Could not resolve user for event %s", event_id)
        return {"status": "unresolved", "event_id": event_id}

    transaction_id = data.get("data", {}).get("id") or data.get("data", {}).get("transaction_id")
    subscription_id = data.get("data", {}).get("subscription_id") or data.get("data", {}).get("id")

    if event_type == "transaction.completed":
        status = _handle_transaction_completed(
            db, user, data,
            transaction_id=transaction_id,
            subscription_id=subscription_id,
            event_id=event_id,
            raw_payload=raw_payload,
        )
        if status in ("activated", "renewed"):
            await _notify_user(
                user.telegram_id,
                "\u2705 <b>Payment confirmed!</b>\n\n"
                "Your subscription is now active.\n"
                "Tell me what you ate, and I'll log it!",
            )

    elif event_type == "subscription.activated":
        sub_id = data.get("data", {}).get("id")
        if sub_id and not user.subscription_paddle_id:
            user.subscription_paddle_id = sub_id
            db.commit()
            logger.info("[PADDLE] Stored paddle subscription_id=%s for user_id=%s", sub_id, user.id)
        status = "subscription_stored"

    elif event_type in ("subscription.canceled", "subscription.past_due"):
        status = apply_cancellation(
            db, user,
            provider="paddle",
            provider_event_id=event_id,
            raw_payload=raw_payload,
        )

    elif event_type == "adjustment.created":
        action = data.get("data", {}).get("action", "")
        if action in ("refund", "chargeback"):
            status = apply_refund(
                db, user,
                provider="paddle",
                provider_event_id=event_id,
                raw_payload=raw_payload,
            )
            if status == "refunded":
                await _notify_user(
                    user.telegram_id,
                    "\u26a0\ufe0f <b>Refund processed</b>\n\n"
                    "Your subscription access has been revoked.\n"
                    "Contact @nik_kur if you have questions.",
                )
        else:
            status = "ignored"

    elif event_type == "subscription.updated":
        new_plan = _extract_plan_id(data)
        if new_plan != user.subscription_plan_id:
            user.subscription_plan_id = new_plan
            db.commit()
            logger.info("[PADDLE] Plan updated to %s for user_id=%s", new_plan, user.id)
        status = "plan_updated"

    else:
        logger.info("[PADDLE] Ignoring event_type=%s", event_type)
        status = "ignored"

    return {"status": status, "event_id": event_id}


def _handle_transaction_completed(
    db: Session,
    user: User,
    data: dict,
    *,
    transaction_id: Optional[str],
    subscription_id: Optional[str],
    event_id: str,
    raw_payload: str,
) -> str:
    plan_id = _extract_plan_id(data)
    amount_cents = _extract_amount_cents(data)
    currency = _extract_currency(data)

    billing_period = data.get("data", {}).get("billing_period", {})
    is_recurring = billing_period.get("starts_at") is not None

    try:
        status = apply_subscription_payment(
            db,
            user,
            provider="paddle",
            plan_id=plan_id,
            provider_event_id=event_id,
            paddle_transaction_id=transaction_id,
            paddle_subscription_id=subscription_id,
            amount_cents=amount_cents,
            currency=currency,
            event_type="purchase",
            is_recurring=is_recurring,
            raw_payload=raw_payload,
        )
        return status
    except DuplicateEvent:
        logger.info("[PADDLE] Duplicate transaction event_id=%s", event_id)
        return "already_processed"
    except ValueError as e:
        logger.error("[PADDLE] Transaction failed: %s", e)
        return "error"
