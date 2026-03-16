from dataclasses import dataclass
from typing import Dict, Optional


TRIAL_DAYS = 3
SUBSCRIPTION_PERIOD_SECONDS = 30 * 24 * 60 * 60  # Telegram only allows 30-day periods


@dataclass(frozen=True)
class Plan:
    id: str
    name_ru: str
    price_xtr: int
    period_days: int
    subscription_period_seconds: Optional[int]
    is_active: bool
    is_recurring: bool


def get_plans() -> Dict[str, Plan]:
    from app.core.config import settings

    return {
        "monthly": Plan(
            id="monthly",
            name_ru="Месячный",
            price_xtr=settings.billing_monthly_price_xtr,
            period_days=30,
            subscription_period_seconds=SUBSCRIPTION_PERIOD_SECONDS,
            is_active=True,
            is_recurring=True,
        ),
        "yearly": Plan(
            id="yearly",
            name_ru="Годовой",
            price_xtr=settings.billing_yearly_price_xtr,
            period_days=365,
            subscription_period_seconds=None,
            is_active=True,
            is_recurring=False,
        ),
    }


def get_active_plan(plan_id: str) -> Optional[Plan]:
    plans = get_plans()
    plan = plans.get(plan_id)
    if plan and plan.is_active:
        return plan
    return None
