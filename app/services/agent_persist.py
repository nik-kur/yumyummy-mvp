"""
Adapter to persist agent workflow results to database.
Converts agent_result (from /agent/run) to existing DB schema (User, MealEntry, UserDay).

There are two public entry points:
  * ``persist_agent_result(db, telegram_id, result)`` — the original
    Telegram-bot path (resolves/creates the user by telegram_id).
  * ``persist_agent_result_for_user(db, user, result)`` — the mobile-app path
    (the account's primary ``User`` is already resolved from the JWT).

Both share the same writing logic, so the diary is identical regardless of
which client logged the meal.
"""
import logging
from datetime import date, datetime
from typing import Any, Dict

import pytz
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.models.user import User
from app.models.user_day import UserDay
from app.models.meal_entry import MealEntry

logger = logging.getLogger(__name__)

# Intents whose results represent an actual eaten meal we should store.
MEAL_INTENTS = ["log_meal", "product", "eatout", "barcode", "photo_meal", "nutrition_label"]


def _get_or_create_user(db: Session, telegram_id: str) -> User:
    """
    Get or create user by telegram_id.
    Returns existing user if found, creates new one otherwise.
    """
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user:
        return user

    user = User(telegram_id=telegram_id)
    db.add(user)
    db.flush()  # Get ID without committing
    return user


def _is_persistable(agent_result: Dict[str, Any]) -> bool:
    """Decide whether an agent result represents a meal worth storing."""
    intent = agent_result.get("intent", "")
    if intent not in MEAL_INTENTS:
        logger.debug(f"[PERSIST] Skipping intent={intent}, not a meal logging intent")
        return False

    totals = agent_result.get("totals", {})
    items = agent_result.get("items", [])
    confidence = agent_result.get("confidence")

    calories_kcal = totals.get("calories_kcal", 0.0) or 0.0
    protein_g = totals.get("protein_g", 0.0) or 0.0
    fat_g = totals.get("fat_g", 0.0) or 0.0
    carbs_g = totals.get("carbs_g", 0.0) or 0.0

    if not items and calories_kcal == 0.0 and protein_g == 0.0 and fat_g == 0.0 and carbs_g == 0.0 and confidence is None:
        logger.debug("[PERSIST] Skipping: empty result (no items, all zeros, no confidence)")
        return False
    return True


def persist_agent_result_for_user(db: Session, user: User, agent_result: Dict[str, Any]) -> None:
    """Persist an agent workflow result onto an already-resolved ``User``.

    This is the shared core used by both the Telegram and mobile-app paths.
    """
    if not _is_persistable(agent_result):
        return

    intent = agent_result.get("intent", "")
    totals = agent_result.get("totals", {})
    items = agent_result.get("items", [])
    confidence = agent_result.get("confidence")

    calories_kcal = totals.get("calories_kcal", 0.0) or 0.0
    protein_g = totals.get("protein_g", 0.0) or 0.0
    fat_g = totals.get("fat_g", 0.0) or 0.0
    carbs_g = totals.get("carbs_g", 0.0) or 0.0

    try:
        # Use current date in user's timezone (or server timezone as fallback)
        user_tz_name = user.timezone or "Europe/Moscow"
        try:
            user_tz = pytz.timezone(user_tz_name)
        except pytz.exceptions.UnknownTimeZoneError:
            user_tz = pytz.timezone("Europe/Moscow")
        now_local = datetime.now(user_tz)
        today = now_local.date()

        # Find or create UserDay for today
        user_day = (
            db.query(UserDay)
            .filter(UserDay.user_id == user.id, UserDay.date == today)
            .first()
        )

        if not user_day:
            user_day = UserDay(
                user_id=user.id,
                date=today,
                total_calories=0,
                total_protein_g=0,
                total_fat_g=0,
                total_carbs_g=0,
            )
            db.add(user_day)
            db.flush()  # Get ID without committing

        # Build description from items or message_text
        description = ""
        if items and len(items) > 0:
            item_names = [item.get("name", "") for item in items if item.get("name")]
            if item_names:
                description = ", ".join(item_names[:3])  # Max 3 items
                if len(item_names) > 3:
                    description += f" и ещё {len(item_names) - 3}"
        else:
            message_text = agent_result.get("message_text", "")
            description = message_text.split("\n")[0][:100] if message_text else "Meal"

        # Normalize accuracy_level from confidence
        accuracy_level = "ESTIMATE"  # default
        if confidence == "HIGH":
            accuracy_level = "ESTIMATE"
        elif confidence == "ESTIMATE":
            accuracy_level = "ESTIMATE"

        meal = MealEntry(
            user_id=user.id,
            user_day_id=user_day.id,
            eaten_at=now_local,
            description_user=description,
            calories=calories_kcal,
            protein_g=protein_g,
            fat_g=fat_g,
            carbs_g=carbs_g,
            uc_type="AGENT",  # Mark as agent-logged
            accuracy_level=accuracy_level,
        )

        # Update day aggregates
        user_day.total_calories += calories_kcal
        user_day.total_protein_g += protein_g
        user_day.total_fat_g += fat_g
        user_day.total_carbs_g += carbs_g

        db.add(meal)
        db.commit()
        db.refresh(meal)

        logger.info(
            f"[PERSIST] Saved meal: user_id={user.id}, meal_id={meal.id}, "
            f"calories={calories_kcal}, intent={intent}"
        )

    except OperationalError as op_error:
        db.rollback()
        logger.error(
            f"[PERSIST] OperationalError (connection closed): {op_error}, "
            f"user_id={getattr(user, 'id', None)}, intent={intent}. "
            f"Caller should retry with a fresh session.",
            exc_info=True
        )
        raise  # Re-raise to let caller handle (endpoint will retry)
    except Exception as e:
        db.rollback()
        logger.error(f"[PERSIST] Error persisting agent result: {e}", exc_info=True)
        raise  # Re-raise to let caller handle


def persist_agent_result(db: Session, telegram_id: str, agent_result: Dict[str, Any]) -> None:
    """
    Persist agent workflow result to database (Telegram path).

    Args:
        db: Database session
        telegram_id: Telegram user ID (string)
        agent_result: Dict from agent workflow with keys:
            intent, message_text, confidence, totals{calories_kcal,protein_g,fat_g,carbs_g},
            items[{name,grams,calories_kcal,protein_g,fat_g,carbs_g}], source_url

    Returns:
        None (raises exception on error)
    """
    # Skip non-meal / empty results *before* touching the DB so we never
    # create a user row for a non-logging interaction (unchanged behaviour).
    if not _is_persistable(agent_result):
        return

    try:
        user = _get_or_create_user(db, telegram_id)
    except OperationalError as op_error:
        db.rollback()
        logger.error(
            f"[PERSIST] OperationalError resolving user telegram_id={telegram_id}: {op_error}. "
            f"Caller should retry with a fresh session.",
            exc_info=True,
        )
        raise

    persist_agent_result_for_user(db, user, agent_result)
