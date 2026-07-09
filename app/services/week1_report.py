"""
Week 1 Report generator — aggregate stats for the first 7 days post-purchase.

If the user has 5+ days of data, also re-evaluates targets and suggests an
adjustment (per spec v2.1 §5.5).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_day import UserDay

logger = logging.getLogger(__name__)


def build_week1_report(db: Session, user: User) -> dict:
    """Return the Week 1 Report payload."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=7)

    days = (
        db.query(UserDay)
        .filter(
            UserDay.user_id == user.id,
            UserDay.date >= start.date(),
        )
        .order_by(UserDay.date)
        .all()
    )

    logged_days = len(days)
    if logged_days == 0:
        return {
            "has_data": False,
            "days_logged": 0,
            "summary": "Log your meals this week to unlock your Week 1 Report!",
        }

    total_meals = sum(d.meal_count or 0 for d in days)
    avg_cal = sum(d.total_calories or 0 for d in days) / logged_days
    avg_protein = sum(d.total_protein_g or 0 for d in days) / logged_days
    avg_fat = sum(d.total_fat_g or 0 for d in days) / logged_days
    avg_carbs = sum(d.total_carbs_g or 0 for d in days) / logged_days

    target_cal = user.target_calories or 0
    on_target_days = 0
    if target_cal > 0:
        for d in days:
            cal = d.total_calories or 0
            if abs(cal - target_cal) / target_cal < 0.15:
                on_target_days += 1

    report: dict = {
        "has_data": True,
        "days_logged": logged_days,
        "total_meals": total_meals,
        "avg_calories": round(avg_cal),
        "avg_protein_g": round(avg_protein),
        "avg_fat_g": round(avg_fat),
        "avg_carbs_g": round(avg_carbs),
        "on_target_days": on_target_days,
        "target_calories": target_cal,
    }

    if logged_days >= 5 and target_cal > 0:
        delta_pct = (avg_cal - target_cal) / target_cal
        if abs(delta_pct) > 0.15:
            suggested = round(target_cal * (1 - delta_pct * 0.3))
            report["target_adjustment"] = {
                "suggested_calories": suggested,
                "reason": (
                    f"You averaged {round(avg_cal)} kcal vs your {target_cal} target. "
                    f"A slight adjustment to {suggested} kcal may be more sustainable."
                ),
            }

    report["summary"] = _build_summary(logged_days, total_meals, round(avg_cal), on_target_days, target_cal)
    return report


def _build_summary(days: int, meals: int, avg_cal: int, on_target: int, target: int) -> str:
    parts = [f"You logged {meals} meals across {days} days this week."]
    if target > 0:
        parts.append(f"{on_target} of {days} days were within 15% of your {target} kcal target.")
    parts.append(f"Your average was {avg_cal} kcal/day.")
    return " ".join(parts)
