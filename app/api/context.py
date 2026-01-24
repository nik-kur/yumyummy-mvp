"""
Internal API endpoints for agent tools.
Provides read-only access to user meal data.
Protected by X-Internal-Token header.
"""
import logging
from datetime import date, datetime
from typing import Optional

import pytz
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.deps import verify_internal_token, get_db
from app.models.user import User
from app.models.user_day import UserDay
from app.models.meal_entry import MealEntry
from app.schemas.ai import ContextDayResponse, ContextDayTotals, ContextDayItem, MealsRecentResponse

logger = logging.getLogger(__name__)

# Europe/Berlin timezone
BERLIN_TZ = pytz.timezone("Europe/Berlin")

router = APIRouter(tags=["context"])


@router.get("/context/day", response_model=ContextDayResponse)
async def get_context_day(
    telegram_id: str = Query(..., description="Telegram user ID"),
    date_str: Optional[str] = Query(None, alias="date", description="Date in YYYY-MM-DD format (optional, defaults to today in Europe/Berlin)"),
    _token: str = Depends(verify_internal_token),
    db: Session = Depends(get_db),
):
    """
    Get meal entries for a specific day.
    Returns totals and list of meals for the given date.
    If date is not provided, uses today's date in Europe/Berlin timezone.
    """
    try:
        # Determine target date
        if date_str:
            # Parse provided date
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            # Use today in Europe/Berlin timezone
            berlin_now = datetime.now(BERLIN_TZ)
            target_date = berlin_now.date()
            date_str = target_date.strftime("%Y-%m-%d")
        
        # Find user by telegram_id
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            # Return empty response if user doesn't exist
            return ContextDayResponse(
                date=date_str,
                telegram_id=telegram_id,
                entries_count=0,
                totals=ContextDayTotals(
                    calories_kcal=0.0,
                    protein_g=0.0,
                    fat_g=0.0,
                    carbs_g=0.0,
                ),
                items=[],
            )
        
        # Find UserDay for the date
        user_day = (
            db.query(UserDay)
            .filter(and_(UserDay.user_id == user.id, UserDay.date == target_date))
            .first()
        )
        
        if not user_day:
            # Return empty response if no data for this day
            return ContextDayResponse(
                date=date_str,
                telegram_id=telegram_id,
                entries_count=0,
                totals=ContextDayTotals(
                    calories_kcal=0.0,
                    protein_g=0.0,
                    fat_g=0.0,
                    carbs_g=0.0,
                ),
                items=[],
            )
        
        # Get meal entries for this day, ordered by eaten_at
        meals = (
            db.query(MealEntry)
            .filter(MealEntry.user_day_id == user_day.id)
            .order_by(MealEntry.eaten_at.asc())
            .all()
        )
        
        # Build items list
        items = []
        for meal in meals:
            # Extract grams from description if possible, or use None
            grams = None
            # Try to parse grams from description (simple heuristic)
            # This is a fallback - ideally grams should be stored separately
            description = meal.description_user or ""
            
            items.append(
                ContextDayItem(
                    name=description,
                    grams=grams,
                    calories_kcal=meal.calories,
                    protein_g=meal.protein_g,
                    fat_g=meal.fat_g,
                    carbs_g=meal.carbs_g,
                    created_at=meal.eaten_at.isoformat() if meal.eaten_at else datetime.utcnow().isoformat(),
                )
            )
        
        # Build totals from UserDay aggregates
        totals = ContextDayTotals(
            calories_kcal=user_day.total_calories or 0.0,
            protein_g=user_day.total_protein_g or 0.0,
            fat_g=user_day.total_fat_g or 0.0,
            carbs_g=user_day.total_carbs_g or 0.0,
        )
        
        return ContextDayResponse(
            date=date_str,
            telegram_id=telegram_id,
            entries_count=len(items),
            totals=totals,
            items=items,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CONTEXT] Error in get_context_day: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/meals/recent", response_model=MealsRecentResponse)
async def get_meals_recent(
    telegram_id: str = Query(..., description="Telegram user ID"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of meals to return"),
    _token: str = Depends(verify_internal_token),
    db: Session = Depends(get_db),
):
    """
    Get recent meal entries for a user.
    Returns the most recent meals ordered by eaten_at (descending).
    """
    try:
        # Find user by telegram_id
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            # Return empty response if user doesn't exist
            return MealsRecentResponse(
                telegram_id=telegram_id,
                limit=limit,
                items=[],
            )
        
        # Get recent meal entries, ordered by eaten_at descending
        meals = (
            db.query(MealEntry)
            .filter(MealEntry.user_id == user.id)
            .order_by(MealEntry.eaten_at.desc())
            .limit(limit)
            .all()
        )
        
        # Build items list
        items = []
        for meal in meals:
            grams = None
            description = meal.description_user or ""
            
            items.append(
                ContextDayItem(
                    name=description,
                    grams=grams,
                    calories_kcal=meal.calories,
                    protein_g=meal.protein_g,
                    fat_g=meal.fat_g,
                    carbs_g=meal.carbs_g,
                    created_at=meal.eaten_at.isoformat() if meal.eaten_at else datetime.utcnow().isoformat(),
                )
            )
        
        return MealsRecentResponse(
            telegram_id=telegram_id,
            limit=limit,
            items=items,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CONTEXT] Error in get_meals_recent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
