from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class SavedMealItemCreate(BaseModel):
    name: str
    grams: Optional[float] = None
    calories_kcal: float = 0
    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0
    source_url: Optional[str] = None


class SavedMealCreate(BaseModel):
    user_id: int
    name: str
    total_calories: float = 0
    total_protein_g: float = 0
    total_fat_g: float = 0
    total_carbs_g: float = 0
    items: List[SavedMealItemCreate] = []


class SavedMealItemRead(BaseModel):
    id: int
    name: str
    grams: Optional[float] = None
    calories_kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    source_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SavedMealRead(BaseModel):
    id: int
    name: str
    total_calories: float
    total_protein_g: float
    total_fat_g: float
    total_carbs_g: float
    use_count: int
    created_at: datetime
    items: List[SavedMealItemRead] = []

    model_config = ConfigDict(from_attributes=True)


class SavedMealListRead(BaseModel):
    id: int
    name: str
    total_calories: float
    total_protein_g: float
    total_fat_g: float
    total_carbs_g: float
    use_count: int

    model_config = ConfigDict(from_attributes=True)


class SavedMealUpdate(BaseModel):
    name: Optional[str] = None
    total_calories: Optional[float] = None
    total_protein_g: Optional[float] = None
    total_fat_g: Optional[float] = None
    total_carbs_g: Optional[float] = None


class SavedMealsListResponse(BaseModel):
    items: List[SavedMealListRead]
    total: int
    page: int
    per_page: int
