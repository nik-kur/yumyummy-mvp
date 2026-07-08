"""Weekly "Recap" aggregation + friendly LLM summary (Задача 6).

Reuses the diary tables the Telegram weekly-summary already reads, but adds
avg macros, a time-of-day split, best day, streak and deltas vs the previous
week, plus a cached one-line LLM summary. Everything is additive; nothing here
touches the 25(0) contract.
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import pytz
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_day import UserDay
from app.models.meal_entry import MealEntry
from app.models.weekly_recap import WeeklyRecap
from app.services.llm_client import chat_completion

logger = logging.getLogger(__name__)

# A day counts as "on target" when calories land within +10% of the goal —
# same rule the Week tab uses on the client.
ON_TARGET_MULT = 1.1
_STREAK_LOOKBACK_DAYS = 60
_WEEKDAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
]
_MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


# ── week math ────────────────────────────────────────────────────────────────


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def latest_completed_week_start(today: date) -> date:
    """Monday of the most recent Mon–Sun week whose Sunday is ``<= today``.

    On a Sunday this is the current week (it ends today, which is when the
    recap fires); on any other day it's the previous full week.
    """
    days_since_sunday = (today.weekday() + 1) % 7  # Sun=0, Mon=1, … Sat=6
    most_recent_sunday = today - timedelta(days=days_since_sunday)
    return most_recent_sunday - timedelta(days=6)


def _format_range(start: date, end: date) -> str:
    if start.month == end.month:
        return f"{_MONTHS[start.month - 1]} {start.day} – {end.day}"
    return f"{_MONTHS[start.month - 1]} {start.day} – {_MONTHS[end.month - 1]} {end.day}"


# ── stats ────────────────────────────────────────────────────────────────────


def _meal_counts(db: Session, day_ids: list[int]) -> dict[int, int]:
    if not day_ids:
        return {}
    return dict(
        db.query(MealEntry.user_day_id, func.count(MealEntry.id))
        .filter(MealEntry.user_day_id.in_(day_ids))
        .group_by(MealEntry.user_day_id)
        .all()
    )


def _local_hour(eaten_at: datetime, tz) -> int:
    dt = eaten_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).hour


def _bucket_for_hour(hour: int) -> str:
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 16:
        return "midday"
    if 16 <= hour < 22:
        return "evening"
    return "night"


def _logged_dates(db: Session, user_id: int, start: date, end: date) -> set[date]:
    """Dates in [start, end] with at least one logged meal."""
    rows = (
        db.query(UserDay.date)
        .join(MealEntry, MealEntry.user_day_id == UserDay.id)
        .filter(
            UserDay.user_id == user_id,
            UserDay.date >= start,
            UserDay.date <= end,
        )
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def _streak_ending(db: Session, user_id: int, anchor: date) -> int:
    """Consecutive days with a logged meal ending at ``anchor`` (an unlogged
    anchor doesn't break the streak — we count back from the day before)."""
    logged = _logged_dates(db, user_id, anchor - timedelta(days=_STREAK_LOOKBACK_DAYS), anchor)
    cursor = anchor
    if cursor not in logged:
        cursor -= timedelta(days=1)
    count = 0
    while cursor in logged:
        count += 1
        cursor -= timedelta(days=1)
    return count


def compute_week_stats(db: Session, user: User, week_start: date, tz) -> dict:
    """Numeric stats for the Mon–Sun week starting ``week_start``."""
    week_end = week_start + timedelta(days=6)
    target = user.target_calories or 0
    has_target = target > 0

    day_rows = (
        db.query(UserDay)
        .filter(
            UserDay.user_id == user.id,
            UserDay.date >= week_start,
            UserDay.date <= week_end,
        )
        .all()
    )
    counts = _meal_counts(db, [d.id for d in day_rows])
    active = [d for d in day_rows if counts.get(d.id, 0) > 0]

    meals_count = sum(counts.get(d.id, 0) for d in active)
    days_logged = len(active)

    def _avg(attr: str) -> float:
        if not active:
            return 0.0
        return round(sum((getattr(d, attr) or 0) for d in active) / len(active))

    avg_calories = _avg("total_calories")
    avg_protein = _avg("total_protein_g")
    avg_fat = _avg("total_fat_g")
    avg_carbs = _avg("total_carbs_g")

    on_target_days = (
        sum(1 for d in active if (d.total_calories or 0) <= target * ON_TARGET_MULT)
        if has_target else 0
    )

    # Best day: closest to (but within) the target if we have one; otherwise
    # the highest-protein day.
    best = None
    if active:
        if has_target:
            best = min(active, key=lambda d: abs((d.total_calories or 0) - target))
        else:
            best = max(active, key=lambda d: (d.total_protein_g or 0))

    # Time-of-day split over the week's meals.
    split = {"morning": 0.0, "midday": 0.0, "evening": 0.0, "night": 0.0}
    if active:
        meals = (
            db.query(MealEntry)
            .filter(MealEntry.user_day_id.in_([d.id for d in active]))
            .all()
        )
        for m in meals:
            bucket = _bucket_for_hour(_local_hour(m.eaten_at, tz)) if m.eaten_at else "midday"
            split[bucket] += m.calories or 0
    split = {k: round(v) for k, v in split.items()}

    return {
        "week_start": week_start,
        "week_end": week_end,
        "days_logged": days_logged,
        "meals_count": int(meals_count),
        "on_target_days": on_target_days,
        "avg_calories": avg_calories,
        "avg_protein_g": avg_protein,
        "avg_fat_g": avg_fat,
        "avg_carbs_g": avg_carbs,
        "best_day": best.date if best else None,
        "best_day_label": _WEEKDAY_NAMES[best.date.weekday()] if best else None,
        "best_day_calories": round(best.total_calories or 0) if best else None,
        "meal_time_split": split,
        "has_data": days_logged > 0,
    }


# ── summary ──────────────────────────────────────────────────────────────────


def _fallback_summary(stats: dict, target: Optional[float]) -> str:
    if not stats["has_data"]:
        return "No meals logged this week — an easy win for next week is to log just breakfast each day."
    dl = stats["days_logged"]
    parts = [f"You logged {dl} of 7 days"]
    if target and stats["on_target_days"]:
        parts.append(f"and stayed on target {stats['on_target_days']} of them")
    return ". ".join([" ".join(parts) + ".", "Keep the streak going next week."])


async def generate_summary(stats: dict, user: User) -> str:
    """One warm, specific sentence about the week. Cheap flash model; falls back
    to a template on any error so the recap never breaks."""
    target = user.target_calories or None
    if not stats["has_data"]:
        return _fallback_summary(stats, target)

    payload = {
        "days_logged_of_7": stats["days_logged"],
        "meals_logged": stats["meals_count"],
        "avg_calories": stats["avg_calories"],
        "calorie_target": round(target) if target else None,
        "days_on_target_of_logged": stats["on_target_days"],
        "avg_protein_g": stats["avg_protein_g"],
        "protein_target_g": round(user.target_protein_g) if user.target_protein_g else None,
        "best_day": stats["best_day_label"],
        "streak_days": stats.get("streak", 0),
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You are YumYummy, a warm, concise nutrition coach. Write ONE or TWO short "
                "sentences summarising the user's week from the JSON stats. Be specific and "
                "encouraging, reference real numbers, at most one emoji, no medical advice, "
                "under 240 characters. Plain text only."
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    try:
        text = await chat_completion(messages, model="gpt-4.1-mini", temperature=0.6)
        text = (text or "").strip()
        return text[:280] if text else _fallback_summary(stats, target)
    except Exception as exc:  # never fail the endpoint on the LLM
        logger.warning("[RECAP] summary generation failed: %s", exc)
        return _fallback_summary(stats, target)


# ── public entry point ───────────────────────────────────────────────────────


async def build_recap(db: Session, user: User, today: date, week_start: Optional[date] = None) -> dict:
    """Assemble the recap response dict for one week.

    Stats are computed live; the LLM summary is cached in ``weekly_recaps`` and
    reused on subsequent reads.
    """
    try:
        tz = pytz.timezone(user.timezone or "Europe/Moscow")
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.timezone("Europe/Moscow")

    if week_start is None:
        week_start = latest_completed_week_start(today)
    else:
        week_start = monday_of(week_start)

    stats = compute_week_stats(db, user, week_start, tz)
    prev = compute_week_stats(db, user, week_start - timedelta(days=7), tz)
    stats["streak"] = _streak_ending(db, user.id, min(stats["week_end"], today))

    summary = _get_or_generate_summary(db, user, week_start, stats)
    if summary is None:
        summary = await generate_summary(stats, user)
        _store_summary(db, user.id, week_start, stats, summary)

    return {
        "week_start": stats["week_start"],
        "week_end": stats["week_end"],
        "date_range": _format_range(stats["week_start"], stats["week_end"]),
        "has_data": stats["has_data"],
        "days_logged": stats["days_logged"],
        "meals_count": stats["meals_count"],
        "on_target_days": stats["on_target_days"],
        "avg_calories": stats["avg_calories"],
        "avg_protein_g": stats["avg_protein_g"],
        "avg_fat_g": stats["avg_fat_g"],
        "avg_carbs_g": stats["avg_carbs_g"],
        "target_calories": user.target_calories,
        "target_protein_g": user.target_protein_g,
        "target_fat_g": user.target_fat_g,
        "target_carbs_g": user.target_carbs_g,
        "prev_days_logged": prev["days_logged"] if prev["has_data"] else None,
        "prev_meals_count": prev["meals_count"] if prev["has_data"] else None,
        "prev_on_target_days": prev["on_target_days"] if prev["has_data"] else None,
        "prev_avg_calories": prev["avg_calories"] if prev["has_data"] else None,
        "best_day": stats["best_day"],
        "best_day_label": stats["best_day_label"],
        "best_day_calories": stats["best_day_calories"],
        "meal_time_split": stats["meal_time_split"],
        "streak": stats["streak"],
        "summary": summary,
    }


def _get_or_generate_summary(db: Session, user: User, week_start: date, stats: dict) -> Optional[str]:
    """Return a cached summary for the week, or None if we must generate one."""
    row = (
        db.query(WeeklyRecap)
        .filter(WeeklyRecap.user_id == user.id, WeeklyRecap.week_start == week_start)
        .first()
    )
    if row and row.llm_summary:
        return row.llm_summary
    return None


def _store_summary(db: Session, user_id: int, week_start: date, stats: dict, summary: str) -> None:
    """Persist the generated summary. Best-effort: a failure (e.g. a unique-key
    race) must not break the response."""
    try:
        snapshot = dict(stats)
        # dates aren't JSON-serialisable
        for k in ("week_start", "week_end", "best_day"):
            if snapshot.get(k) is not None:
                snapshot[k] = snapshot[k].isoformat()
        row = (
            db.query(WeeklyRecap)
            .filter(WeeklyRecap.user_id == user_id, WeeklyRecap.week_start == week_start)
            .first()
        )
        if row is None:
            row = WeeklyRecap(user_id=user_id, week_start=week_start)
            db.add(row)
        row.stats_json = json.dumps(snapshot, ensure_ascii=False)
        row.llm_summary = summary
        db.commit()
    except Exception as exc:
        logger.warning("[RECAP] failed to cache summary: %s", exc)
        db.rollback()
