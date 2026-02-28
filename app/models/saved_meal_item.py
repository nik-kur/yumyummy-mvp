from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base import Base


class SavedMealItem(Base):
    __tablename__ = "saved_meal_items"

    id = Column(Integer, primary_key=True, index=True)
    saved_meal_id = Column(
        Integer, ForeignKey("saved_meals.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String, nullable=False)
    grams = Column(Float, nullable=True)

    calories_kcal = Column(Float, default=0)
    protein_g = Column(Float, default=0)
    fat_g = Column(Float, default=0)
    carbs_g = Column(Float, default=0)

    source_url = Column(String, nullable=True)

    saved_meal = relationship("SavedMeal", back_populates="items")
