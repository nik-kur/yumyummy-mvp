"""
Push profile attributes (email, name) to the Adapty profile behind an account.

Adapty Mail can only email a profile that carries an ``email`` attribute, and
the SDK never sets one on its own. The canonical place to do it is the client
(`adapty.updateProfile({ email })` after `identify()`), but that only reaches
people who open the app again — the churned users a win-back campaign exists
for never will. So we mirror the same write from the server, keyed on the
``customer_user_id`` the app already sets to our account id.

Requires ``ADAPTY_SERVER_API_KEY``; without it every call here is a no-op.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.billing.adapty_sync import ADAPTY_PROFILE_URL

logger = logging.getLogger(__name__)


def _split_name(display_name: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Apple hands us one "Given Family" string; Adapty wants the two halves."""
    parts = (display_name or "").strip().split()
    if not parts:
        return None, None
    return parts[0], (" ".join(parts[1:]) or None)


def push_profile_attributes(
    account_id: int,
    *,
    email: Optional[str],
    display_name: Optional[str] = None,
    timeout: float = 10.0,
) -> bool:
    """PATCH email/name onto the account's Adapty profile. Returns success.

    Safe to call repeatedly — the request is idempotent, and a 404 just means
    ``identify()`` hasn't reached Adapty yet (the next call will land).
    """
    api_key = settings.adapty_server_api_key
    if not api_key or not email:
        return False

    first_name, last_name = _split_name(display_name)
    body: dict[str, Any] = {"email": email}
    if first_name:
        body["first_name"] = first_name
    if last_name:
        body["last_name"] = last_name

    try:
        resp = httpx.patch(
            ADAPTY_PROFILE_URL,
            headers={
                "Authorization": f"Api-Key {api_key}",
                "Content-Type": "application/json",
                "adapty-customer-user-id": str(account_id),
            },
            json=body,
            timeout=timeout,
        )
    except httpx.HTTPError:
        logger.exception("[ADAPTY_PROFILE] request failed account=%s", account_id)
        return False

    if resp.status_code == 404:
        logger.info("[ADAPTY_PROFILE] no profile yet for account=%s", account_id)
        return False
    if resp.status_code >= 400:
        logger.warning(
            "[ADAPTY_PROFILE] API %s account=%s body=%s",
            resp.status_code, account_id, resp.text[:300],
        )
        return False

    logger.info("[ADAPTY_PROFILE] email synced account=%s", account_id)
    return True
