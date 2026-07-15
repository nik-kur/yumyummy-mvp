import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.usage_record import UsageRecord


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def record_usage_for_user(
    db: Session,
    user: Optional[User],
    usage_data: Optional[Dict[str, Any]],
    intent: Optional[str] = None,
) -> Optional[UsageRecord]:
    """Record an agent run's cost/tokens against an already-resolved ``User``.

    Shared core for both the Telegram path and the mobile-app path.
    """
    if not usage_data or user is None:
        return None

    cost_info = usage_data.get("cost", {}) if isinstance(usage_data, dict) else {}
    estimated_total_cost_usd = _as_float(cost_info.get("estimated_total_cost_usd"))
    input_tokens = _as_int(usage_data.get("input_tokens"))
    output_tokens = _as_int(usage_data.get("output_tokens"))
    web_search_calls = _as_int(usage_data.get("web_search_calls"))

    model_name = None
    models = usage_data.get("models")
    if isinstance(models, dict) and models:
        model_name = ",".join(sorted(models.keys()))

    usage_record = UsageRecord(
        user_id=user.id,
        cost_usd=estimated_total_cost_usd,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        web_search_calls=web_search_calls,
        intent=intent,
        model_name=model_name,
    )
    db.add(usage_record)

    user.usage_cost_current_period = _as_float(user.usage_cost_current_period) + estimated_total_cost_usd
    if user.usage_period_start is None:
        user.usage_period_start = user.trial_started_at or user.subscription_started_at or datetime.now(timezone.utc)

    db.commit()
    db.refresh(usage_record)
    db.refresh(user)
    return usage_record


def record_usage_for_telegram_user(
    db: Session,
    telegram_id: str,
    usage_data: Optional[Dict[str, Any]],
    intent: Optional[str] = None,
) -> Optional[UsageRecord]:
    if not usage_data:
        return None

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        return None

    return record_usage_for_user(db, user, usage_data, intent=intent)


# --- Global daily LLM spend circuit breaker -------------------------------
# A safety net on top of the per-user USD caps: even if a coordinated attack
# spins up many fresh accounts (each within its own tiny "new" cap), the sum
# of LLM cost across ALL users is bounded per calendar day (UTC). Recorded
# cost lags the run (we persist after the workflow), so this is a coarse
# breaker, not a hard per-request gate. Result is cached briefly to keep the
# aggregate off the hot path of every agent call.

_global_cost_cache: Dict[str, float] = {"value": 0.0, "checked_at": 0.0}
_GLOBAL_COST_CACHE_TTL_SECONDS = 30.0


def global_daily_llm_cost_usd(db: Session) -> float:
    """Total recorded LLM cost since UTC midnight (cached ~30s)."""
    now = time.monotonic()
    if now - _global_cost_cache["checked_at"] < _GLOBAL_COST_CACHE_TTL_SECONDS:
        return _global_cost_cache["value"]

    day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total = (
        db.query(sa_func.coalesce(sa_func.sum(UsageRecord.cost_usd), 0.0))
        .filter(UsageRecord.created_at >= day_start)
        .scalar()
    ) or 0.0
    _global_cost_cache["value"] = float(total)
    _global_cost_cache["checked_at"] = now
    return float(total)


def global_daily_cost_exceeded(db: Session) -> bool:
    """True when today's total LLM spend has hit the global cap.

    Fails open on any error (never block traffic because the breaker query
    itself failed) and when the cap is disabled (<= 0).
    """
    cap = settings.global_daily_llm_cost_cap_usd
    if not cap or cap <= 0:
        return False
    try:
        return global_daily_llm_cost_usd(db) >= cap
    except Exception:
        return False
