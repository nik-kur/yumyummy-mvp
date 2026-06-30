import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    Float,
    String,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.db.base import Base

logger = logging.getLogger(__name__)


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

    # AI workflow provenance, so the app can show an ingredient-level breakdown
    # and a real source link, and re-log the meal verbatim ("Repeat"):
    #   items_json: JSON list of {name, grams, calories_kcal, protein_g, fat_g,
    #               carbs_g, source_url}
    #   source_url: primary source the macros were checked against
    items_json = Column(Text, nullable=True)
    source_url = Column(String, nullable=True)

    user = relationship("User", back_populates="meals")
    user_day = relationship("UserDay", back_populates="meals")

    @property
    def items(self) -> List[Dict[str, Any]]:
        """Parsed ingredient breakdown (empty list when absent/legacy/corrupt)."""
        if not self.items_json:
            return []
        try:
            data = json.loads(self.items_json)
            return data if isinstance(data, list) else []
        except (ValueError, TypeError):
            logger.warning("[MealEntry] bad items_json on meal id=%s", self.id)
            return []
