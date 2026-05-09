"""TikTok Events API client for server-side conversion tracking.

The browser TikTok pixel installed on yumyummy.ai sees ``Pageview``
and ``Lead`` (CTA click) — but the actual signup, trial start, and
subscription purchase happen inside the Telegram bot, where the
pixel can't reach.

This module bridges that gap by sending those server-side events
(``CompleteRegistration``, ``StartTrial``, ``CompletePayment``)
straight to TikTok with the user's ``$ttp`` / ``$ttclid`` pulled
from their PostHog person profile via :mod:`posthog_persons`. That
gives the TikTok ads algorithm a real-money signal to optimize
toward, instead of only optimizing for clicks.

Mirror-image of :mod:`posthog_client` — silent no-op if not
configured, swallows exceptions so the analytics layer never blocks
the user-facing flow. The actual HTTP call runs in a daemon thread
so a slow TikTok response never delays a Paddle webhook past its
10-second budget.

Reference: https://business-api.tiktok.com/portal/docs?id=1771101303285761
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.core.posthog_persons import fetch_pixel_ids

logger = logging.getLogger(__name__)

_TIKTOK_API_URL = "https://business-api.tiktok.com/open_api/v1.3/event/track/"


def _enabled() -> bool:
    return bool(
        settings.tiktok_pixel_code and settings.tiktok_access_token
    )


def _sha256(value: str) -> str:
    """SHA-256 lower-cased trimmed value, per TikTok's PII matching spec."""
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def _build_event_id(event_kind: str, user_id: int, suffix: str = "") -> str:
    """Stable id used for browser/server dedup.

    For events that only fire server-side (CompleteRegistration,
    StartTrial, CompletePayment) the id only needs to be unique per
    occurrence. We include user_id so multiple users don't collide
    and an optional suffix (e.g. unix-time) for repeating events
    like renewals.
    """
    parts = ["yy", event_kind, str(user_id)]
    if suffix:
        parts.append(str(suffix))
    return ":".join(parts)


def _post_event_blocking(body: Dict[str, Any], event: str) -> None:
    """The actual HTTP call. Runs inside the dispatcher thread."""
    try:
        resp = httpx.post(
            _TIKTOK_API_URL,
            json=body,
            headers={
                "Access-Token": settings.tiktok_access_token,
                "Content-Type": "application/json",
            },
            timeout=4.0,
        )
        if resp.status_code >= 300:
            logger.warning(
                "[tiktok-eapi] %s -> HTTP %s %s",
                event, resp.status_code, resp.text[:300],
            )
            return
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        # TikTok returns {"code": 0, "message": "OK", ...} on success;
        # any non-zero code is a logical error.
        if payload.get("code") not in (0, None):
            logger.warning("[tiktok-eapi] %s -> API error %s", event, payload)
            return
        logger.info("[tiktok-eapi] %s sent OK", event)
    except Exception as exc:
        logger.debug("[tiktok-eapi] %s send failed: %s", event, exc)


def _send(
    *,
    event: str,
    event_id: str,
    user_id: int,
    posthog_distinct_id: Optional[str],
    telegram_id: Optional[str],
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    """Build the EAPI payload and dispatch it in a daemon thread."""
    if not _enabled():
        return

    pixel_ids = fetch_pixel_ids(posthog_distinct_id)
    external_id = posthog_distinct_id or (
        f"tg_{telegram_id}" if telegram_id else None
    )

    user_payload: Dict[str, Any] = {}
    if external_id:
        user_payload["external_id"] = [_sha256(external_id)]
    if pixel_ids.get("ttp"):
        user_payload["ttp"] = pixel_ids["ttp"]
    if pixel_ids.get("ttclid"):
        user_payload["ttclid"] = pixel_ids["ttclid"]

    event_data: Dict[str, Any] = {
        "event": event,
        "event_time": int(time.time()),
        "event_id": event_id,
        "user": user_payload,
        "page": {"url": "https://yumyummy.ai/"},
    }
    if properties:
        event_data["properties"] = properties

    body: Dict[str, Any] = {
        "event_source": "web",
        "event_source_id": settings.tiktok_pixel_code,
        "data": [event_data],
    }
    if settings.tiktok_test_event_code:
        body["test_event_code"] = settings.tiktok_test_event_code

    threading.Thread(
        target=_post_event_blocking,
        args=(body, event),
        daemon=True,
        name=f"tiktok-eapi-{event}",
    ).start()


# ---------------------------------------------------------------------------
# Public helpers — one per business event, mirroring posthog_client.capture()
# ---------------------------------------------------------------------------


def send_complete_registration(
    *,
    user_id: int,
    telegram_id: Optional[str],
    posthog_distinct_id: Optional[str],
    acquisition_source: Optional[str] = None,
) -> None:
    """Fire when a new user runs ``/start`` for the very first time.

    Maps to TikTok standard event ``CompleteRegistration``.
    """
    props: Dict[str, Any] = {"content_type": "product"}
    if acquisition_source:
        props["description"] = acquisition_source
    _send(
        event="CompleteRegistration",
        event_id=_build_event_id("registration", user_id),
        user_id=user_id,
        posthog_distinct_id=posthog_distinct_id,
        telegram_id=telegram_id,
        properties=props,
    )


def send_start_trial(
    *,
    user_id: int,
    telegram_id: Optional[str],
    posthog_distinct_id: Optional[str],
    trial_days: int,
) -> None:
    """Fire when ``/billing/trial/start`` succeeds.

    Maps to TikTok standard event ``StartTrial``.
    """
    _send(
        event="StartTrial",
        event_id=_build_event_id("trial", user_id),
        user_id=user_id,
        posthog_distinct_id=posthog_distinct_id,
        telegram_id=telegram_id,
        properties={
            "value": 0,
            "currency": "USD",
            "content_id": f"trial_{trial_days}d",
            "content_type": "product",
        },
    )


def send_complete_payment(
    *,
    user_id: int,
    telegram_id: Optional[str],
    posthog_distinct_id: Optional[str],
    plan_id: Optional[str],
    revenue_usd: Optional[float],
    currency: Optional[str],
    is_first_payment: bool,
) -> None:
    """Fire on a successful (first or recurring) subscription payment.

    Maps to TikTok standard event ``CompletePayment``. ``value`` is
    the USD revenue; for Telegram-Stars-paid subs without a USD
    equivalent we fall back to 0 so the event still counts as a
    conversion (TikTok's algo prioritises *that* a conversion
    happened over its exact USD value when training).
    """
    suffix = "first" if is_first_payment else f"renew_{int(time.time())}"
    _send(
        event="CompletePayment",
        event_id=_build_event_id("payment", user_id, suffix=suffix),
        user_id=user_id,
        posthog_distinct_id=posthog_distinct_id,
        telegram_id=telegram_id,
        properties={
            "value": revenue_usd if revenue_usd is not None else 0,
            "currency": (currency or "USD").upper(),
            "content_id": plan_id or "subscription",
            "content_type": "product",
            "description": (
                "first_subscription" if is_first_payment else "renewal"
            ),
        },
    )
