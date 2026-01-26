from typing import Optional
from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    telegram_id: str


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    """Схема для обновления профиля пользователя"""
    goal_type: Optional[str] = None  # 'lose', 'maintain', 'gain'
    gender: Optional[str] = None  # 'male', 'female'
    age: Optional[int] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[float] = None
    activity_level: Optional[str] = None  # 'sedentary', 'light', 'moderate', 'high', 'very_high'
    target_calories: Optional[float] = None
    target_protein_g: Optional[float] = None
    target_fat_g: Optional[float] = None
    target_carbs_g: Optional[float] = None
    onboarding_completed: Optional[bool] = None


class UserRead(UserBase):
    id: int
    goal_type: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[float] = None
    activity_level: Optional[str] = None
    target_calories: Optional[float] = None
    target_protein_g: Optional[float] = None
    target_fat_g: Optional[float] = None
    target_carbs_g: Optional[float] = None
    onboarding_completed: bool = False

    model_config = ConfigDict(from_attributes=True)
