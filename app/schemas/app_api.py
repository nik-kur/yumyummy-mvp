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


class DayTotals(BaseModel):
    """Lightweight per-day aggregate (no meal breakdown) for history/analytics.

    Additive (25(1)+): powers the Week tab's streak counter and month heatmap
    over a wide date range without pulling every day's full meal list.
    """

    date: date
    total_calories: float = 0
    total_protein_g: float = 0
    total_fat_g: float = 0
    total_carbs_g: float = 0
    meal_count: int = 0


class MealTimeSplit(BaseModel):
    """Calories eaten by time-of-day bucket (from each meal's ``eaten_at`` in the
    user's timezone). Buckets: morning 5–11, midday 11–16, evening 16–22,
    night 22–5."""

    morning: float = 0
    midday: float = 0
    evening: float = 0
    night: float = 0


class RecapHighlight(BaseModel):
    """One "fun fact" card on the Recap screen. The server owns the copy so new
    categories can ship without an app update; ``icon`` is a hint the client
    maps to a local icon (unknown values fall back gracefully)."""

    id: str  # stable category id, e.g. "top_dish"
    icon: str  # client icon hint: "utensils" | "flame" | "sunrise" | ...
    title: str  # overline, e.g. "Most logged dish"
    value: str  # the big line, e.g. "Butter croissant"
    caption: Optional[str] = None  # e.g. "Logged 3 times this week"


class WeeklyRecapResponse(BaseModel):
    """"Week in Recap" (Задача 6) — a friendly, shareable weekly summary.

    All numeric stats are computed live from the diary; ``summary`` is an
    LLM-generated (and cached) one-liner. ``prev_*`` fields carry the previous
    week's value for the same metric so the client can render ▲/▼ deltas
    (``None`` when there's no prior data). Additive (25(1)+).
    """

    week_start: date
    week_end: date
    date_range: str  # e.g. "Jul 6 – 12"
    has_data: bool = False

    days_logged: int = 0
    meals_count: int = 0
    on_target_days: int = 0

    avg_calories: float = 0
    avg_protein_g: float = 0
    avg_fat_g: float = 0
    avg_carbs_g: float = 0

    target_calories: Optional[float] = None
    target_protein_g: Optional[float] = None
    target_fat_g: Optional[float] = None
    target_carbs_g: Optional[float] = None

    # Previous-week values for delta chips (None when no prior data).
    prev_days_logged: Optional[int] = None
    prev_meals_count: Optional[int] = None
    prev_on_target_days: Optional[int] = None
    prev_avg_calories: Optional[float] = None

    best_day: Optional[date] = None
    best_day_label: Optional[str] = None  # e.g. "Wednesday"
    best_day_calories: Optional[float] = None

    meal_time_split: MealTimeSplit = Field(default_factory=MealTimeSplit)
    streak: int = 0

    # 3–4 rotating "fun fact" cards drawn from a larger candidate pool, so each
    # week's recap feels fresh. Empty when there's no data.
    highlights: list[RecapHighlight] = Field(default_factory=list)

    summary: str = ""


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
    # Length caps are defense against accidental/abusive oversized payloads
    # driving up LLM token cost. A user meal/advisor message never needs more
    # than a few thousand chars; nutrition_context is client-assembled diary
    # context so it gets a larger ceiling.
    text: str = Field(..., max_length=4000)
    image_url: Optional[str] = Field(default=None, max_length=2048)
    # Additive (25(1)+): multi-photo meals, capped server-side at 5 images.
    # image_url stays populated (first photo) so old servers keep working.
    image_urls: Optional[List[str]] = Field(default=None, max_length=5)
    force_intent: Optional[str] = Field(default=None, max_length=64)
    nutrition_context: Optional[str] = Field(default=None, max_length=8000)


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
