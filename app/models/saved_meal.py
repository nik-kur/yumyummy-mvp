from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class SavedMeal(Base):
    __tablename__ = "saved_meals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)

    total_calories = Column(Float, default=0)
    total_protein_g = Column(Float, default=0)
    total_fat_g = Column(Float, default=0)
    total_carbs_g = Column(Float, default=0)

    use_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="saved_meals")
    items = relationship(
        "SavedMealItem",
        back_populates="saved_meal",
        cascade="all, delete-orphan",
    )
