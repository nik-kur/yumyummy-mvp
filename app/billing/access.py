from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

# Per-status spend caps (anti-abuse ceilings, NOT expected budgets — normal
# users cost a small fraction of these). The "new" cap is intentionally tiny —
# it only needs to cover the single onboarding demo meal that runs *before* the
# user activates a trial. Without this, server-side billing enforcement
# on /agent/run would block the demo and the user would see "Your trial
# has ended" during their very first interaction with the bot. Capping
# new users at $0.50 prevents abuse (signing up many fresh accounts to
# burn through agent runs) while keeping the demo a true wow moment.
#
# Trial/active caps were recalibrated for the Agent v2 engine (Jul 2026):
# web-search intents (product/eatout/photo) cost ~$0.04-0.16/run vs the old
# v1 baseline, so the previous $2 / $10 caps throttled legitimate heavy use.
USAGE_CAP_NEW_USD = 0.5
USAGE_CAP_TRIAL_USD = 3.0
USAGE_CAP_ACTIVE_USD = 20.0

# Spend caps apply over a rolling window, NOT the whole billing period. Without
# this a yearly subscriber's meter would only reset once a year, so a burst in
# month one could lock them out for the rest of the term. The DB counter
# (users.usage_cost_current_period / usage_period_start) is rolled lazily on
# the next write in usage_guardrails.record_usage_for_user; here we treat a
# stale window as already reset so the read-side access check agrees.
USAGE_PERIOD_DAYS = 30


def compute_access_status(user: Dict[str, Any]) -> str:
    """
    Compute billing access status from user fields.
    Returns: 'new' | 'trial' | 'active' | 'trial_expired' | 'expired'
    """
    now = datetime.now(timezone.utc)

    sub_ends = _parse_dt(user.get("subscription_ends_at"))
    if sub_ends and sub_ends > now:
        return "active"

    trial_ends = _parse_dt(user.get("trial_ends_at"))
    if trial_ends:
        if trial_ends > now:
            return "trial"
        return "trial_expired"

    if sub_ends:
        return "expired"

    return "new"


def has_access(user: Dict[str, Any]) -> bool:
    """Decide whether the user is allowed to consume an agent run.

    "new" users are allowed a tiny demo budget so the onboarding flow
    works (the first agent call happens *before* the trial CTA). All
    other non-paid statuses are rejected.
    """
    status = compute_access_status(user)
    if status in ("trial", "active", "new"):
        return check_usage_cap(user)
    return False


def get_usage_cap_usd(user: Dict[str, Any]) -> Optional[float]:
    status = compute_access_status(user)
    if status == "new":
        return USAGE_CAP_NEW_USD
    if status == "trial":
        return USAGE_CAP_TRIAL_USD
    if status == "active":
        return USAGE_CAP_ACTIVE_USD
    return None


def effective_period_cost(user: Dict[str, Any]) -> float:
    """Current-period spend, treating a window older than ``USAGE_PERIOD_DAYS``
    as already reset (the DB counter is rolled lazily on the next usage write).
    Keeps the read-side cap check in sync with the write-side reset."""
    start = _parse_dt(user.get("usage_period_start"))
    if start is not None and (datetime.now(timezone.utc) - start) >= timedelta(days=USAGE_PERIOD_DAYS):
        return 0.0
    try:
        return float(user.get("usage_cost_current_period") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def check_usage_cap(user: Dict[str, Any]) -> bool:
    cap = get_usage_cap_usd(user)
    if cap is None:
        return True
    return effective_period_cost(user) < cap


def trial_days_remaining(user: Dict[str, Any]) -> float:
    trial_ends = _parse_dt(user.get("trial_ends_at"))
    if not trial_ends:
        return 0.0
    now = datetime.now(timezone.utc)
    delta = (trial_ends - now).total_seconds()
    return max(delta / 86400, 0.0)


def _parse_dt(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None
