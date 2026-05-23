"""Server-side fetch helper for landing_attribution rows.

The Meta CAPI / TikTok EAPI clients call ``fetch_landing_attribution(phid)``
to recover the visitor's ``fbp`` / ``fbc`` / ``ip`` / ``user_agent`` /
landing URL captured when they first hit yumyummy.ai. This is a strict
superset of what we used to pull from PostHog's Persons API plus the
fields PostHog can't reliably surface (``$ip`` is event-scoped, not
person-scoped, so PostHog returns null for it via the Persons API).

Same in-process cache shape as :mod:`posthog_persons`: short TTL on
empty results so a CAPI call that races the ``POST /landing-attribution``
write doesn't get permanently pinned to an empty dict; longer TTL once
we have data so we don't beat on the DB for every subsequent CAPI event
for the same user.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple

from app.db.session import SessionLocal
from app.models.landing_attribution import LandingAttribution

logger = logging.getLogger(__name__)


_CACHE_TTL_SECONDS = 30 * 60
# If the LP push hasn't landed yet, retry quickly so the next CAPI event
# (StartTrial, Subscribe) for the same user gets a fresh chance to pick
# up the now-populated row. Mirrors posthog_persons._EMPTY_CACHE_TTL_SECONDS.
_EMPTY_CACHE_TTL_SECONDS = 60

_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def fetch_landing_attribution(phid: Optional[str]) -> Dict[str, Optional[str]]:
    """Return the captured attribution row for ``phid`` as a flat dict.

    Output keys (any value can be ``None``):

    ``fbp``, ``fbc``, ``fbclid``, ``ttp``, ``ttclid``,
    ``ip``, ``user_agent``, ``landing_url``,
    ``utm_source``, ``utm_medium``, ``utm_campaign``,
    ``utm_term``, ``utm_content``

    Returns an empty dict if ``phid`` is falsy, no row exists, or the DB
    lookup raises (the function is deliberately infallible — analytics
    must never block the user-facing flow).
    """
    if not phid:
        return {}

    now = time.time()
    cached = _cache.get(phid)
    if cached:
        cached_at, cached_props = cached
        ttl = _CACHE_TTL_SECONDS if cached_props else _EMPTY_CACHE_TTL_SECONDS
        if (now - cached_at) < ttl:
            return cached_props

    props: Dict[str, Optional[str]] = {}
    db = SessionLocal()
    try:
        row = (
            db.query(LandingAttribution)
            .filter(LandingAttribution.phid == phid)
            .first()
        )
        if row is not None:
            props = {
                "fbp": row.fbp,
                "fbc": row.fbc,
                "fbclid": row.fbclid,
                "ttp": row.ttp,
                "ttclid": row.ttclid,
                "ip": row.ip,
                "user_agent": row.user_agent,
                "landing_url": row.landing_url,
                "utm_source": row.utm_source,
                "utm_medium": row.utm_medium,
                "utm_campaign": row.utm_campaign,
                "utm_term": row.utm_term,
                "utm_content": row.utm_content,
            }
    except Exception as exc:
        logger.debug("[landing-attr] lookup failed for %s: %s", phid, exc)
        return {}
    finally:
        db.close()

    _cache[phid] = (now, props)
    return props


def invalidate_cache(phid: Optional[str]) -> None:
    """Drop the cached row for ``phid``.

    Called right after we UPSERT a fresh row so the next CAPI lookup for
    this user picks up the freshly-written data instead of the negative
    cache from the lookup that ran while the row didn't yet exist.
    """
    if not phid:
        return
    _cache.pop(phid, None)
