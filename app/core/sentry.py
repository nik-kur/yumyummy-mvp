"""Lightweight Sentry initializer used by both the FastAPI backend and the Telegram bot worker.

Reads SENTRY_DSN (and friends) from settings. If the DSN is unset, this is a
no-op so local development and CI keep working without any extra configuration.
"""

from __future__ import annotations

import logging
import os

from app.core.config import settings

logger = logging.getLogger(__name__)


def init_sentry(component: str) -> None:
    """Initialize Sentry for a given component (e.g. "backend", "bot").

    Safe to call multiple times — Sentry's SDK guards against double init.
    """
    dsn = settings.sentry_dsn
    if not dsn:
        logger.info("[SENTRY] SENTRY_DSN not set; Sentry disabled for component=%s", component)
        return

    try:
        import sentry_sdk
    except ImportError:
        logger.warning("[SENTRY] sentry-sdk not installed; skipping init for component=%s", component)
        return

    environment = (
        settings.sentry_environment
        or os.environ.get("RENDER_SERVICE_NAME")
        or "production"
    )

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            send_default_pii=True,
            traces_sample_rate=settings.sentry_traces_sample_rate,
        )
        sentry_sdk.set_tag("component", component)
        logger.info(
            "[SENTRY] Initialized component=%s environment=%s traces_sample_rate=%s",
            component,
            environment,
            settings.sentry_traces_sample_rate,
        )
    except Exception as exc:  # pragma: no cover — never let Sentry init crash the app
        logger.exception("[SENTRY] Failed to initialize for component=%s: %s", component, exc)
