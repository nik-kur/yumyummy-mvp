from sqlalchemy import Column, Integer, Date, ForeignKey, Float
from sqlalchemy.orm import relationship

from app.db.base import Base


class UserDay(Base):
    __tablename__ = "user_days"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    date = Column(Date, nullable=False, index=True)

    total_calories = Column(Float, default=0)
    total_protein_g = Column(Float, default=0)
    total_fat_g = Column(Float, default=0)
    total_carbs_g = Column(Float, default=0)

    user = relationship("User", back_populates="days")
    meals = relationship("MealEntry", back_populates="user_day")
