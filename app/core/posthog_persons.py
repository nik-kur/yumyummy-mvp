"""PostHog Persons API client for fetching person properties.

Used by the ad-platform server-side bridges (TikTok Events API,
Meta Conversions API) to retrieve the pixel identifiers that the
landing page stashed on the user's PostHog person profile:

    $ttp     — TikTok browser id (from `_ttp` cookie)
    $ttclid  — TikTok click id (from `?ttclid=` URL param)
    $fbp     — Meta browser id (from `_fbp` cookie)
    $fbc     — Meta click id (from `?fbclid=` URL param)

Flow:
    1. LP captures these cookies/params into PostHog via
       posthog.register() / posthog.setPersonProperties().
    2. User clicks the bot link, /start fires, our backend stores the
       same posthog_distinct_id on `users.posthog_distinct_id`.
    3. When the user signs up / starts a trial / buys a subscription,
       we fetch their person properties here, pull out the pixel IDs,
       and forward them to TikTok/Meta server-side APIs.

Implementation notes:

  - Reads via the project-scoped `/api/projects/<id>/persons/`
    endpoint, filtered by `distinct_id`. Requires a *personal* API
    key (different from the project ingestion key used to capture
    events).
  - Hostname: PostHog ingestion runs on `eu.i.posthog.com` while the
    REST API runs on `eu.posthog.com`. We translate automatically.
  - Result is cached in-process with a 30-min TTL keyed by
    distinct_id. The same user is queried multiple times during
    their lifecycle (bot_started → trial_started → subscription_
    purchased) and pixel IDs effectively never change.
  - The lookup is best-effort: any failure (missing key, rate limit,
    network blip, person not yet visible) is swallowed and logged at
    debug level. Ad attribution is non-critical compared to the
    user-facing flow.

PostHog person properties are eventually consistent: a user who just
hit the LP and bounced into the bot may not yet be visible via this
endpoint (10-30s lag). The downstream EAPI/CAPI clients should
gracefully degrade by sending the event without `ttp`/`fbp` — TikTok
and Meta will still match by `external_id` if provided.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30 * 60
_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _api_base() -> str:
    """Resolve the REST API host from the configured ingestion host."""
    host = (settings.posthog_host or "https://eu.i.posthog.com").rstrip("/")
    return host.replace(".i.posthog.com", ".posthog.com")


def _enabled() -> bool:
    return bool(
        settings.posthog_personal_api_key and settings.posthog_project_id
    )


def fetch_person_properties(distinct_id: str) -> Dict[str, Any]:
    """Return PostHog ``person.properties`` for ``distinct_id``.

    Returns an empty dict if the lookup fails for any reason — the
    function is intentionally infallible so feature code can call it
    inline without try/except.
    """
    if not distinct_id or not _enabled():
        return {}

    now = time.time()
    cached = _cache.get(distinct_id)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    url = f"{_api_base()}/api/projects/{settings.posthog_project_id}/persons/"
    try:
        resp = httpx.get(
            url,
            params={"distinct_id": distinct_id},
            headers={
                "Authorization": f"Bearer {settings.posthog_personal_api_key}"
            },
            timeout=3.0,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        results = data.get("results") or []
        props = (results[0] or {}).get("properties") or {} if results else {}
    except Exception as exc:
        logger.debug(
            "[posthog-persons] lookup failed for %s: %s", distinct_id, exc
        )
        return {}

    _cache[distinct_id] = (now, props)
    logger.debug(
        "[posthog-persons] cached %d props for %s", len(props), distinct_id
    )
    return props


def fetch_pixel_ids(distinct_id: Optional[str]) -> Dict[str, Optional[str]]:
    """Convenience wrapper returning just the ad-platform IDs.

    Output shape (any field can be ``None``)::

        {"ttp": "...", "ttclid": "...", "fbp": "...", "fbc": "..."}
    """
    empty = {"ttp": None, "ttclid": None, "fbp": None, "fbc": None}
    if not distinct_id:
        return empty
    props = fetch_person_properties(distinct_id)
    if not props:
        return empty
    return {
        "ttp": props.get("$ttp"),
        "ttclid": props.get("$ttclid"),
        "fbp": props.get("$fbp"),
        "fbc": props.get("$fbc"),
    }


def fetch_device_context(distinct_id: Optional[str]) -> Dict[str, Optional[str]]:
    """Return device + landing context PostHog stashed for this person.

    Meta CAPI / TikTok EAPI use these to lift Event Match Quality:

      - ``client_ip_address``: PostHog stores the visitor IP as ``$ip``
        on the person profile (from the ingestion request that captured
        their pageview). Meta dedupes & cross-references it.
      - ``client_user_agent``: stashed by ``analytics.js`` as
        ``raw_user_agent`` because PostHog's auto-captured fields parse
        the UA but don't keep the raw string.
      - ``event_source_url``: the actual landing URL with UTMs / fbclid,
        not the hard-coded homepage default.

    Output shape (any field can be ``None``)::

        {"ip": "...", "user_agent": "...", "event_source_url": "..."}
    """
    empty: Dict[str, Optional[str]] = {
        "ip": None,
        "user_agent": None,
        "event_source_url": None,
    }
    if not distinct_id:
        return empty
    props = fetch_person_properties(distinct_id)
    if not props:
        return empty
    return {
        "ip": props.get("$ip"),
        "user_agent": props.get("raw_user_agent") or props.get("$raw_user_agent"),
        "event_source_url": (
            props.get("initial_landing_url")
            or props.get("$initial_current_url")
            or props.get("$current_url")
        ),
    }
