from sqlalchemy import Column, Integer, String, DateTime, func

from app.db.base import Base


class NotificationEvent(Base):
    __tablename__ = "notification_events"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, index=True, nullable=False)
    event_type = Column(String, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    extra_data = Column(String, nullable=True)
