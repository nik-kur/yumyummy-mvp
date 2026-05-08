"""PostHog backend integration for YumYummy.

This module exposes a single ``capture()`` helper that backend code
(``main.py``, the bot, the Paddle/Gumroad webhooks) uses to record
funnel events for a given Telegram user. It is intentionally tiny:

- If ``settings.posthog_api_key`` is unset (e.g. local dev), every call
  is a silent no-op so feature code never has to ``if posthog_enabled:``
  itself.
- We pick the user's PostHog ``distinct_id`` first (so events land on
  the same person profile created by the marketing site), and fall
  back to ``tg_<telegram_id>`` so the events are still attributable
  even for users acquired before we deployed the LP→bot identity link.
- All key acquisition properties (``acquisition_source``, UTMs once we
  store them, plan, provider) are sent on every event as event
  properties — PostHog will also resolve them as person properties on
  the first event via ``$set``.

The wrapper swallows all PostHog exceptions: analytics never blocks a
user-facing flow.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


_client = None
_initialized = False


def _get_client():
    """Lazy-init the PostHog client on first use."""
    global _client, _initialized
    if _initialized:
        return _client
    _initialized = True
    if not settings.posthog_api_key:
        logger.info("[posthog] disabled (no POSTHOG_API_KEY set)")
        return None
    try:
        from posthog import Posthog  # type: ignore

        _client = Posthog(
            project_api_key=settings.posthog_api_key,
            host=settings.posthog_host,
        )
        logger.info("[posthog] initialised host=%s", settings.posthog_host)
    except Exception as exc:
        logger.warning("[posthog] failed to initialise: %s", exc)
        _client = None
    return _client


def _resolve_distinct_id(
    *,
    telegram_id: Optional[str],
    posthog_distinct_id: Optional[str],
) -> Optional[str]:
    if posthog_distinct_id:
        return posthog_distinct_id
    if telegram_id:
        return f"tg_{telegram_id}"
    return None


def capture(
    event: str,
    *,
    telegram_id: Optional[str] = None,
    posthog_distinct_id: Optional[str] = None,
    properties: Optional[Dict[str, Any]] = None,
    set_properties: Optional[Dict[str, Any]] = None,
) -> None:
    """Send an event to PostHog. Silent on failure / when disabled.

    Args:
        event: Event name, e.g. ``"trial_started"``.
        telegram_id: User's Telegram ID; used as fallback distinct_id.
        posthog_distinct_id: Web-side PostHog distinct_id, preferred so
            web pageviews and bot events live on the same person.
        properties: Event properties.
        set_properties: ``$set`` payload — propagated to person
            properties (e.g. ``acquisition_source``) so cohorts and
            breakdowns work without joining tables.
    """
    client = _get_client()
    if client is None:
        return

    distinct_id = _resolve_distinct_id(
        telegram_id=telegram_id,
        posthog_distinct_id=posthog_distinct_id,
    )
    if not distinct_id:
        logger.debug("[posthog] capture(%s) skipped — no distinct_id", event)
        return

    props: Dict[str, Any] = dict(properties or {})
    if telegram_id:
        props.setdefault("telegram_id", telegram_id)
    if set_properties:
        props["$set"] = set_properties

    try:
        client.capture(
            distinct_id=distinct_id,
            event=event,
            properties=props,
        )
        # If the bot has a "real" PostHog distinct_id from the LP, also
        # alias the Telegram-only id so historical bot-only events
        # collapse into the same person.
        if posthog_distinct_id and telegram_id:
            try:
                client.alias(
                    previous_id=f"tg_{telegram_id}",
                    distinct_id=posthog_distinct_id,
                )
            except Exception:
                pass
    except Exception as exc:
        logger.debug("[posthog] capture(%s) failed: %s", event, exc)


def shutdown() -> None:
    """Flush pending events on graceful shutdown."""
    if _client is None:
        return
    try:
        _client.shutdown()
    except Exception:
        pass
