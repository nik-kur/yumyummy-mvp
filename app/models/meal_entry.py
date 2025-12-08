from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    Float,
    String,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class MealEntry(Base):
    __tablename__ = "meal_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_day_id = Column(Integer, ForeignKey("user_days.id"), nullable=False)

    eaten_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    description_user = Column(String, nullable=False)

    calories = Column(Float, nullable=False)
    protein_g = Column(Float, default=0)
    fat_g = Column(Float, default=0)
    carbs_g = Column(Float, default=0)

    uc_type = Column(String, nullable=True)         # UC1 / UC2 / UC3 / ...
    accuracy_level = Column(String, nullable=True)  # EXACT / ESTIMATE / APPROX

    user = relationship("User", back_populates="meals")
    user_day = relationship("UserDay", back_populates="meals")
