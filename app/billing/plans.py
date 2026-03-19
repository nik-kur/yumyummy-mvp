from dataclasses import dataclass
from typing import Dict, Optional


TRIAL_DAYS = 3
SUBSCRIPTION_PERIOD_SECONDS = 30 * 24 * 60 * 60  # Telegram only allows 30-day periods


@dataclass(frozen=True)
class Plan:
    id: str
    name_en: str
    name_ru: str
    period_days: int
    is_active: bool
    is_recurring: bool
    # Telegram Stars pricing
    price_xtr: int = 0
    subscription_period_seconds: Optional[int] = None
    approx_usd: Optional[str] = None
    # Gumroad pricing
    gumroad_price_cents: int = 0
    gumroad_recurrence: Optional[str] = None


def get_plans() -> Dict[str, Plan]:
    from app.core.config import settings

    return {
        "monthly": Plan(
            id="monthly",
            name_en="Monthly",
            name_ru="Месячный",
            price_xtr=settings.billing_monthly_price_xtr,
            period_days=30,
            subscription_period_seconds=SUBSCRIPTION_PERIOD_SECONDS,
            is_active=True,
            is_recurring=True,
            approx_usd="~$9.99",
            gumroad_price_cents=settings.gumroad_monthly_price_cents,
            gumroad_recurrence="monthly",
        ),
        "yearly": Plan(
            id="yearly",
            name_en="Yearly",
            name_ru="Годовой",
            price_xtr=settings.billing_yearly_price_xtr,
            period_days=365,
            subscription_period_seconds=None,
            is_active=True,
            is_recurring=False,
            approx_usd="~$89.99",
            gumroad_price_cents=settings.gumroad_yearly_price_cents,
            gumroad_recurrence="yearly",
        ),
    }


def get_active_plan(plan_id: str) -> Optional[Plan]:
    plans = get_plans()
    plan = plans.get(plan_id)
    if plan and plan.is_active:
        return plan
    return None
