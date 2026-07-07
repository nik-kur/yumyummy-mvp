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


class AppMealItemInput(BaseModel):
    """One component of a meal's breakdown, as sent by the app when creating
    or editing a meal. Mirrors the shape stored in ``MealEntry.items_json``."""

    name: str
    grams: Optional[float] = Field(default=None, ge=0)
    calories_kcal: Optional[float] = Field(default=None, ge=0)
    protein_g: Optional[float] = Field(default=None, ge=0)
    fat_g: Optional[float] = Field(default=None, ge=0)
    carbs_g: Optional[float] = Field(default=None, ge=0)
    source_url: Optional[str] = None


class AppMealCreate(BaseModel):
    date: date
    description_user: str
    calories: float
    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0
    accuracy_level: Optional[str] = None
    # Optional component breakdown (additive, 25(1)+). Stored verbatim so the
    # created entry can be component-edited later like AI-logged meals.
    items: List[AppMealItemInput] = []
    source_url: Optional[str] = None


class AppMealUpdate(BaseModel):
    """Additive edit payload for a logged meal (25(1)+).

    ``items`` replaces the whole breakdown and the meal totals are recomputed
    from it; explicit total fields override the recomputed values.
    """

    description_user: Optional[str] = None
    calories: Optional[float] = Field(default=None, ge=0)
    protein_g: Optional[float] = Field(default=None, ge=0)
    fat_g: Optional[float] = Field(default=None, ge=0)
    carbs_g: Optional[float] = Field(default=None, ge=0)
    items: Optional[List[AppMealItemInput]] = None


class AppSavedMealUpdate(BaseModel):
    """Additive edit payload for a saved meal (25(1)+). Same semantics as
    :class:`AppMealUpdate`: items replace the breakdown and drive the totals."""

    name: Optional[str] = None
    total_calories: Optional[float] = Field(default=None, ge=0)
    total_protein_g: Optional[float] = Field(default=None, ge=0)
    total_fat_g: Optional[float] = Field(default=None, ge=0)
    total_carbs_g: Optional[float] = Field(default=None, ge=0)
    items: Optional[List[AppMealItemInput]] = None


class AppAgentRunRequest(BaseModel):
    text: str
    image_url: Optional[str] = None
    # Additive (25(1)+): multi-photo meals, capped server-side at 5 images.
    # image_url stays populated (first photo) so old servers keep working.
    image_urls: Optional[List[str]] = Field(default=None, max_length=5)
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
