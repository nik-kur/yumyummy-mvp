from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class ChurnSurvey(Base):
    __tablename__ = "churn_surveys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    telegram_id = Column(String, nullable=False, index=True)

    reason = Column(String, nullable=False)
    comment = Column(String, nullable=True)
    subscription_provider = Column(String, nullable=True)
    subscription_plan_id = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
