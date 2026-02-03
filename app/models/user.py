from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Онбординг данные
    goal_type = Column(String, nullable=True)  # 'lose', 'maintain', 'gain'
    gender = Column(String, nullable=True)  # 'male', 'female'
    age = Column(Integer, nullable=True)
    height_cm = Column(Integer, nullable=True)
    weight_kg = Column(Float, nullable=True)
    activity_level = Column(String, nullable=True)  # 'sedentary', 'light', 'moderate', 'high', 'very_high'

    # Целевые КБЖУ
    target_calories = Column(Float, nullable=True)
    target_protein_g = Column(Float, nullable=True)
    target_fat_g = Column(Float, nullable=True)
    target_carbs_g = Column(Float, nullable=True)

    # Статус онбординга
    onboarding_completed = Column(Boolean, default=False, nullable=False)

    # Связи
    days = relationship("UserDay", back_populates="user")
    meals = relationship("MealEntry", back_populates="user")
