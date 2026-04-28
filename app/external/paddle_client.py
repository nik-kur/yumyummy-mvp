"""
Minimal Paddle Billing API client.

Used to:
  - Fetch the canonical state of a subscription (current_billing_period.ends_at,
    next_billed_at, status, scheduled_change, ...) when reconciling local DB
    state against Paddle's source of truth.
  - Provide a single place that knows about sandbox vs production base URLs.

Only the read-only endpoints we actually need are wrapped. We deliberately
keep this minimal — Paddle's full surface is large.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


_SANDBOX_BASE = "https://sandbox-api.paddle.com"
_PRODUCTION_BASE = "https://api.paddle.com"


class PaddleAPIError(Exception):
    """Raised when the Paddle API returns an error or is unreachable."""


def paddle_api_base() -> str:
    """Return the correct Paddle API base URL for the current environment."""
    if settings.paddle_environment == "sandbox":
        return _SANDBOX_BASE
    return _PRODUCTION_BASE


def _require_api_key() -> str:
    if not settings.paddle_api_key:
        raise PaddleAPIError("PADDLE_API_KEY not configured")
    return settings.paddle_api_key


def _auth_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_require_api_key()}",
        "Accept": "application/json",
    }


def parse_paddle_datetime(value: Optional[str]) -> Optional[datetime]:
    """
    Parse a Paddle ISO 8601 timestamp into a timezone-aware UTC datetime.

    Paddle returns timestamps like "2026-04-29T12:34:56.123456Z". We accept
    the trailing 'Z' as well as explicit offsets.
    """
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def get_subscription(subscription_id: str) -> Dict[str, Any]:
    """
    GET /subscriptions/{id} — returns the full subscription resource.

    Returns the parsed `data` object on success. Raises PaddleAPIError on
    network/HTTP failure.
    """
    if not subscription_id:
        raise PaddleAPIError("subscription_id is required")

    url = f"{paddle_api_base()}/subscriptions/{subscription_id}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=_auth_headers())
    except httpx.HTTPError as e:
        raise PaddleAPIError(f"Network error contacting Paddle: {e}") from e

    if resp.status_code != 200:
        raise PaddleAPIError(
            f"Paddle returned {resp.status_code} for subscription {subscription_id}: "
            f"{resp.text[:200]}"
        )

    body = resp.json()
    data = body.get("data")
    if not isinstance(data, dict):
        raise PaddleAPIError("Paddle response did not contain a `data` object")
    return data


def extract_period_ends_at(subscription_data: Dict[str, Any]) -> Optional[datetime]:
    """
    Determine the authoritative end-of-current-period timestamp from a Paddle
    subscription resource.

    Order of preference:
      1. `current_billing_period.ends_at` — exact end of paid-for window.
      2. `next_billed_at` — when Paddle will attempt the next charge (for
         active recurring subs this is identical to billing period end).
      3. `scheduled_change.effective_at` — for pending cancel/pause changes.
    """
    period = subscription_data.get("current_billing_period") or {}
    ends_at = parse_paddle_datetime(period.get("ends_at"))
    if ends_at:
        return ends_at

    ends_at = parse_paddle_datetime(subscription_data.get("next_billed_at"))
    if ends_at:
        return ends_at

    scheduled = subscription_data.get("scheduled_change") or {}
    return parse_paddle_datetime(scheduled.get("effective_at"))
