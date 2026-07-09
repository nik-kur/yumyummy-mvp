"""
Insight generator v0 — simple rule-based daily insights for Day 3+.

Four rules checked in priority order; first match wins. Falls back to
a generic motivational insight if none match. Insights are computed lazily
when the user opens the app on Day 3+.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_day import UserDay

logger = logging.getLogger(__name__)


def _avg_calories(days: list[UserDay]) -> float:
    if not days:
        return 0
    return sum(d.total_calories or 0 for d in days) / len(days)


def _max_protein_day(days: list[UserDay]) -> Optional[UserDay]:
    if not days:
        return None
    return max(days, key=lambda d: d.total_protein_g or 0)


def generate_insight(db: Session, user: User) -> dict:
    """Generate the first available insight for the user's logged data."""
    days = (
        db.query(UserDay)
        .filter(UserDay.user_id == user.id)
        .order_by(UserDay.date.desc())
        .limit(7)
        .all()
    )

    if not days:
        return _fallback()

    avg_cal = _avg_calories(days)
    target_cal = user.target_calories or 0
    logged_days = len(days)

    # Rule 1: Consistency champion (3+ days logged)
    if logged_days >= 3:
        insight = {
            "id": "consistency",
            "icon": "streak",
            "title": f"{logged_days} days logged!",
            "body": "Consistency is the #1 predictor of success. You're building a great habit.",
            "metric_value": str(logged_days),
            "metric_label": "days tracked",
        }
        return insight

    # Rule 2: On target (within 10% of calorie target)
    if target_cal > 0 and abs(avg_cal - target_cal) / target_cal < 0.1:
        insight = {
            "id": "on_target",
            "icon": "target",
            "title": "Right on target",
            "body": f"Your average is {int(avg_cal)} kcal — within 10% of your {target_cal} kcal goal.",
            "metric_value": f"{int(avg_cal)}",
            "metric_label": "avg kcal",
        }
        return insight

    # Rule 3: Protein star
    best_p = _max_protein_day(days)
    if best_p and (best_p.total_protein_g or 0) > 100:
        insight = {
            "id": "protein_star",
            "icon": "protein",
            "title": "Protein star",
            "body": f"Your best day hit {best_p.total_protein_g}g protein — great for recovery and satiety.",
            "metric_value": f"{best_p.total_protein_g}g",
            "metric_label": "protein",
        }
        return insight

    # Rule 4: Over by a lot
    if target_cal > 0 and avg_cal > target_cal * 1.2:
        over_pct = int((avg_cal - target_cal) / target_cal * 100)
        insight = {
            "id": "over_budget",
            "icon": "alert",
            "title": "A bit over budget",
            "body": f"You're averaging {over_pct}% over your target. Small portion cuts can make a big difference.",
            "metric_value": f"+{over_pct}%",
            "metric_label": "over target",
        }
        return insight

    return _fallback()


def _fallback() -> dict:
    return {
        "id": "motivation",
        "icon": "sparkle",
        "title": "Every meal counts",
        "body": "Keep logging — the more data you have, the smarter your insights become.",
        "metric_value": "",
        "metric_label": "",
    }
