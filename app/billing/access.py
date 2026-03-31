from datetime import datetime, timezone
from typing import Any, Dict, Optional

USAGE_CAP_TRIAL_USD = 2.0
USAGE_CAP_ACTIVE_USD = 10.0


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
    return compute_access_status(user) in ("trial", "active") and check_usage_cap(user)


def get_usage_cap_usd(user: Dict[str, Any]) -> Optional[float]:
    status = compute_access_status(user)
    if status == "trial":
        return USAGE_CAP_TRIAL_USD
    if status == "active":
        return USAGE_CAP_ACTIVE_USD
    return None


def check_usage_cap(user: Dict[str, Any]) -> bool:
    cap = get_usage_cap_usd(user)
    if cap is None:
        return True
    try:
        current_cost = float(user.get("usage_cost_current_period") or 0.0)
    except (TypeError, ValueError):
        current_cost = 0.0
    return current_cost < cap


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
