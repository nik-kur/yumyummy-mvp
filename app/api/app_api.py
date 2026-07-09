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

import json
import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_account
from app.ai.stt_client import transcribe_audio
from app.db.session import SessionLocal
from app.core.config import settings
from app.models.account import Account, Identity
from app.models.user import User
from app.models.user_day import UserDay
from app.models.meal_entry import MealEntry
from app.models.saved_meal import SavedMeal
from app.models.saved_meal_item import SavedMealItem
from app.models.usage_record import UsageRecord
from app.models.churn_survey import ChurnSurvey
from app.models.payment_event import PaymentEvent
from app.models.notification_event import NotificationEvent
from app.models.acquisition_event import AcquisitionEvent
from app.models.auth_code import AuthOneTimeCode
from app.auth.service import get_primary_user, account_member_users
from app.billing.account_access import account_billing_snapshot, account_has_access
from app.billing.plans import resolve_trial_days
from app.services.agent_persist import persist_agent_result_for_user
from app.services.usage_guardrails import record_usage_for_user
from app.services.user_time import today_for_user
from app.services.weekly_recap import build_recap
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
    AppMealItemInput,
    AppMealUpdate,
    AppSavedMealUpdate,
    AppAgentRunRequest,
    AppTrialStartRequest,
    AppTrialStartResponse,
    DayTotals,
    WeeklyRecapResponse,
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


def _items_json(items: list[AppMealItemInput]) -> str:
    """Serialize breakdown items to the ``MealEntry.items_json`` format."""
    return json.dumps([i.model_dump() for i in items], ensure_ascii=False)


def _items_totals(items: list[AppMealItemInput]) -> tuple[float, float, float, float]:
    """(calories, protein, fat, carbs) summed over a breakdown."""
    return (
        sum((i.calories_kcal or 0) for i in items),
        sum((i.protein_g or 0) for i in items),
        sum((i.fat_g or 0) for i in items),
        sum((i.carbs_g or 0) for i in items),
    )


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


@router.delete("/me")
def delete_me(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Permanently delete the caller's account and all of its data.

    Required by App Store Review Guideline 5.1.1(v): an app that supports
    account creation must let the user *delete* their account (not merely sign
    out) from within the app. This erases the account, every sign-in identity
    (Apple / Google / email / Telegram), the diary (days, meals, saved meals),
    billing/usage history, and lifecycle analytics keyed to the account.

    It does NOT cancel an active App Store subscription — auto-renewable
    subscriptions are managed by Apple and cancelled by the user in Settings;
    we only remove our own copy of the account and its data.
    """
    members = account_member_users(db, account.id)
    user_ids = [u.id for u in members]
    telegram_ids = [u.telegram_id for u in members if u.telegram_id]

    # email_login one-time codes are keyed by email with a NULL account_id, so
    # the accounts FK cascade won't reach them — collect the account's emails.
    emails: set[str] = set()
    if account.primary_email:
        emails.add(account.primary_email.strip().lower())
    for ident in db.query(Identity).filter(Identity.account_id == account.id).all():
        if ident.email:
            emails.add(ident.email.strip().lower())
        if ident.provider == "email" and ident.provider_id:
            emails.add(str(ident.provider_id).strip().lower())

    if user_ids:
        # Diary children first (these FKs have no ON DELETE CASCADE).
        saved_ids = [
            row[0]
            for row in db.query(SavedMeal.id).filter(SavedMeal.user_id.in_(user_ids)).all()
        ]
        if saved_ids:
            db.query(SavedMealItem).filter(
                SavedMealItem.saved_meal_id.in_(saved_ids)
            ).delete(synchronize_session=False)
        db.query(SavedMeal).filter(SavedMeal.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(MealEntry).filter(MealEntry.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(UserDay).filter(UserDay.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(UsageRecord).filter(UsageRecord.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(ChurnSurvey).filter(ChurnSurvey.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(PaymentEvent).filter(PaymentEvent.user_id.in_(user_ids)).delete(synchronize_session=False)

    if telegram_ids:
        db.query(NotificationEvent).filter(
            NotificationEvent.telegram_id.in_(telegram_ids)
        ).delete(synchronize_session=False)
        db.query(AcquisitionEvent).filter(
            AcquisitionEvent.telegram_id.in_(telegram_ids)
        ).delete(synchronize_session=False)

    if emails:
        db.query(AuthOneTimeCode).filter(
            AuthOneTimeCode.subject.in_(list(emails))
        ).delete(synchronize_session=False)

    # Diary containers, then the account. Identities and telegram_link one-time
    # codes are removed by the accounts FK cascade (ON DELETE CASCADE).
    db.query(User).filter(User.account_id == account.id).delete(synchronize_session=False)
    db.query(Account).filter(Account.id == account.id).delete(synchronize_session=False)

    db.commit()
    logger.info("account_deleted account_id=%s users=%s", account.id, user_ids)
    return {"status": "deleted"}


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


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")


@router.get("/week", response_model=list[DaySummary])
def get_week(
    start: str = Query(..., description="First day of the 7-day window, YYYY-MM-DD"),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Return 7 consecutive :class:`DaySummary` objects starting at ``start``.

    Additive convenience (25(1)+) over calling ``GET /app/today`` seven times:
    the Week tab needs a whole week (bars, weekly averages, and the selected
    day's meal list) in a single round-trip. Days with no diary row come back as
    zeroed summaries with an empty ``meals`` list, so the client always receives
    exactly 7 ordered entries.
    """
    user = get_primary_user(db, account)
    db.commit()

    start_date = _parse_date(start)
    dates = [start_date + timedelta(days=i) for i in range(7)]
    end_date = dates[-1]

    day_rows = (
        db.query(UserDay)
        .filter(
            UserDay.user_id == user.id,
            UserDay.date >= start_date,
            UserDay.date <= end_date,
        )
        .all()
    )
    day_by_date = {d.date: d for d in day_rows}

    meals_by_day: dict[int, list[MealEntry]] = {}
    day_ids = [d.id for d in day_rows]
    if day_ids:
        for meal in (
            db.query(MealEntry)
            .filter(MealEntry.user_day_id.in_(day_ids))
            .order_by(MealEntry.eaten_at.asc())
            .all()
        ):
            meals_by_day.setdefault(meal.user_day_id, []).append(meal)

    summaries: list[DaySummary] = []
    for d in dates:
        ud = day_by_date.get(d)
        if ud is None:
            summaries.append(DaySummary(
                user_id=user.id, date=d,
                total_calories=0, total_protein_g=0, total_fat_g=0, total_carbs_g=0,
                meals=[],
            ))
            continue
        summaries.append(DaySummary(
            user_id=user.id,
            date=d,
            total_calories=ud.total_calories or 0,
            total_protein_g=ud.total_protein_g or 0,
            total_fat_g=ud.total_fat_g or 0,
            total_carbs_g=ud.total_carbs_g or 0,
            meals=[MealRead.model_validate(m) for m in meals_by_day.get(ud.id, [])],
        ))
    return summaries


@router.get("/history", response_model=list[DayTotals])
def get_history(
    start: str = Query(..., description="Range start, YYYY-MM-DD (inclusive)"),
    end: str = Query(..., description="Range end, YYYY-MM-DD (inclusive)"),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Lightweight per-day totals over a date range (no meal breakdown).

    Additive (25(1)+). Powers the Week tab's logging streak and the month
    heatmap without pulling every day's full meal list. Only days that have a
    diary row are returned (ordered by date); the client fills the gaps with
    zeros.
    """
    user = get_primary_user(db, account)
    db.commit()

    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end must be on or after start")
    if (end_date - start_date).days > 400:
        raise HTTPException(status_code=400, detail="Range too large (max 400 days)")

    day_rows = (
        db.query(UserDay)
        .filter(
            UserDay.user_id == user.id,
            UserDay.date >= start_date,
            UserDay.date <= end_date,
        )
        .order_by(UserDay.date.asc())
        .all()
    )
    counts: dict[int, int] = {}
    if day_rows:
        counts = dict(
            db.query(MealEntry.user_day_id, func.count(MealEntry.id))
            .filter(MealEntry.user_day_id.in_([d.id for d in day_rows]))
            .group_by(MealEntry.user_day_id)
            .all()
        )

    return [
        DayTotals(
            date=d.date,
            total_calories=d.total_calories or 0,
            total_protein_g=d.total_protein_g or 0,
            total_fat_g=d.total_fat_g or 0,
            total_carbs_g=d.total_carbs_g or 0,
            meal_count=int(counts.get(d.id, 0)),
        )
        for d in day_rows
    ]


@router.get("/recap/latest", response_model=WeeklyRecapResponse)
async def get_recap_latest(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """"Week in Recap" for the most recent completed week (Задача 6).

    Additive (25(1)+): a friendly, shareable weekly summary — live stats plus a
    cached LLM one-liner. Anchored to the user's timezone (on a Sunday it's the
    week that ends today, otherwise the previous full week).
    """
    user = get_primary_user(db, account)
    db.commit()
    today = today_for_user(user)
    data = await build_recap(db, user, today)
    return WeeklyRecapResponse(**data)


@router.get("/recap", response_model=WeeklyRecapResponse)
async def get_recap(
    week: str = Query(..., description="Any day inside the target week, YYYY-MM-DD"),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Recap for a specific week (the Monday of the week containing ``week``)."""
    user = get_primary_user(db, account)
    db.commit()
    today = today_for_user(user)
    week_start = _parse_date(week)
    data = await build_recap(db, user, today, week_start=week_start)
    return WeeklyRecapResponse(**data)


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
        items_json=_items_json(payload.items) if payload.items else None,
        source_url=payload.source_url,
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


@router.patch("/meals/{meal_id}", response_model=MealRead)
def update_meal(
    meal_id: int,
    payload: AppMealUpdate,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Edit a logged meal: rename, replace the component breakdown, or set
    totals directly. Additive endpoint (25(1)+) — nothing existing changes.

    When ``items`` is provided it replaces the stored breakdown and the meal
    totals are recomputed from it; explicit total fields override. The owning
    day's aggregates are adjusted by the delta so Today stays consistent.
    """
    ids = _member_ids(db, account)
    meal = db.query(MealEntry).filter(MealEntry.id == meal_id).first()
    if meal is None or meal.user_id not in ids:
        raise HTTPException(status_code=404, detail="Meal not found")

    old_cal = meal.calories or 0
    old_prot = meal.protein_g or 0
    old_fat = meal.fat_g or 0
    old_carbs = meal.carbs_g or 0

    if payload.description_user is not None and payload.description_user.strip():
        meal.description_user = payload.description_user.strip()

    if payload.items is not None:
        meal.items_json = _items_json(payload.items)
        meal.calories, meal.protein_g, meal.fat_g, meal.carbs_g = _items_totals(payload.items)

    if payload.calories is not None:
        meal.calories = payload.calories
    if payload.protein_g is not None:
        meal.protein_g = payload.protein_g
    if payload.fat_g is not None:
        meal.fat_g = payload.fat_g
    if payload.carbs_g is not None:
        meal.carbs_g = payload.carbs_g

    user_day = db.query(UserDay).filter(UserDay.id == meal.user_day_id).first()
    if user_day is not None:
        user_day.total_calories = max((user_day.total_calories or 0) + (meal.calories or 0) - old_cal, 0)
        user_day.total_protein_g = max((user_day.total_protein_g or 0) + (meal.protein_g or 0) - old_prot, 0)
        user_day.total_fat_g = max((user_day.total_fat_g or 0) + (meal.fat_g or 0) - old_fat, 0)
        user_day.total_carbs_g = max((user_day.total_carbs_g or 0) + (meal.carbs_g or 0) - old_carbs, 0)

    db.commit()
    db.refresh(meal)
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
        assessment_json=src.assessment_json,
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


@router.patch("/saved-meals/{saved_meal_id}", response_model=SavedMealRead)
def update_saved_meal(
    saved_meal_id: int,
    payload: AppSavedMealUpdate,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Edit a saved meal: rename, replace its component breakdown, or set
    totals directly. Additive endpoint (25(1)+)."""
    ids = _member_ids(db, account)
    saved = db.query(SavedMeal).filter(SavedMeal.id == saved_meal_id).first()
    if saved is None or saved.user_id not in ids:
        raise HTTPException(status_code=404, detail="Saved meal not found")

    if payload.name is not None and payload.name.strip():
        saved.name = payload.name.strip()

    if payload.items is not None:
        db.query(SavedMealItem).filter(
            SavedMealItem.saved_meal_id == saved.id
        ).delete(synchronize_session=False)
        for item in payload.items:
            db.add(SavedMealItem(
                saved_meal_id=saved.id,
                name=item.name,
                grams=item.grams,
                calories_kcal=item.calories_kcal or 0,
                protein_g=item.protein_g or 0,
                fat_g=item.fat_g or 0,
                carbs_g=item.carbs_g or 0,
                source_url=item.source_url,
            ))
        (saved.total_calories, saved.total_protein_g,
         saved.total_fat_g, saved.total_carbs_g) = _items_totals(payload.items)

    if payload.total_calories is not None:
        saved.total_calories = payload.total_calories
    if payload.total_protein_g is not None:
        saved.total_protein_g = payload.total_protein_g
    if payload.total_fat_g is not None:
        saved.total_fat_g = payload.total_fat_g
    if payload.total_carbs_g is not None:
        saved.total_carbs_g = payload.total_carbs_g

    db.commit()
    db.refresh(saved)
    return SavedMealRead.model_validate(saved)


@router.delete("/saved-meals/{saved_meal_id}")
def delete_saved_meal(
    saved_meal_id: int,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Remove a saved meal (and its items) from My Menu. Additive (25(1)+)."""
    ids = _member_ids(db, account)
    saved = db.query(SavedMeal).filter(SavedMeal.id == saved_meal_id).first()
    if saved is None or saved.user_id not in ids:
        raise HTTPException(status_code=404, detail="Saved meal not found")
    db.delete(saved)  # ORM cascade removes the items
    db.commit()
    return {"status": "deleted", "saved_meal_id": saved_meal_id}


@router.post("/saved-meals/{saved_meal_id}/log", response_model=MealRead)
def log_saved_meal(
    saved_meal_id: int,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Log a saved meal onto today, breakdown included, and bump its use count.

    Additive endpoint (25(1)+). Replaces the client-side "Log again" flow that
    posted bare totals (losing the component breakdown and never incrementing
    ``use_count``).
    """
    import pytz

    ids = _member_ids(db, account)
    saved = db.query(SavedMeal).filter(SavedMeal.id == saved_meal_id).first()
    if saved is None or saved.user_id not in ids:
        raise HTTPException(status_code=404, detail="Saved meal not found")

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

    items = [
        {
            "name": it.name,
            "grams": it.grams,
            "calories_kcal": it.calories_kcal,
            "protein_g": it.protein_g,
            "fat_g": it.fat_g,
            "carbs_g": it.carbs_g,
            "source_url": it.source_url,
        }
        for it in saved.items
    ]
    meal = MealEntry(
        user_id=user.id,
        user_day_id=user_day.id,
        eaten_at=now_local,
        description_user=saved.name,
        calories=saved.total_calories or 0,
        protein_g=saved.total_protein_g or 0,
        fat_g=saved.total_fat_g or 0,
        carbs_g=saved.total_carbs_g or 0,
        uc_type="APP_SAVED",
        accuracy_level="ESTIMATE",
        items_json=json.dumps(items, ensure_ascii=False) if items else None,
    )
    user_day.total_calories = (user_day.total_calories or 0) + (saved.total_calories or 0)
    user_day.total_protein_g = (user_day.total_protein_g or 0) + (saved.total_protein_g or 0)
    user_day.total_fat_g = (user_day.total_fat_g or 0) + (saved.total_fat_g or 0)
    user_day.total_carbs_g = (user_day.total_carbs_g or 0) + (saved.total_carbs_g or 0)
    saved.use_count = (saved.use_count or 0) + 1
    db.add(meal)
    db.commit()
    db.refresh(meal)
    return MealRead.model_validate(meal)


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


@router.post("/billing/sync", response_model=BillingSnapshot)
def billing_sync(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Post-identify reconciliation: pull subscription state from Adapty Server
    API so purchases made on an anonymous Adapty profile (before the user signed
    in with Apple) are reflected in our entitlement."""
    from app.billing.adapty_sync import sync_from_adapty
    user = get_primary_user(db, account)
    sync_from_adapty(db, user, account)
    return BillingSnapshot(**account_billing_snapshot(db, account))


@router.get("/insights/latest")
def get_latest_insight(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Generate the latest rule-based insight for the user."""
    from app.services.insights import generate_insight
    user = get_primary_user(db, account)
    return generate_insight(db, user)


@router.get("/report/week1")
def get_week1_report(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Week 1 Report — aggregate stats from the first 7 days."""
    from app.services.week1_report import build_week1_report
    user = get_primary_user(db, account)
    return build_week1_report(db, user)


def _empty_totals() -> WorkflowTotals:
    return WorkflowTotals(calories_kcal=0, protein_g=0, fat_g=0, carbs_g=0)


def _build_nutrition_context(db: Session, user: User) -> str:
    """Targets + eaten today + remaining, as the Telegram bot builds for
    food_advice. The mobile app doesn't send this, so we compute it here."""
    import json

    import pytz

    try:
        tz = pytz.timezone(user.timezone or "Europe/Moscow")
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.timezone("Europe/Moscow")
    today = datetime.now(tz).date()

    day = (
        db.query(UserDay)
        .filter(UserDay.user_id == user.id, UserDay.date == today)
        .first()
    )
    target_cal = user.target_calories or 2000
    target_prot = user.target_protein_g or 150
    target_fat = user.target_fat_g or 65
    target_carbs = user.target_carbs_g or 200
    eaten_cal = (day.total_calories if day else 0) or 0
    eaten_prot = (day.total_protein_g if day else 0) or 0
    eaten_fat = (day.total_fat_g if day else 0) or 0
    eaten_carbs = (day.total_carbs_g if day else 0) or 0
    return json.dumps(
        {
            "target_calories": target_cal,
            "target_protein_g": target_prot,
            "target_fat_g": target_fat,
            "target_carbs_g": target_carbs,
            "eaten_calories": eaten_cal,
            "eaten_protein_g": eaten_prot,
            "eaten_fat_g": eaten_fat,
            "eaten_carbs_g": eaten_carbs,
            "remaining_calories": max(0, target_cal - eaten_cal),
            "remaining_protein_g": max(0, target_prot - eaten_prot),
            "remaining_fat_g": max(0, target_fat - eaten_fat),
            "remaining_carbs_g": max(0, target_carbs - eaten_carbs),
        },
        ensure_ascii=False,
    )


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

    # --- Agent v2 beta: per-account engine switch (server-side, no app change).
    # Any v2 failure falls through to the v1 workflow, so beta accounts can
    # never end up worse off than production.
    result = None
    use_v2 = (
        settings.agent_engine_default == "v2"
        or account.id in settings.agent_v2_account_id_set
    )
    if use_v2:
        try:
            from app.agent_v2.adapter import run_v2_workflow

            nutrition_context = payload.nutrition_context
            if (payload.force_intent or "").lower() in ("advice", "food_advice") and not nutrition_context:
                nutrition_context = _build_nutrition_context(db, user)

            result = await run_v2_workflow(
                user_text=payload.text,
                telegram_id=workflow_id,
                image_url=payload.image_url,
                image_urls=payload.image_urls,
                force_intent=payload.force_intent,
                nutrition_context=nutrition_context,
                variant=settings.agent_v2_variant,
            )
            logger.info(
                "[/app/agent/run] served by agent v2 (%s) account=%s intent=%s",
                settings.agent_v2_variant, account.id, result.get("intent"),
            )
        except Exception as exc:
            logger.warning(
                "[/app/agent/run] agent v2 failed, falling back to v1: %s", exc,
            )
            result = None

    try:
        if result is None:
            # v1 workflow is single-photo only: fall back to the first image.
            first_image = payload.image_url or (
                payload.image_urls[0] if payload.image_urls else None
            )
            result = await run_yumyummy_workflow(
                user_text=payload.text,
                telegram_id=workflow_id,
                image_url=first_image,
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


@router.post("/voice/transcribe")
async def app_voice_transcribe(
    audio: UploadFile = File(...),
    account: Account = Depends(get_current_account),
):
    """Speech-to-text only for the mobile composer.

    Unlike ``/ai/voice_parse_meal`` this deliberately does NOT run the
    web-search meal-analysis pipeline — the app just drops the transcript into
    the capture box so the user can review/edit it, then submits it through
    ``/app/agent/run`` (which does the source-checked logging). Keeping this
    endpoint transcript-only makes voice logging fast and avoids duplicate,
    wasted analysis work.
    """
    try:
        file_bytes = await audio.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read audio file")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        transcript = await transcribe_audio(
            file_bytes=file_bytes,
            filename=audio.filename or "voice.m4a",
        )
    except Exception as exc:
        logger.error("[/app/voice/transcribe] STT failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Could not recognize speech")

    return {"transcript": transcript.strip()}
