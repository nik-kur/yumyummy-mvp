"""
Adapty webhook — App Store / Play subscription events.

Configure Adapty (Integrations -> Webhook) to POST here with a shared secret
in the ``Authorization`` header (matching ``ADAPTY_WEBHOOK_SECRET``) and to
send the app's ``customer_user_id`` — which we set equal to our ``account_id``
when initialising the Adapty SDK in the app.

NOTE: Adapty's exact event names / property keys vary by app config. We parse
defensively and classify by keyword (active / cancel / expire / refund), so
the mapping is robust, but you should confirm ``vendor_product_id`` values and
event names against your Adapty dashboard once products are created.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.core.config import settings
from app.core import posthog_client
from app.models.account import Account
from app.models.user import User
from app.auth.service import get_primary_user
from app.billing import adapty as adapty_billing

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


def _extract_revenue(props: dict) -> Optional[float]:
    """Best-effort revenue amount from an Adapty webhook payload.

    Adapty property names vary by app config, so we probe the common ones and
    a nested ``price`` object. Returns ``None`` when nothing usable is found.
    """
    for key in ("revenue_usd", "price_usd", "proceeds_usd", "net_revenue_usd", "price", "revenue", "proceeds"):
        val = props.get(key)
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val)
            except ValueError:
                continue
        if isinstance(val, dict):
            for sub in ("amount", "value", "usd"):
                sv = val.get(sub)
                if isinstance(sv, (int, float)):
                    return float(sv)
                if isinstance(sv, str):
                    try:
                        return float(sv)
                    except ValueError:
                        continue
    return None


def _mirror_adapty_to_posthog(*, account_id: int, event_type: str, result: str,
                              plan_id: str, props: dict) -> None:
    """Emit the App Store subscription event to PostHog so IAP revenue lands in
    the same funnels/LTV as the web + Telegram paths.

    distinct_id = account_id — the mobile app identifies PostHog with the same
    value (``phIdentify(String(account_id))``), so events collapse onto the
    correct person. Silent on any failure; analytics never blocks billing.
    """
    et = (event_type or "").lower()
    ph_event: Optional[str] = None
    if result == "active":
        if "trial" in et:
            ph_event = "trial_started"
        elif "renew" in et:
            ph_event = "subscription_renewed"
        else:
            ph_event = "subscription_purchased"
    elif result == "cancelled":
        ph_event = "subscription_cancelled"
    elif result == "refund":
        ph_event = "subscription_refunded"
    elif result == "expiration":
        ph_event = "subscription_expired"
    if not ph_event:
        return

    properties: dict = {"plan_id": plan_id, "provider": "adapty",
                        "store": props.get("store") or "app_store"}
    revenue = _extract_revenue(props)
    if revenue is not None:
        properties["revenue"] = revenue
        properties["currency"] = props.get("currency") or props.get("price_currency") or "USD"

    posthog_client.capture(
        ph_event,
        posthog_distinct_id=str(account_id),
        properties=properties,
        set_properties={"subscription_provider": "adapty", "subscription_plan_id": plan_id},
    )


def _verify_secret(authorization: Optional[str]) -> None:
    secret = settings.adapty_webhook_secret
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Adapty webhook not configured")
    # Accept either the bare secret or a "Bearer <secret>" form.
    provided = (authorization or "").strip()
    if provided.lower().startswith("bearer "):
        provided = provided.split(" ", 1)[1].strip()
    if provided != secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")


def _parse_dt(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Heuristic: ms vs s since epoch.
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        s = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _map_plan_id(vendor_product_id: Optional[str]) -> str:
    vid = vendor_product_id or ""
    if settings.adapty_product_yearly and vid == settings.adapty_product_yearly:
        return "yearly"
    if settings.adapty_product_monthly and vid == settings.adapty_product_monthly:
        return "monthly"
    if settings.adapty_product_weekly and vid == settings.adapty_product_weekly:
        return "weekly"
    # Fall back on a substring hint, else monthly.
    low = vid.lower()
    if "year" in low or "annual" in low:
        return "yearly"
    if "week" in low:
        return "weekly"
    return "monthly"


@router.post("/webhooks/adapty")
async def adapty_webhook(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    _verify_secret(authorization)

    raw = await request.body()
    try:
        body = json.loads(raw.decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_type = (body.get("event_type") or body.get("event") or "").strip()
    props = body.get("event_properties") or body.get("data") or {}
    if not isinstance(props, dict):
        props = {}

    customer_user_id = (
        body.get("customer_user_id")
        or props.get("customer_user_id")
        or (body.get("profile") or {}).get("customer_user_id")
    )
    if not customer_user_id:
        logger.warning("[ADAPTY] webhook missing customer_user_id event=%s", event_type)
        return {"status": "ignored", "reason": "no customer_user_id"}

    try:
        account_id = int(customer_user_id)
    except (TypeError, ValueError):
        logger.warning("[ADAPTY] non-numeric customer_user_id=%r", customer_user_id)
        return {"status": "ignored", "reason": "bad customer_user_id"}

    account = db.query(Account).filter(Account.id == account_id).first()
    if account is None:
        logger.warning("[ADAPTY] no account for customer_user_id=%s", account_id)
        return {"status": "ignored", "reason": "account not found"}

    user = get_primary_user(db, account)
    db.commit()

    vendor_product_id = props.get("vendor_product_id") or props.get("product_id")
    plan_id = _map_plan_id(vendor_product_id)
    expires_at = _parse_dt(
        props.get("subscription_expires_at")
        or props.get("expires_at")
        or props.get("subscription_expires_at_iso")
    )
    transaction_id = (
        props.get("transaction_id")
        or props.get("store_transaction_id")
        or props.get("original_transaction_id")
    )
    raw_payload = raw.decode("utf-8", errors="replace")[:8000]

    et = event_type.lower()
    if "refund" in et:
        result = adapty_billing.revoke(db, user, event_type="refund", transaction_id=transaction_id, raw_payload=raw_payload)
    elif "expir" in et:
        result = adapty_billing.revoke(db, user, event_type="expiration", transaction_id=transaction_id, raw_payload=raw_payload)
    elif "cancel" in et:
        result = adapty_billing.cancel(db, user, transaction_id=transaction_id, raw_payload=raw_payload)
    elif expires_at is not None:
        result = adapty_billing.grant_or_extend(
            db, user, plan_id=plan_id, expires_at=expires_at,
            transaction_id=transaction_id, event_type=event_type or "purchase", raw_payload=raw_payload,
        )
    else:
        logger.info("[ADAPTY] event=%s had no actionable expiry; ignored (account_id=%s)", event_type, account_id)
        result = "ignored"

    # Mirror the billing outcome to PostHog (revenue / funnel). Never let an
    # analytics hiccup fail the webhook — Adapty would retry and we'd double
    # process the entitlement.
    try:
        _mirror_adapty_to_posthog(
            account_id=account_id, event_type=event_type, result=result,
            plan_id=plan_id, props=props,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("[ADAPTY] posthog mirror failed: %s", exc)

    return {"status": result, "account_id": account_id, "event_type": event_type}
