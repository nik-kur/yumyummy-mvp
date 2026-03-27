from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BillingStatusResponse(BaseModel):
    telegram_id: str
    access_status: str
    trial_started_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    trial_days_remaining: Optional[float] = None
    subscription_plan_id: Optional[str] = None
    subscription_ends_at: Optional[datetime] = None
    subscription_auto_renew: Optional[bool] = None
    subscription_provider: Optional[str] = None
    usage_cost_current_period: Optional[float] = None
    usage_cap_usd: Optional[float] = None
    usage_exceeded: Optional[bool] = None


class TrialStartRequest(BaseModel):
    telegram_id: str


class TrialStartResponse(BaseModel):
    telegram_id: str
    trial_started_at: datetime
    trial_ends_at: datetime
    already_started: bool


class PaymentSuccessRequest(BaseModel):
    telegram_id: str
    telegram_payment_charge_id: str
    provider_payment_charge_id: Optional[str] = None
    plan_id: str
    amount_xtr: int
    currency: str = "XTR"
    is_recurring: bool = False
    is_first_recurring: bool = False
    invoice_payload: Optional[str] = None
    raw_payload: Optional[str] = None
    subscription_expiration_date: Optional[int] = None


class PaymentSuccessResponse(BaseModel):
    telegram_id: str
    status: str
    subscription_ends_at: Optional[datetime] = None
    plan_id: str


class SubscriptionCancelRequest(BaseModel):
    telegram_id: str


class SubscriptionCancelResponse(BaseModel):
    telegram_id: str
    status: str
    access_until: Optional[datetime] = None


class GumroadCheckoutRequest(BaseModel):
    telegram_id: str
    plan_id: str


class GumroadCheckoutResponse(BaseModel):
    checkout_url: str
    plan_id: str
    expires_in_seconds: int


class PaddleCheckoutRequest(BaseModel):
    telegram_id: str
    plan_id: str


class PaddleCheckoutResponse(BaseModel):
    checkout_url: str
    plan_id: str
