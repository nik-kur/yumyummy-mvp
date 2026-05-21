"""Meta Conversions API client for server-side conversion tracking.

The browser Meta Pixel installed on yumyummy.ai sees ``PageView``
and ``Lead`` (CTA click) — but the actual signup, trial start, and
subscription purchase happen inside the Telegram bot, where the
pixel can't reach.

This module bridges that gap by sending those server-side events
(``CompleteRegistration``, ``StartTrial``, ``Subscribe``) straight
to Meta with the user's ``$fbp`` / ``$fbc`` pulled from their
PostHog person profile via :mod:`posthog_persons`. That gives
Meta's ads algorithm a real-money signal to optimize toward,
instead of only optimizing for clicks. It also recovers the ~30-50%
of attribution that iOS 14.5+ ITP and ad-blockers strip from the
browser pixel alone.

Mirror-image of :mod:`tiktok_events_client` — silent no-op if not
configured, swallows exceptions so the analytics layer never blocks
the user-facing flow. The HTTP call runs in a daemon thread so a
slow Meta response can't push a Paddle webhook past its 10-second
budget.

Reference: https://developers.facebook.com/docs/marketing-api/conversions-api
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.core.posthog_persons import fetch_device_context, fetch_pixel_ids

logger = logging.getLogger(__name__)


# action_source = "website" tells Meta this conversion was triggered
# by a customer interaction on a website (the LP CTA click that drove
# them into the bot). Even though the actual /start happens in
# Telegram, the originating action was the website click — using
# "website" lets Meta stitch the conversion back to the LP pageview
# the browser pixel already captured.
_ACTION_SOURCE = "website"
_EVENT_SOURCE_URL = "https://yumyummy.ai/"


def _enabled() -> bool:
    return bool(
        settings.meta_pixel_id and settings.meta_access_token
    )


def _api_url() -> str:
    return (
        f"https://graph.facebook.com/{settings.meta_api_version}/"
        f"{settings.meta_pixel_id}/events"
    )


def _sha256(value: str) -> str:
    """SHA-256 lower-cased trimmed value, per Meta's PII matching spec."""
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def _build_event_id(event_kind: str, user_id: int, suffix: str = "") -> str:
    """Stable id used for browser/server dedup.

    For events that only fire server-side (CompleteRegistration,
    StartTrial, Subscribe) the id only needs to be unique per
    occurrence. user_id keeps multiple users from colliding; the
    optional suffix (e.g. ``"first"`` / ``"renew_<ts>"``) keeps
    repeated events for the same user from deduping against each
    other.
    """
    parts = ["yy", event_kind, str(user_id)]
    if suffix:
        parts.append(str(suffix))
    return ":".join(parts)


def _post_event_blocking(body: Dict[str, Any], event: str) -> None:
    """The actual HTTPS call. Runs inside the dispatcher thread."""
    try:
        resp = httpx.post(
            _api_url(),
            json=body,
            params={"access_token": settings.meta_access_token},
            headers={"Content-Type": "application/json"},
            timeout=4.0,
        )
        if resp.status_code >= 300:
            logger.warning(
                "[meta-capi] %s -> HTTP %s %s",
                event, resp.status_code, resp.text[:300],
            )
            return
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        # Successful CAPI calls return {"events_received": 1, ...}.
        # Anything else is a logical error (bad payload, expired
        # token, deactivated pixel, etc).
        if not payload.get("events_received"):
            logger.warning("[meta-capi] %s -> unexpected response %s", event, payload)
            return
        logger.info("[meta-capi] %s sent OK", event)
    except Exception as exc:
        logger.debug("[meta-capi] %s send failed: %s", event, exc)


def _send(
    *,
    event_name: str,
    event_id: str,
    user_id: int,
    posthog_distinct_id: Optional[str],
    telegram_id: Optional[str],
    custom_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Build the CAPI payload and dispatch it in a daemon thread."""
    if not _enabled():
        return

    pixel_ids = fetch_pixel_ids(posthog_distinct_id)
    device_ctx = fetch_device_context(posthog_distinct_id)
    external_id_raw = posthog_distinct_id or (
        f"tg_{telegram_id}" if telegram_id else None
    )

    user_data: Dict[str, Any] = {}
    if external_id_raw:
        # Meta accepts either a single string or an array. Single
        # string is fine for one identifier.
        user_data["external_id"] = _sha256(external_id_raw)
    if pixel_ids.get("fbp"):
        user_data["fbp"] = pixel_ids["fbp"]
    if pixel_ids.get("fbc"):
        user_data["fbc"] = pixel_ids["fbc"]
    # IP + UA lift Event Match Quality by ~2-3 points each — Meta's
    # spec recommends them as the primary cross-device identifiers
    # when hashed PII (email/phone) isn't available. Captured by the
    # LP pixel and stashed on the PostHog person profile.
    if device_ctx.get("ip"):
        user_data["client_ip_address"] = device_ctx["ip"]
    if device_ctx.get("user_agent"):
        user_data["client_user_agent"] = device_ctx["user_agent"]

    # Prefer the actual landing URL (with UTMs + fbclid) over the
    # hard-coded homepage so Meta can stitch the conversion to the
    # exact ad click. Falls back to "/" for users we have no LP touch
    # for (rare — bot-only acquisition without web visit).
    source_url = device_ctx.get("event_source_url") or _EVENT_SOURCE_URL

    event_obj: Dict[str, Any] = {
        "event_name": event_name,
        "event_time": int(time.time()),
        "event_id": event_id,
        "action_source": _ACTION_SOURCE,
        "event_source_url": source_url,
        "user_data": user_data,
    }
    if custom_data:
        event_obj["custom_data"] = custom_data

    body: Dict[str, Any] = {"data": [event_obj]}
    if settings.meta_capi_test_event_code:
        body["test_event_code"] = settings.meta_capi_test_event_code

    threading.Thread(
        target=_post_event_blocking,
        args=(body, event_name),
        daemon=True,
        name=f"meta-capi-{event_name}",
    ).start()


# ---------------------------------------------------------------------------
# Public helpers — one per business event, mirroring tiktok_events_client
# ---------------------------------------------------------------------------


def send_complete_registration(
    *,
    user_id: int,
    telegram_id: Optional[str],
    posthog_distinct_id: Optional[str],
    acquisition_source: Optional[str] = None,
) -> None:
    """Fire when a new user runs ``/start`` for the very first time.

    Maps to Meta standard event ``CompleteRegistration``.
    """
    custom: Dict[str, Any] = {"content_category": "subscription"}
    if acquisition_source:
        custom["content_name"] = acquisition_source
    _send(
        event_name="CompleteRegistration",
        event_id=_build_event_id("registration", user_id),
        user_id=user_id,
        posthog_distinct_id=posthog_distinct_id,
        telegram_id=telegram_id,
        custom_data=custom,
    )


def send_start_trial(
    *,
    user_id: int,
    telegram_id: Optional[str],
    posthog_distinct_id: Optional[str],
    trial_days: int,
) -> None:
    """Fire when ``/billing/trial/start`` succeeds.

    Maps to Meta standard event ``StartTrial``.
    """
    _send(
        event_name="StartTrial",
        event_id=_build_event_id("trial", user_id),
        user_id=user_id,
        posthog_distinct_id=posthog_distinct_id,
        telegram_id=telegram_id,
        custom_data={
            "value": 0,
            "currency": "USD",
            "predicted_ltv": 0,
            "content_ids": [f"trial_{trial_days}d"],
            "content_type": "product",
        },
    )


def send_subscribe(
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

    Maps to Meta standard event ``Subscribe``. Meta uses ``Subscribe``
    for recurring revenue (vs ``Purchase`` for one-time). ``value`` is
    USD revenue; for Telegram-Stars-paid subs without a USD
    equivalent we fall back to 0 so the event still counts as a
    conversion.
    """
    suffix = "first" if is_first_payment else f"renew_{int(time.time())}"
    _send(
        event_name="Subscribe",
        event_id=_build_event_id("subscribe", user_id, suffix=suffix),
        user_id=user_id,
        posthog_distinct_id=posthog_distinct_id,
        telegram_id=telegram_id,
        custom_data={
            "value": revenue_usd if revenue_usd is not None else 0,
            "currency": (currency or "USD").upper(),
            "content_ids": [plan_id or "subscription"],
            "content_type": "product",
            "predicted_ltv": revenue_usd if revenue_usd is not None else 0,
        },
    )
