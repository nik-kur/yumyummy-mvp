from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    telegram_id: str


class UserCreate(UserBase):
    pass


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

    model_config = ConfigDict(from_attributes=True)
