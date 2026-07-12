from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.billing.access import USAGE_PERIOD_DAYS
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

    # Roll the spend window before accumulating: a window older than
    # USAGE_PERIOD_DAYS resets the meter, so yearly subscribers (whose billing
    # period only turns over once a year) still get a fresh budget each month.
    now = datetime.now(timezone.utc)
    start = user.usage_period_start
    if start is not None and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if start is None:
        user.usage_period_start = user.trial_started_at or user.subscription_started_at or now
    elif (now - start) >= timedelta(days=USAGE_PERIOD_DAYS):
        user.usage_cost_current_period = 0.0
        user.usage_period_start = now

    user.usage_cost_current_period = _as_float(user.usage_cost_current_period) + estimated_total_cost_usd

    db.commit()
    db.refresh(usage_record)
    db.refresh(user)
    return usage_record


def check_rate_limit(db: Session, user_ids: Sequence[int]) -> Optional[str]:
    """Anti-abuse throttle for the AI agent, per account (across member users).

    Returns ``"minute"`` or ``"day"`` when the account is over the respective
    rolling limit, else ``None``. Counts already-recorded agent runs
    (``usage_records``); paywalled/rate-limited responses write no record, so
    they never count against the caller. Thresholds are configurable via
    ``settings.agent_rate_limit_per_min`` / ``_per_day`` (0 disables a window).
    """
    if not user_ids:
        return None
    now = datetime.now(timezone.utc)

    per_min = settings.agent_rate_limit_per_min
    if per_min and per_min > 0:
        n_min = (
            db.query(func.count(UsageRecord.id))
            .filter(
                UsageRecord.user_id.in_(list(user_ids)),
                UsageRecord.created_at >= now - timedelta(seconds=60),
            )
            .scalar()
        ) or 0
        if n_min >= per_min:
            return "minute"

    per_day = settings.agent_rate_limit_per_day
    if per_day and per_day > 0:
        n_day = (
            db.query(func.count(UsageRecord.id))
            .filter(
                UsageRecord.user_id.in_(list(user_ids)),
                UsageRecord.created_at >= now - timedelta(days=1),
            )
            .scalar()
        ) or 0
        if n_day >= per_day:
            return "day"

    return None


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
