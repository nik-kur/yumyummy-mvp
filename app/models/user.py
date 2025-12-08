from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    days = relationship("UserDay", back_populates="user")
    meals = relationship("MealEntry", back_populates="user")
