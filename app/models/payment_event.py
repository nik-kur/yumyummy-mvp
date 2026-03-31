from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    provider = Column(String, nullable=False, default="telegram")
    provider_event_id = Column(String, nullable=True, index=True)

    telegram_payment_charge_id = Column(String, nullable=True, index=True)
    provider_payment_charge_id = Column(String, nullable=True)
    gumroad_sale_id = Column(String, nullable=True, index=True)
    gumroad_subscription_id = Column(String, nullable=True, index=True)
    paddle_transaction_id = Column(String, nullable=True, index=True)
    paddle_subscription_id = Column(String, nullable=True, index=True)

    plan_id = Column(String, nullable=False)
    amount_cents = Column(Integer, nullable=True)
    amount_xtr = Column(Integer, nullable=True)
    currency = Column(String, default="USD", nullable=False)

    event_type = Column(String, nullable=False, default="purchase")
    is_recurring = Column(Boolean, default=False, nullable=False)
    is_first_recurring = Column(Boolean, default=False, nullable=False)
    invoice_payload = Column(String, nullable=True)
    raw_payload = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="payment_events")
