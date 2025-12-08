from datetime import datetime, date
from typing import List

from pydantic import BaseModel, ConfigDict


class MealCreate(BaseModel):
    user_id: int
    date: date
    description_user: str
    calories: float
    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0


class MealRead(BaseModel):
    id: int
    eaten_at: datetime
    description_user: str
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float

    model_config = ConfigDict(from_attributes=True)


class DaySummary(BaseModel):
    user_id: int
    date: date
    total_calories: float
    total_protein_g: float
    total_fat_g: float
    total_carbs_g: float
    meals: List[MealRead]
