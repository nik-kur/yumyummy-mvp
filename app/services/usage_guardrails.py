from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

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
