"""
Pull subscription state from Adapty Server API for billing reconciliation.

Our acquisition funnel lets people buy *before* they sign in, so the purchase
lands on an anonymous Adapty profile. Adapty's webhook then arrives with no
``customer_user_id`` and we cannot map it to an account (see
``app/api/adapty_webhook.py``). This module closes that gap: once the user signs
in, the app calls ``/app/billing/sync`` and we read the entitlement straight
from Adapty.

Lookup order matters. ``adapty-customer-user-id`` only resolves after
``adapty.identify()`` has propagated, so we fall back to ``adapty-profile-id``
(the app sends the id it read from the local SDK), which resolves anonymous
profiles too.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.account import Account
from app.billing import adapty as adapty_billing

logger = logging.getLogger(__name__)

ADAPTY_PROFILE_URL = "https://api.adapty.io/api/v2/server-side-api/profile/"
PREMIUM_ACCESS_LEVEL = "premium"


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
    except (ValueError, AttributeError):
        return None


def _get_profile(api_key: str, header: str, value: str) -> Optional[dict[str, Any]]:
    """One Adapty profile lookup. Returns the ``data`` object, or None."""
    try:
        resp = httpx.get(
            ADAPTY_PROFILE_URL,
            headers={
                "Authorization": f"Api-Key {api_key}",
                "Accept": "application/json",
                header: value,
            },
            timeout=10,
        )
    except httpx.HTTPError:
        logger.exception("[ADAPTY_SYNC] request failed for %s=%s", header, value)
        return None

    if resp.status_code == 404:
        logger.info("[ADAPTY_SYNC] no profile for %s=%s", header, value)
        return None
    if resp.status_code != 200:
        logger.warning(
            "[ADAPTY_SYNC] API %s for %s=%s body=%s",
            resp.status_code, header, value, resp.text[:300],
        )
        return None

    try:
        return resp.json().get("data") or {}
    except ValueError:
        logger.warning("[ADAPTY_SYNC] non-JSON body for %s=%s", header, value)
        return None


def _premium_level(data: dict[str, Any]) -> Optional[dict[str, Any]]:
    """The active `premium` entry from the v2 `access_levels` array, if any.

    A null `expires_at` means lifetime access. `renewal_cancelled_at` does not
    revoke anything — access runs until it expires.
    """
    now = datetime.now(timezone.utc)
    for level in data.get("access_levels") or []:
        if level.get("access_level_id") != PREMIUM_ACCESS_LEVEL:
            continue
        starts_at = _parse_iso(level.get("starts_at"))
        if starts_at and starts_at > now:
            continue
        expires_at = _parse_iso(level.get("expires_at"))
        if expires_at is None or expires_at > now:
            return level
    return None


def sync_from_adapty(
    db: Session,
    user: User,
    account: Account,
    adapty_profile_id: Optional[str] = None,
) -> bool:
    """Grant the Adapty entitlement locally when we're missing it.

    Returns whether anything was granted.
    """
    api_key = settings.adapty_server_api_key
    if not api_key:
        logger.debug("[ADAPTY_SYNC] no server API key configured, skipping")
        return False

    data = _get_profile(api_key, "adapty-customer-user-id", str(account.id))
    if data is None and adapty_profile_id:
        # identify() hasn't propagated (or never ran) — resolve the anonymous
        # profile the purchase actually landed on.
        data = _get_profile(api_key, "adapty-profile-id", adapty_profile_id)
    if data is None:
        return False

    premium = _premium_level(data)
    if premium is None:
        return False

    expires_at = _parse_iso(premium.get("expires_at"))
    if expires_at is None:
        # Lifetime access: park the entitlement far enough out that it never
        # lapses, since our columns can't express "no expiry".
        expires_at = datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 100)

    if user.subscription_ends_at:
        current = user.subscription_ends_at
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        if current >= expires_at:
            return False

    offer = premium.get("offer") or {}
    result = adapty_billing.grant_or_extend(
        db, user,
        plan_id=_map_vendor_product_to_plan(premium.get("store_product_id") or ""),
        expires_at=expires_at,
        auto_renew=premium.get("renewal_cancelled_at") is None,
        transaction_id=premium.get("store_transaction_id"),
        event_type="sync",
        raw_payload=None,
        is_trial=offer.get("type") == "free_trial",
        purchased_at=_parse_iso(premium.get("purchased_at")),
    )
    logger.info(
        "[ADAPTY_SYNC] %s account=%s until=%s profile_id=%s",
        result, account.id, expires_at, data.get("profile_id"),
    )
    return result == "active"
