from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    cost_usd = Column(Float, nullable=False, default=0.0)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    web_search_calls = Column(Integer, nullable=False, default=0)
    intent = Column(String, nullable=True)
    model_name = Column(String, nullable=True)

    user = relationship("User", back_populates="usage_records")
