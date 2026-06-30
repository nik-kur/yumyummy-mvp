"""
Account-scoped, JWT-authenticated API for the mobile app.

Every endpoint resolves the caller's :class:`Account` from the Bearer token
(via :func:`app.deps.get_current_account`) and operates on that account's
primary ``User`` diary container — so the app reads/writes exactly the same
data the Telegram bot does once the two are linked.

These endpoints intentionally reuse the existing services
(``run_yumyummy_workflow``, ``persist_agent_result_for_user``,
``record_usage_for_user``, billing access) rather than duplicating logic.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_account
from app.db.session import SessionLocal
from app.core.config import settings
from app.models.account import Account, Identity
from app.models.user import User
from app.models.user_day import UserDay
from app.models.meal_entry import MealEntry
from app.models.saved_meal import SavedMeal
from app.models.saved_meal_item import SavedMealItem
from app.auth.service import get_primary_user, account_member_users
from app.billing.account_access import account_billing_snapshot, account_has_access
from app.billing.plans import resolve_trial_days
from app.services.agent_persist import persist_agent_result_for_user
from app.services.usage_guardrails import record_usage_for_user
from app.agent_runner import run_yumyummy_workflow, WorkflowNotInstalledError
from app.schemas.ai import WorkflowRunResponse, WorkflowTotals
from app.schemas.meal import DaySummary, MealRead
from app.schemas.saved_meal import (
    SavedMealRead,
    SavedMealListRead,
    SavedMealsListResponse,
    SavedMealCreate,
)
from app.schemas.app_api import (
    AccountProfile,
    AccountProfileUpdate,
    BillingSnapshot,
    AppMealCreate,
    AppAgentRunRequest,
    AppTrialStartRequest,
    AppTrialStartResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/app", tags=["app"])

_PROFILE_FIELDS = (
    "goal_type", "gender", "age", "height_cm", "weight_kg", "activity_level",
    "target_calories", "target_protein_g", "target_fat_g", "target_carbs_g",
    "onboarding_completed", "timezone",
)


def _member_ids(db: Session, account: Account) -> list[int]:
    return [u.id for u in account_member_users(db, account.id)]


def _build_profile(db: Session, account: Account, user: User) -> AccountProfile:
    providers = [
        i.provider for i in db.query(Identity).filter(Identity.account_id == account.id).all()
    ]
    snapshot = BillingSnapshot(**account_billing_snapshot(db, account))
    return AccountProfile(
        account_id=account.id,
        user_id=user.id,
        telegram_id=user.telegram_id,
        linked_providers=sorted(set(providers)),
        goal_type=user.goal_type,
        gender=user.gender,
        age=user.age,
        height_cm=user.height_cm,
        weight_kg=user.weight_kg,
        activity_level=user.activity_level,
        target_calories=user.target_calories,
        target_protein_g=user.target_protein_g,
        target_fat_g=user.target_fat_g,
        target_carbs_g=user.target_carbs_g,
        onboarding_completed=bool(user.onboarding_completed),
        timezone=user.timezone,
        billing=snapshot,
    )


@router.get("/me", response_model=AccountProfile)
def get_me(db: Session = Depends(get_db), account: Account = Depends(get_current_account)):
    user = get_primary_user(db, account)
    db.commit()  # persist a defensively-created primary user, if any
    return _build_profile(db, account, user)


@router.patch("/me", response_model=AccountProfile)
def update_me(
    payload: AccountProfileUpdate,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    user = get_primary_user(db, account)
    data = payload.model_dump(exclude_unset=True)
    for field in _PROFILE_FIELDS:
        if field in data and data[field] is not None:
            setattr(user, field, data[field])
    db.commit()
    db.refresh(user)
    return _build_profile(db, account, user)


@router.get("/today", response_model=DaySummary)
def get_today(
    date_str: str = Query(None, alias="date", description="YYYY-MM-DD (defaults to today in user tz)"),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    import pytz

    user = get_primary_user(db, account)
    db.commit()

    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        tz_name = user.timezone or "Europe/Moscow"
        try:
            tz = pytz.timezone(tz_name)
        except pytz.exceptions.UnknownTimeZoneError:
            tz = pytz.timezone("Europe/Moscow")
        target_date = datetime.now(tz).date()

    user_day = (
        db.query(UserDay)
        .filter(UserDay.user_id == user.id, UserDay.date == target_date)
        .first()
    )
    if not user_day:
        return DaySummary(
            user_id=user.id, date=target_date,
            total_calories=0, total_protein_g=0, total_fat_g=0, total_carbs_g=0,
            meals=[],
        )
    meals = (
        db.query(MealEntry)
        .filter(MealEntry.user_day_id == user_day.id)
        .order_by(MealEntry.eaten_at.asc())
        .all()
    )
    return DaySummary(
        user_id=user.id,
        date=target_date,
        total_calories=user_day.total_calories or 0,
        total_protein_g=user_day.total_protein_g or 0,
        total_fat_g=user_day.total_fat_g or 0,
        total_carbs_g=user_day.total_carbs_g or 0,
        meals=[MealRead.model_validate(m) for m in meals],
    )


@router.get("/meals/recent", response_model=list[MealRead])
def recent_meals(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    ids = _member_ids(db, account)
    meals = (
        db.query(MealEntry)
        .filter(MealEntry.user_id.in_(ids))
        .order_by(MealEntry.eaten_at.desc())
        .limit(limit)
        .all()
    )
    return [MealRead.model_validate(m) for m in meals]


@router.post("/meals", response_model=MealRead)
def create_meal(
    payload: AppMealCreate,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    user = get_primary_user(db, account)
    db.flush()
    user_day = (
        db.query(UserDay)
        .filter(UserDay.user_id == user.id, UserDay.date == payload.date)
        .first()
    )
    if not user_day:
        user_day = UserDay(
            user_id=user.id, date=payload.date,
            total_calories=0, total_protein_g=0, total_fat_g=0, total_carbs_g=0,
        )
        db.add(user_day)
        db.flush()

    meal = MealEntry(
        user_id=user.id,
        user_day_id=user_day.id,
        eaten_at=datetime.now(timezone.utc),
        description_user=payload.description_user,
        calories=payload.calories,
        protein_g=payload.protein_g,
        fat_g=payload.fat_g,
        carbs_g=payload.carbs_g,
        uc_type="APP",
        accuracy_level=payload.accuracy_level or "ESTIMATE",
    )
    user_day.total_calories = (user_day.total_calories or 0) + payload.calories
    user_day.total_protein_g = (user_day.total_protein_g or 0) + payload.protein_g
    user_day.total_fat_g = (user_day.total_fat_g or 0) + payload.fat_g
    user_day.total_carbs_g = (user_day.total_carbs_g or 0) + payload.carbs_g
    db.add(meal)
    db.commit()
    db.refresh(meal)
    return MealRead.model_validate(meal)


@router.get("/meals/{meal_id}", response_model=MealRead)
def get_meal(
    meal_id: int,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Single meal with its ingredient-level breakdown + source link."""
    ids = _member_ids(db, account)
    meal = db.query(MealEntry).filter(MealEntry.id == meal_id).first()
    if meal is None or meal.user_id not in ids:
        raise HTTPException(status_code=404, detail="Meal not found")
    return MealRead.model_validate(meal)


@router.post("/meals/{meal_id}/repeat", response_model=MealRead)
def repeat_meal(
    meal_id: int,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Re-log an existing meal *verbatim* onto today — no new AI search.

    Copies the stored macros, ingredient breakdown and source so the repeated
    entry is byte-for-byte identical (this is the deterministic counterpart to
    "Log similar", which re-runs the workflow and can return different numbers).
    """
    import pytz

    ids = _member_ids(db, account)
    src = db.query(MealEntry).filter(MealEntry.id == meal_id).first()
    if src is None or src.user_id not in ids:
        raise HTTPException(status_code=404, detail="Meal not found")

    user = get_primary_user(db, account)
    db.flush()

    tz_name = user.timezone or "Europe/Moscow"
    try:
        tz = pytz.timezone(tz_name)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.timezone("Europe/Moscow")
    now_local = datetime.now(tz)
    today = now_local.date()

    user_day = (
        db.query(UserDay)
        .filter(UserDay.user_id == user.id, UserDay.date == today)
        .first()
    )
    if not user_day:
        user_day = UserDay(
            user_id=user.id, date=today,
            total_calories=0, total_protein_g=0, total_fat_g=0, total_carbs_g=0,
        )
        db.add(user_day)
        db.flush()

    meal = MealEntry(
        user_id=user.id,
        user_day_id=user_day.id,
        eaten_at=now_local,
        description_user=src.description_user,
        calories=src.calories or 0,
        protein_g=src.protein_g or 0,
        fat_g=src.fat_g or 0,
        carbs_g=src.carbs_g or 0,
        uc_type="APP_REPEAT",
        accuracy_level=src.accuracy_level,
        items_json=src.items_json,
        source_url=src.source_url,
    )
    user_day.total_calories = (user_day.total_calories or 0) + (src.calories or 0)
    user_day.total_protein_g = (user_day.total_protein_g or 0) + (src.protein_g or 0)
    user_day.total_fat_g = (user_day.total_fat_g or 0) + (src.fat_g or 0)
    user_day.total_carbs_g = (user_day.total_carbs_g or 0) + (src.carbs_g or 0)
    db.add(meal)
    db.commit()
    db.refresh(meal)
    return MealRead.model_validate(meal)


@router.delete("/meals/{meal_id}")
def delete_meal(
    meal_id: int,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    ids = _member_ids(db, account)
    meal = db.query(MealEntry).filter(MealEntry.id == meal_id).first()
    if meal is None or meal.user_id not in ids:
        raise HTTPException(status_code=404, detail="Meal not found")

    user_day = db.query(UserDay).filter(UserDay.id == meal.user_day_id).first()
    if user_day is not None:
        user_day.total_calories = max((user_day.total_calories or 0) - (meal.calories or 0), 0)
        user_day.total_protein_g = max((user_day.total_protein_g or 0) - (meal.protein_g or 0), 0)
        user_day.total_fat_g = max((user_day.total_fat_g or 0) - (meal.fat_g or 0), 0)
        user_day.total_carbs_g = max((user_day.total_carbs_g or 0) - (meal.carbs_g or 0), 0)
    db.delete(meal)
    db.commit()
    return {"status": "deleted", "meal_id": meal_id}


@router.get("/saved-meals", response_model=SavedMealsListResponse)
def list_saved_meals(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    ids = _member_ids(db, account)
    rows = (
        db.query(SavedMeal)
        .filter(SavedMeal.user_id.in_(ids))
        .order_by(SavedMeal.use_count.desc(), SavedMeal.created_at.desc())
        .all()
    )
    return SavedMealsListResponse(
        items=[SavedMealListRead.model_validate(r) for r in rows],
        total=len(rows),
        page=1,
        per_page=len(rows),
    )


@router.post("/saved-meals", response_model=SavedMealRead)
def create_saved_meal(
    payload: SavedMealCreate,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    user = get_primary_user(db, account)
    db.flush()
    saved = SavedMeal(
        user_id=user.id,
        name=payload.name,
        total_calories=payload.total_calories,
        total_protein_g=payload.total_protein_g,
        total_fat_g=payload.total_fat_g,
        total_carbs_g=payload.total_carbs_g,
    )
    db.add(saved)
    db.flush()
    for item in payload.items:
        db.add(SavedMealItem(
            saved_meal_id=saved.id,
            name=item.name,
            grams=item.grams,
            calories_kcal=item.calories_kcal,
            protein_g=item.protein_g,
            fat_g=item.fat_g,
            carbs_g=item.carbs_g,
            source_url=item.source_url,
        ))
    db.commit()
    db.refresh(saved)
    return SavedMealRead.model_validate(saved)


@router.get("/billing/status", response_model=BillingSnapshot)
def billing_status(db: Session = Depends(get_db), account: Account = Depends(get_current_account)):
    return BillingSnapshot(**account_billing_snapshot(db, account))


@router.post("/billing/trial/start", response_model=AppTrialStartResponse)
def start_trial(
    payload: AppTrialStartRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    user = get_primary_user(db, account)
    trial_days = resolve_trial_days(payload.trial_days)

    if user.trial_started_at is not None:
        snap = account_billing_snapshot(db, account)
        return AppTrialStartResponse(
            access_status=snap["access_status"],
            trial_started_at=user.trial_started_at,
            trial_ends_at=user.trial_ends_at,
            trial_days=trial_days,
            already_started=True,
        )

    now = datetime.now(timezone.utc)
    user.trial_started_at = now
    user.trial_ends_at = now + timedelta(days=trial_days)
    user.usage_cost_current_period = 0.0
    user.usage_period_start = now
    db.commit()
    db.refresh(user)
    snap = account_billing_snapshot(db, account)
    return AppTrialStartResponse(
        access_status=snap["access_status"],
        trial_started_at=user.trial_started_at,
        trial_ends_at=user.trial_ends_at,
        trial_days=trial_days,
        already_started=False,
    )


def _empty_totals() -> WorkflowTotals:
    return WorkflowTotals(calories_kcal=0, protein_g=0, fat_g=0, carbs_g=0)


@router.post("/agent/run", response_model=WorkflowRunResponse)
async def app_agent_run(
    payload: AppAgentRunRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Run the AI logging/advisor workflow for the signed-in account."""
    # Defense-in-depth paywall, mirroring /agent/run.
    if settings.billing_paywall_enabled and not account_has_access(db, account):
        return WorkflowRunResponse(
            intent="paywall",
            message_text="Your trial has ended. Subscribe to keep logging meals.",
            confidence=None,
            totals=_empty_totals(),
            items=[],
            source_url=None,
        )

    user = get_primary_user(db, account)
    db.commit()
    # The workflow only uses this id as an opaque context key.
    workflow_id = user.telegram_id or f"acct:{account.id}"

    try:
        result = await run_yumyummy_workflow(
            user_text=payload.text,
            telegram_id=workflow_id,
            image_url=payload.image_url,
            force_intent=payload.force_intent,
            nutrition_context=payload.nutrition_context,
        )
    except WorkflowNotInstalledError as exc:
        logger.warning("[/app/agent/run] workflow unavailable: %s", exc)
        return WorkflowRunResponse(
            intent="help",
            message_text="The assistant is temporarily unavailable. Please try again soon.",
            confidence=None, totals=_empty_totals(), items=[], source_url=None,
        )
    except Exception as exc:  # never crash the client
        logger.error("[/app/agent/run] workflow error: %s", exc, exc_info=True)
        return WorkflowRunResponse(
            intent="help",
            message_text="Something went wrong. Please try again.",
            confidence=None, totals=_empty_totals(), items=[], source_url=None,
        )

    usage_data = result.pop("_usage", None)
    intent = result.get("intent", "unknown")

    # Persist with a fresh session (mirrors /agent/run's stale-connection guard).
    db2 = SessionLocal()
    try:
        u2 = (
            db2.query(User)
            .filter(User.account_id == account.id)
            .order_by(User.id.asc())
            .first()
        )
        if u2 is not None:
            if usage_data:
                record_usage_for_user(db2, u2, usage_data, intent=intent)
            persist_agent_result_for_user(db2, u2, result)
    except Exception as exc:
        logger.error("[/app/agent/run] persist failed: %s", exc, exc_info=True)
    finally:
        db2.close()

    try:
        return WorkflowRunResponse(**result)
    except Exception as exc:
        logger.error("[/app/agent/run] response validation error: %s", exc, exc_info=True)
        return WorkflowRunResponse(
            intent="help",
            message_text="Got it, but I couldn't format the result. Please try again.",
            confidence=None, totals=_empty_totals(), items=[], source_url=None,
        )
