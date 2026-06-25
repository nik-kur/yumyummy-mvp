"""Pydantic schemas for the account-scoped (JWT-authenticated) app API."""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BillingSnapshot(BaseModel):
    access_status: str
    trial_started_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    trial_days_remaining: Optional[float] = None
    subscription_plan_id: Optional[str] = None
    subscription_ends_at: Optional[datetime] = None
    subscription_auto_renew: Optional[bool] = None
    subscription_provider: Optional[str] = None
    usage_cost_current_period: float = 0.0
    usage_cap_usd: Optional[float] = None
    usage_exceeded: bool = False


class AccountProfile(BaseModel):
    account_id: int
    user_id: int
    telegram_id: Optional[str] = None
    linked_providers: List[str] = []

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

    billing: BillingSnapshot


class AccountProfileUpdate(BaseModel):
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


class AppMealCreate(BaseModel):
    date: date
    description_user: str
    calories: float
    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0
    accuracy_level: Optional[str] = None


class AppAgentRunRequest(BaseModel):
    text: str
    image_url: Optional[str] = None
    force_intent: Optional[str] = None
    nutrition_context: Optional[str] = None


class AppTrialStartRequest(BaseModel):
    # Adapty cohort drives this (we A/B 3 vs 7); validated server-side.
    trial_days: Optional[int] = None


class AppTrialStartResponse(BaseModel):
    access_status: str
    trial_started_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    trial_days: int
    already_started: bool = False


class PresignRequest(BaseModel):
    content_type: str = Field(default="image/jpeg", max_length=100)
    ext: Optional[str] = Field(default=None, max_length=10)


class PresignResponse(BaseModel):
    key: str
    upload_url: str
    public_url: Optional[str] = None
    expires_in_seconds: int
