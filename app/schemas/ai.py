from typing import Optional

from pydantic import BaseModel, ConfigDict


class ParseMealRequest(BaseModel):
    text: str


class MealParsed(BaseModel):
    description: str
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    accuracy_level: str
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
