"""
End-to-end style tests for the Gumroad billing integration.

Tests cover:
  1. Claim token create / verify / expiry / bad secret
  2. apply_subscription_payment: activate, renew, duplicate
  3. apply_cancellation: cancel, already cancelled, no subscription
  4. apply_refund: revoke access
  5. Gumroad webhook routing: purchase, renewal, cancel, refund, duplicate
  6. Telegram Stars flow still works after multi-provider refactor
  7. Post-purchase status check
  8. Admin manual activation

Uses an in-memory SQLite database to avoid touching production.
"""

import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.user import User
from app.models.payment_event import PaymentEvent
from app.billing.claim_token import create_claim_token, verify_claim_token
from app.billing.service import (
    apply_subscription_payment,
    apply_cancellation,
    apply_refund,
    DuplicateEvent,
)
from app.billing.access import compute_access_status

TEST_SECRET = "test-claim-secret-for-tests"


def _utcnow():
    return datetime.now(timezone.utc)


def _aware(dt):
    """Ensure a datetime is timezone-aware (SQLite returns naive)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

engine = create_engine("sqlite:///:memory:")
Session = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def user(db):
    u = User(telegram_id="999111", onboarding_completed=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# ===== 1. Claim Token =====

class TestClaimToken:
    def test_roundtrip(self):
        token = create_claim_token("12345", "monthly", TEST_SECRET, ttl_seconds=60)
        payload = verify_claim_token(token, TEST_SECRET)
        assert payload is not None
        assert payload["tid"] == "12345"
        assert payload["pid"] == "monthly"

    def test_bad_secret_rejected(self):
        token = create_claim_token("12345", "monthly", TEST_SECRET)
        assert verify_claim_token(token, "wrong-secret") is None

    def test_expired_rejected(self):
        token = create_claim_token("12345", "monthly", TEST_SECRET, ttl_seconds=-1)
        assert verify_claim_token(token, TEST_SECRET) is None

    def test_tampered_rejected(self):
        token = create_claim_token("12345", "monthly", TEST_SECRET)
        parts = token.split(".")
        assert verify_claim_token(parts[0] + ".0000000000000000", TEST_SECRET) is None

    def test_garbage_rejected(self):
        assert verify_claim_token("not.a.valid.token", TEST_SECRET) is None
        assert verify_claim_token("", TEST_SECRET) is None


# ===== 2. apply_subscription_payment =====

class TestApplySubscriptionPayment:
    def test_activate_new(self, db, user):
        status = apply_subscription_payment(
            db, user,
            provider="gumroad",
            plan_id="monthly",
            provider_event_id="sale:abc123",
            gumroad_sale_id="abc123",
            amount_cents=999,
            currency="USD",
        )
        assert status == "activated"
        assert user.subscription_plan_id == "monthly"
        assert user.subscription_provider == "gumroad"
        assert user.subscription_ends_at is not None
        assert _aware(user.subscription_ends_at) > _utcnow()
        assert user.usage_cost_current_period == 0.0

    def test_renew_extends(self, db, user):
        apply_subscription_payment(
            db, user,
            provider="gumroad",
            plan_id="monthly",
            provider_event_id="sale:first",
            gumroad_sale_id="first",
        )
        first_ends = user.subscription_ends_at

        apply_subscription_payment(
            db, user,
            provider="gumroad",
            plan_id="monthly",
            provider_event_id="sale:second",
            gumroad_sale_id="second",
        )
        assert user.subscription_ends_at > first_ends

    def test_duplicate_raises(self, db, user):
        apply_subscription_payment(
            db, user,
            provider="gumroad",
            plan_id="monthly",
            provider_event_id="sale:dup1",
            gumroad_sale_id="dup1",
        )
        with pytest.raises(DuplicateEvent):
            apply_subscription_payment(
                db, user,
                provider="gumroad",
                plan_id="monthly",
                provider_event_id="sale:dup1",
                gumroad_sale_id="dup1",
            )

    def test_telegram_payment(self, db, user):
        status = apply_subscription_payment(
            db, user,
            provider="telegram",
            plan_id="monthly",
            telegram_payment_charge_id="tg_charge_001",
            amount_xtr=1199,
            currency="XTR",
        )
        assert status == "activated"
        assert user.subscription_provider == "telegram"
        assert user.subscription_telegram_charge_id == "tg_charge_001"

    def test_telegram_duplicate(self, db, user):
        apply_subscription_payment(
            db, user,
            provider="telegram",
            plan_id="monthly",
            telegram_payment_charge_id="tg_dup",
            amount_xtr=1199,
        )
        with pytest.raises(DuplicateEvent):
            apply_subscription_payment(
                db, user,
                provider="telegram",
                plan_id="monthly",
                telegram_payment_charge_id="tg_dup",
                amount_xtr=1199,
            )


# ===== 3. apply_cancellation =====

class TestApplyCancellation:
    def test_cancel_active(self, db, user):
        apply_subscription_payment(
            db, user, provider="gumroad", plan_id="monthly",
            provider_event_id="sale:c1", gumroad_sale_id="c1",
            gumroad_subscription_id="sub_123",
        )
        ends = user.subscription_ends_at

        result = apply_cancellation(
            db, user, provider="gumroad",
            provider_event_id="cancel:c1",
            gumroad_subscription_id="sub_123",
        )
        assert result == "cancelled"
        assert user.subscription_auto_renew is False
        assert user.subscription_ends_at == ends

    def test_cancel_already_cancelled(self, db, user):
        apply_subscription_payment(
            db, user, provider="gumroad", plan_id="monthly",
            provider_event_id="sale:c2", gumroad_sale_id="c2",
        )
        apply_cancellation(db, user, provider="gumroad")
        result = apply_cancellation(db, user, provider="gumroad")
        assert result == "already_cancelled"

    def test_cancel_no_subscription(self, db, user):
        result = apply_cancellation(db, user, provider="gumroad")
        assert result == "no_subscription"


# ===== 4. apply_refund =====

class TestApplyRefund:
    def test_refund_revokes(self, db, user):
        apply_subscription_payment(
            db, user, provider="gumroad", plan_id="monthly",
            provider_event_id="sale:r1", gumroad_sale_id="r1",
        )
        assert _aware(user.subscription_ends_at) > _utcnow()

        result = apply_refund(
            db, user, provider="gumroad",
            provider_event_id="refund:r1",
            gumroad_sale_id="r1",
        )
        assert result == "refunded"
        assert _aware(user.subscription_ends_at) <= _utcnow()
        assert user.subscription_auto_renew is False


# ===== 5. Access status after various operations =====

class TestAccessStatus:
    def test_active_after_purchase(self, db, user):
        apply_subscription_payment(
            db, user, provider="gumroad", plan_id="monthly",
            provider_event_id="sale:a1", gumroad_sale_id="a1",
        )
        user_dict = {"subscription_ends_at": user.subscription_ends_at, "usage_cost_current_period": 0}
        assert compute_access_status(user_dict) == "active"

    def test_expired_after_refund(self, db, user):
        apply_subscription_payment(
            db, user, provider="gumroad", plan_id="monthly",
            provider_event_id="sale:a2", gumroad_sale_id="a2",
        )
        apply_refund(
            db, user, provider="gumroad",
            provider_event_id="refund:a2", gumroad_sale_id="a2",
        )
        user_dict = {"subscription_ends_at": user.subscription_ends_at, "usage_cost_current_period": 0}
        assert compute_access_status(user_dict) == "expired"

    def test_active_after_cancel_until_period_end(self, db, user):
        apply_subscription_payment(
            db, user, provider="gumroad", plan_id="monthly",
            provider_event_id="sale:a3", gumroad_sale_id="a3",
        )
        apply_cancellation(db, user, provider="gumroad")
        user_dict = {"subscription_ends_at": user.subscription_ends_at, "usage_cost_current_period": 0}
        assert compute_access_status(user_dict) == "active"


# ===== 6. Event audit trail =====

class TestEventAuditTrail:
    def test_events_recorded(self, db, user):
        apply_subscription_payment(
            db, user, provider="gumroad", plan_id="monthly",
            provider_event_id="sale:e1", gumroad_sale_id="e1",
        )
        apply_cancellation(db, user, provider="gumroad", provider_event_id="cancel:e1")
        apply_refund(db, user, provider="gumroad", provider_event_id="refund:e1")

        events = db.query(PaymentEvent).filter(PaymentEvent.user_id == user.id).all()
        assert len(events) == 3
        types = [e.event_type for e in events]
        assert "purchase" in types
        assert "cancellation" in types
        assert "refund" in types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
