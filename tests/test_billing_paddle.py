"""
Tests for the Paddle billing integration.

Covers:
  1. ``apply_subscription_payment`` honours ``period_ends_at`` from Paddle
     instead of falling back to "now + 30 days".
  2. ``sync_subscription_state`` updates only the fields it's asked to.
  3. The Paddle reconciliation flow correctly mirrors API responses
     (active / canceled / paused / past_due) onto the local user.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.user import User
from app.billing.service import (
    apply_subscription_payment,
    sync_subscription_state,
)
from app.billing.paddle_reconcile import reconcile_user
from app.external.paddle_client import (
    extract_period_ends_at,
    parse_paddle_datetime,
)


def _utcnow():
    return datetime.now(timezone.utc)


def _aware(dt):
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
    u = User(
        telegram_id="paddle_user_1",
        onboarding_completed=True,
        subscription_paddle_id="sub_test_abc",
        subscription_provider="paddle",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# ===== 1. parse_paddle_datetime =====


class TestParsePaddleDatetime:
    def test_z_suffix(self):
        dt = parse_paddle_datetime("2026-04-29T12:00:00.000Z")
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.year == 2026 and dt.month == 4 and dt.day == 29

    def test_offset_form(self):
        dt = parse_paddle_datetime("2026-04-29T12:00:00+00:00")
        assert dt is not None and dt.utcoffset().total_seconds() == 0

    def test_garbage_returns_none(self):
        assert parse_paddle_datetime("not-a-date") is None
        assert parse_paddle_datetime(None) is None
        assert parse_paddle_datetime("") is None


# ===== 2. extract_period_ends_at on Paddle subscription resource shape =====


class TestExtractPeriodEndsAt:
    def test_prefers_current_billing_period(self):
        sub = {
            "current_billing_period": {
                "starts_at": "2026-03-29T12:00:00Z",
                "ends_at": "2026-04-29T12:00:00Z",
            },
            "next_billed_at": "2026-05-15T12:00:00Z",
        }
        ends = extract_period_ends_at(sub)
        assert ends.day == 29 and ends.month == 4

    def test_falls_back_to_next_billed_at(self):
        sub = {"next_billed_at": "2026-04-29T12:00:00Z"}
        ends = extract_period_ends_at(sub)
        assert ends.day == 29 and ends.month == 4

    def test_falls_back_to_scheduled_change(self):
        sub = {
            "scheduled_change": {
                "action": "cancel",
                "effective_at": "2026-04-29T12:00:00Z",
            }
        }
        ends = extract_period_ends_at(sub)
        assert ends.day == 29 and ends.month == 4

    def test_none_when_nothing_present(self):
        assert extract_period_ends_at({}) is None


# ===== 3. apply_subscription_payment with explicit period_ends_at =====


class TestPaddleSubscriptionPayment:
    def test_uses_paddle_provided_end_date(self, db, user):
        """The whole point of the fix: trust Paddle's calendar-month date,
        not 'now + 30 days'."""
        target_ends = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)

        status = apply_subscription_payment(
            db, user,
            provider="paddle",
            plan_id="monthly",
            paddle_transaction_id="txn_001",
            paddle_subscription_id="sub_test_abc",
            period_ends_at=target_ends,
            event_type="purchase",
        )
        assert status == "activated"
        assert _aware(user.subscription_ends_at) == target_ends

    def test_paddle_renew_uses_paddle_date_not_arithmetic(self, db, user):
        """Renewal must overwrite ends_at with Paddle's new period end,
        not extend the previous local date by 30 days (which would drift)."""
        first = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)
        apply_subscription_payment(
            db, user,
            provider="paddle", plan_id="monthly",
            paddle_transaction_id="txn_001",
            paddle_subscription_id="sub_test_abc",
            period_ends_at=first,
            event_type="purchase",
        )
        # Paddle next billing period: calendar month, 31 days
        second = datetime(2026, 5, 29, 12, 0, 0, tzinfo=timezone.utc)
        apply_subscription_payment(
            db, user,
            provider="paddle", plan_id="monthly",
            paddle_transaction_id="txn_002",
            paddle_subscription_id="sub_test_abc",
            period_ends_at=second,
            event_type="purchase",
        )
        assert _aware(user.subscription_ends_at) == second

    def test_no_paddle_date_falls_back_to_period_days(self, db, user):
        """Other providers without an explicit date keep the old behaviour."""
        before = _utcnow()
        apply_subscription_payment(
            db, user,
            provider="gumroad", plan_id="monthly",
            provider_event_id="sale:noenddate",
            gumroad_sale_id="noenddate",
        )
        ends = _aware(user.subscription_ends_at)
        assert ends > before + timedelta(days=29)
        assert ends < before + timedelta(days=31)


# ===== 4. sync_subscription_state =====


class TestSyncSubscriptionState:
    def test_updates_end_date(self, db, user):
        # Seed an active sub
        apply_subscription_payment(
            db, user, provider="paddle", plan_id="monthly",
            paddle_transaction_id="txn_seed",
            paddle_subscription_id="sub_test_abc",
            period_ends_at=datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc),
        )
        new_end = datetime(2026, 5, 31, 12, 0, 0, tzinfo=timezone.utc)
        result = sync_subscription_state(
            db, user, provider="paddle", period_ends_at=new_end,
        )
        assert result == "updated"
        assert _aware(user.subscription_ends_at) == new_end

    def test_revoke_zeroes_access(self, db, user):
        apply_subscription_payment(
            db, user, provider="paddle", plan_id="monthly",
            paddle_transaction_id="txn_seed2",
            paddle_subscription_id="sub_test_abc",
            period_ends_at=_utcnow() + timedelta(days=10),
        )
        result = sync_subscription_state(db, user, provider="paddle", revoke=True)
        assert result == "updated"
        assert _aware(user.subscription_ends_at) <= _utcnow()
        assert user.subscription_auto_renew is False

    def test_unchanged_when_already_synced(self, db, user):
        ends = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)
        apply_subscription_payment(
            db, user, provider="paddle", plan_id="monthly",
            paddle_transaction_id="txn_seed3",
            paddle_subscription_id="sub_test_abc",
            period_ends_at=ends,
        )
        result = sync_subscription_state(
            db, user, provider="paddle",
            period_ends_at=ends, auto_renew=True,
        )
        assert result == "unchanged"


# ===== 5. reconcile_user =====


def _paddle_sub_response(status="active", ends_at="2026-04-29T12:00:00Z",
                         scheduled=None):
    body = {
        "id": "sub_test_abc",
        "status": status,
        "current_billing_period": {
            "starts_at": "2026-03-29T12:00:00Z",
            "ends_at": ends_at,
        },
        "next_billed_at": ends_at,
    }
    if scheduled:
        body["scheduled_change"] = scheduled
    return body


class TestReconcileUser:
    def test_active_sub_pulls_paddle_end_date(self, db, user):
        # Local DB has stale (off-by-one) end date
        user.subscription_plan_id = "monthly"
        user.subscription_ends_at = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        user.subscription_auto_renew = True
        db.commit()

        with patch(
            "app.billing.paddle_reconcile.get_subscription",
            new=AsyncMock(return_value=_paddle_sub_response(
                status="active",
                ends_at="2026-04-29T12:00:00Z",
            )),
        ):
            result = asyncio.run(reconcile_user(db, user))

        assert result.status == "updated"
        assert result.paddle_status == "active"
        assert _aware(user.subscription_ends_at) == datetime(
            2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc,
        )
        assert user.subscription_auto_renew is True

    def test_paused_revokes_access(self, db, user):
        user.subscription_plan_id = "monthly"
        user.subscription_ends_at = _utcnow() + timedelta(days=15)
        user.subscription_auto_renew = True
        db.commit()

        with patch(
            "app.billing.paddle_reconcile.get_subscription",
            new=AsyncMock(return_value=_paddle_sub_response(status="paused")),
        ):
            result = asyncio.run(reconcile_user(db, user))

        assert result.status == "revoked"
        assert _aware(user.subscription_ends_at) <= _utcnow()
        assert user.subscription_auto_renew is False

    def test_canceled_keeps_access_until_period_end(self, db, user):
        user.subscription_plan_id = "monthly"
        user.subscription_ends_at = _utcnow() + timedelta(days=15)
        user.subscription_auto_renew = True
        db.commit()

        with patch(
            "app.billing.paddle_reconcile.get_subscription",
            new=AsyncMock(return_value=_paddle_sub_response(
                status="canceled",
                ends_at="2026-05-15T00:00:00Z",
            )),
        ):
            result = asyncio.run(reconcile_user(db, user))

        assert result.status == "updated"
        assert user.subscription_auto_renew is False
        # Access still valid until the end of the paid period
        assert _aware(user.subscription_ends_at) == datetime(
            2026, 5, 15, 0, 0, 0, tzinfo=timezone.utc,
        )

    def test_scheduled_cancel_disables_auto_renew(self, db, user):
        user.subscription_plan_id = "monthly"
        user.subscription_ends_at = _utcnow() + timedelta(days=15)
        user.subscription_auto_renew = True
        db.commit()

        with patch(
            "app.billing.paddle_reconcile.get_subscription",
            new=AsyncMock(return_value=_paddle_sub_response(
                status="active",
                scheduled={"action": "cancel", "effective_at": "2026-05-29T12:00:00Z"},
            )),
        ):
            asyncio.run(reconcile_user(db, user))

        assert user.subscription_auto_renew is False

    def test_no_paddle_id(self, db, user):
        user.subscription_paddle_id = None
        db.commit()
        result = asyncio.run(reconcile_user(db, user))
        assert result.status == "no_subscription"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
