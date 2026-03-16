from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    telegram_payment_charge_id = Column(String, unique=True, nullable=False, index=True)
    provider_payment_charge_id = Column(String, nullable=True)
    plan_id = Column(String, nullable=False)
    amount_xtr = Column(Integer, nullable=False)
    currency = Column(String, default="XTR", nullable=False)
    is_recurring = Column(Boolean, default=False, nullable=False)
    is_first_recurring = Column(Boolean, default=False, nullable=False)
    invoice_payload = Column(String, nullable=True)
    raw_payload = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="payment_events")
