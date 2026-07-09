"""
Pull subscription state from Adapty Server API for billing reconciliation.

Called after ``identifyAdapty(account_id)`` in the mobile app to close the gap
where a purchase happened on an anonymous Adapty profile and the webhook arrived
before the profile was identified (so customer_user_id was missing and the
webhook was ignored).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.account import Account
from app.billing import adapty as adapty_billing

logger = logging.getLogger(__name__)

ADAPTY_API_BASE = "https://api.adapty.io/api/v2/server-side-api"


def _map_vendor_product_to_plan(vendor_product_id: str) -> str:
    vid = vendor_product_id or ""
    if settings.adapty_product_yearly and vid == settings.adapty_product_yearly:
        return "yearly"
    if settings.adapty_product_monthly and vid == settings.adapty_product_monthly:
        return "monthly"
    if settings.adapty_product_weekly and vid == settings.adapty_product_weekly:
        return "weekly"
    low = vid.lower()
    if "year" in low or "annual" in low:
        return "yearly"
    if "week" in low:
        return "weekly"
    return "monthly"


def _parse_iso(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        s = raw.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def sync_from_adapty(db: Session, user: User, account: Account) -> None:
    """Pull the Adapty profile and, if there's an active subscription we don't
    have locally, grant it."""
    api_key = settings.adapty_server_api_key
    if not api_key:
        logger.debug("[ADAPTY_SYNC] no server API key configured, skipping")
        return

    customer_user_id = str(account.id)
    try:
        resp = httpx.get(
            f"{ADAPTY_API_BASE}/profiles/{customer_user_id}/",
            headers={"Authorization": f"Api-Key {api_key}"},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning("[ADAPTY_SYNC] API %s for account %s", resp.status_code, account.id)
            return
        data = resp.json().get("data", {})
    except Exception:
        logger.exception("[ADAPTY_SYNC] failed to reach Adapty API for account %s", account.id)
        return

    paid_access = data.get("paid_access_levels", {})
    premium = paid_access.get("premium", {})
    if not premium.get("is_active"):
        return

    vendor_product_id = premium.get("vendor_product_id", "")
    expires_raw = premium.get("expires_at") or premium.get("renewed_at")
    expires_at = _parse_iso(expires_raw)
    if not expires_at:
        return

    if user.subscription_ends_at and user.subscription_ends_at >= expires_at:
        return

    plan_id = _map_vendor_to_plan(vendor_product_id)
    auto_renew = premium.get("will_renew", True)
    store_transaction_id = premium.get("store_transaction_id")

    adapty_billing.grant_or_extend(
        db, user,
        plan_id=plan_id,
        expires_at=expires_at,
        auto_renew=auto_renew,
        transaction_id=store_transaction_id,
        event_type="sync",
        raw_payload=None,
    )
    logger.info(
        "[ADAPTY_SYNC] granted entitlement account=%s plan=%s until=%s",
        account.id, plan_id, expires_at,
    )


def _map_vendor_to_plan(vendor_product_id: str) -> str:
    return _map_vendor_product_to_plan(vendor_product_id)
