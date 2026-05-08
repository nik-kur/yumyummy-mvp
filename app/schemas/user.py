from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    telegram_id: str


class UserCreate(UserBase):
    # Optional Telegram deep-link source parameter
    # (``t.me/<bot>?start=<source>``). Backend stores first-touch on
    # ``users.acquisition_source`` and appends every click to
    # ``acquisition_events``. Validated server-side against
    # ``^[A-Za-z0-9_-]{1,64}$`` (Telegram's deep-link allowed charset).
    acquisition_source: Optional[str] = None

    # Optional PostHog distinct_id forwarded from the marketing site so
    # the backend can attribute funnel events (trial, subscription, …) to
    # the same person who pageview'd the LP. Validated against the same
    # charset as ``acquisition_source``.
    posthog_distinct_id: Optional[str] = None


class UserUpdate(BaseModel):
    """Схема для обновления профиля пользователя"""
    goal_type: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[float] = None
    activity_level: Optional[str] = None
    target_calories: Optional[float] = None
    target_protein_g: Optional[float] = None
    target_fat_g: Optional[float] = None
    target_carbs_g: Optional[float] = None
    onboarding_completed: Optional[bool] = None
    timezone: Optional[str] = None
    trial_started_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    subscription_plan_id: Optional[str] = None
    subscription_started_at: Optional[datetime] = None
    subscription_ends_at: Optional[datetime] = None
    subscription_auto_renew: Optional[bool] = None
    subscription_telegram_charge_id: Optional[str] = None
    subscription_provider: Optional[str] = None
    subscription_gumroad_id: Optional[str] = None
    first_meal_after_onboarding_at: Optional[datetime] = None
    features_used: Optional[str] = None
    meals_count_trial: Optional[int] = None


class UserRead(UserBase):
    id: int
    goal_type: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[float] = None
    activity_level: Optional[str] = None
    target_calories: Optional[float] = None
    target_protein_g: Optional[float] = None
    target_fat_g: Optional[float] = None
    target_carbs_g: Optional[float] = None
    onboarding_completed: bool = False
    timezone: Optional[str] = None
    trial_started_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    subscription_plan_id: Optional[str] = None
    subscription_started_at: Optional[datetime] = None
    subscription_ends_at: Optional[datetime] = None
    subscription_auto_renew: Optional[bool] = None
    subscription_telegram_charge_id: Optional[str] = None
    subscription_provider: Optional[str] = None
    subscription_gumroad_id: Optional[str] = None
    first_meal_after_onboarding_at: Optional[datetime] = None
    features_used: Optional[str] = None
    meals_count_trial: Optional[int] = None
    acquisition_source: Optional[str] = None
    posthog_distinct_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
