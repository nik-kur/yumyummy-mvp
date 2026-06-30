"""
Unit tests for the cross-platform identity / auth / entitlement foundation.

Covers (no HTTP layer):
  * JWT mint / verify (roundtrip, bad secret, expiry)
  * One-time codes (email OTP + telegram link)
  * find_or_create_account_for_identity + get_primary_user
  * Account-level entitlement aggregation (union across members)
  * Configurable trial length
  * Telegram <-> app account/diary MERGE (the unified-profile crux)

Uses an in-memory SQLite database, mirroring the existing test suite.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.user import User
from app.models.account import Account, Identity
from app.models.auth_code import AuthOneTimeCode
from app.models.user_day import UserDay
from app.models.meal_entry import MealEntry
from app.models.saved_meal import SavedMeal

from app.core import jwt_auth
from app.auth import codes
from app.auth.service import (
    find_or_create_account_for_identity,
    get_primary_user,
    account_member_users,
    ensure_account_for_telegram_user,
)
from app.auth.merge import merge_users, link_telegram_account
from app.billing.account_access import (
    compute_account_access_status,
    account_has_access,
    account_billing_snapshot,
)
from app.billing.plans import resolve_trial_days


SECRET = "unit-test-jwt-secret"

engine = create_engine("sqlite:///:memory:")
Session = sessionmaker(bind=engine)


def _utcnow():
    return datetime.now(timezone.utc)


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


# ===== JWT =====

class TestJwt:
    def test_roundtrip(self):
        token = jwt_auth.create_access_token(42, secret=SECRET, ttl_days=1)
        assert jwt_auth.account_id_from_token(token, secret=SECRET) == 42

    def test_bad_secret(self):
        token = jwt_auth.create_access_token(42, secret=SECRET, ttl_days=1)
        with pytest.raises(jwt_auth.TokenError):
            jwt_auth.decode_access_token(token, secret="wrong-secret")

    def test_expired(self):
        token = jwt_auth.create_access_token(42, secret=SECRET, ttl_days=-1)
        with pytest.raises(jwt_auth.TokenError):
            jwt_auth.decode_access_token(token, secret=SECRET)

    def test_no_secret_configured(self, monkeypatch):
        monkeypatch.setattr(jwt_auth.settings, "jwt_secret", None)
        with pytest.raises(jwt_auth.TokenError):
            jwt_auth.create_access_token(1)


# ===== One-time codes =====

class TestEmailCodes:
    def test_verify_success_consumes(self, db):
        code, _ = codes.create_email_login_code(db, "User@Example.com")
        assert codes.verify_email_login_code(db, "user@example.com", code) is True
        # second use fails (consumed)
        assert codes.verify_email_login_code(db, "user@example.com", code) is False

    def test_wrong_code(self, db):
        codes.create_email_login_code(db, "a@b.com")
        assert codes.verify_email_login_code(db, "a@b.com", "000000") is False

    def test_expired_code(self, db):
        code, row = codes.create_email_login_code(db, "a@b.com")
        row.expires_at = _utcnow() - timedelta(minutes=1)
        db.commit()
        assert codes.verify_email_login_code(db, "a@b.com", code) is False


class TestTelegramLinkCodes:
    def test_consume_returns_account(self, db):
        acct = Account()
        db.add(acct)
        db.commit()
        code, _ = codes.create_telegram_link_code(db, account_id=acct.id, telegram_id="555")
        row = codes.consume_telegram_link_code(db, code)
        assert row is not None
        assert row.account_id == acct.id
        # consumed -> second attempt fails
        assert codes.consume_telegram_link_code(db, code) is None


# ===== find_or_create / primary user =====

class TestFindOrCreate:
    def test_creates_account_identity_and_user(self, db):
        acct, created = find_or_create_account_for_identity(
            db, provider="apple", provider_id="apple-sub-1", email="Foo@Bar.com"
        )
        assert created is True
        assert acct.primary_email == "foo@bar.com"
        ident = db.query(Identity).filter(Identity.account_id == acct.id).one()
        assert ident.provider == "apple" and ident.provider_id == "apple-sub-1"
        members = account_member_users(db, acct.id)
        assert len(members) == 1 and members[0].telegram_id is None

    def test_idempotent_for_same_identity(self, db):
        a1, c1 = find_or_create_account_for_identity(db, provider="google", provider_id="g1")
        a2, c2 = find_or_create_account_for_identity(db, provider="google", provider_id="g1")
        assert c1 is True and c2 is False
        assert a1.id == a2.id

    def test_distinct_identities_distinct_accounts(self, db):
        a1, _ = find_or_create_account_for_identity(db, provider="google", provider_id="g1")
        a2, _ = find_or_create_account_for_identity(db, provider="google", provider_id="g2")
        assert a1.id != a2.id

    def test_get_primary_user_creates_when_missing(self, db):
        acct = Account()
        db.add(acct)
        db.commit()
        user = get_primary_user(db, acct)
        db.commit()
        assert user.account_id == acct.id

    def test_ensure_account_for_legacy_telegram_user(self, db):
        u = User(telegram_id="9001")
        db.add(u)
        db.commit()
        acct = ensure_account_for_telegram_user(db, u)
        assert u.account_id == acct.id
        ident = db.query(Identity).filter(Identity.account_id == acct.id).one()
        assert ident.provider == "telegram" and ident.provider_id == "9001"


# ===== Entitlement aggregation =====

class TestAccountEntitlement:
    def _account_with_user(self, db, **user_kwargs):
        acct = Account()
        db.add(acct)
        db.flush()
        u = User(account_id=acct.id, **user_kwargs)
        db.add(u)
        db.commit()
        return acct, u

    def test_new_account_is_new_but_has_demo_access(self, db):
        acct, _ = self._account_with_user(db)
        assert compute_account_access_status(db, acct) == "new"
        assert account_has_access(db, acct) is True  # demo budget

    def test_active_subscription(self, db):
        acct, _ = self._account_with_user(
            db, subscription_ends_at=_utcnow() + timedelta(days=30)
        )
        assert compute_account_access_status(db, acct) == "active"
        assert account_has_access(db, acct) is True

    def test_trial(self, db):
        acct, _ = self._account_with_user(
            db, trial_ends_at=_utcnow() + timedelta(days=2)
        )
        assert compute_account_access_status(db, acct) == "trial"

    def test_expired_subscription_blocks(self, db):
        acct, _ = self._account_with_user(
            db, subscription_ends_at=_utcnow() - timedelta(days=1)
        )
        assert compute_account_access_status(db, acct) == "expired"
        assert account_has_access(db, acct) is False

    def test_union_across_members(self, db):
        # Two member users; one expired, one active -> account is active.
        acct = Account()
        db.add(acct)
        db.flush()
        db.add(User(account_id=acct.id, subscription_ends_at=_utcnow() - timedelta(days=5)))
        db.add(User(account_id=acct.id, subscription_ends_at=_utcnow() + timedelta(days=20)))
        db.commit()
        assert compute_account_access_status(db, acct) == "active"
        snap = account_billing_snapshot(db, acct)
        assert snap["access_status"] == "active"
        assert snap["subscription_ends_at"] is not None


# ===== Configurable trial =====

class TestTrialDays:
    def test_allowed_values(self):
        assert resolve_trial_days(3) == 3
        assert resolve_trial_days(7) == 7

    def test_invalid_falls_back_to_default(self):
        assert resolve_trial_days(99) == 3
        assert resolve_trial_days(None) == 3


# ===== Merge (unified profile) =====

class TestMerge:
    def test_link_unifies_diary_and_entitlement(self, db):
        # Telegram account A with history + active sub.
        acct_a = Account()
        db.add(acct_a)
        db.flush()
        u_a = User(
            telegram_id="111",
            account_id=acct_a.id,
            subscription_ends_at=_utcnow() + timedelta(days=30),
            onboarding_completed=True,
            goal_type="lose",
        )
        db.add(u_a)
        db.add(Identity(account_id=acct_a.id, provider="telegram", provider_id="111"))
        db.flush()
        d1 = date(2026, 6, 1)
        d2 = date(2026, 6, 2)
        day_a1 = UserDay(user_id=u_a.id, date=d1, total_calories=100, total_protein_g=10, total_fat_g=5, total_carbs_g=8)
        db.add(day_a1)
        db.flush()
        db.add(MealEntry(user_id=u_a.id, user_day_id=day_a1.id, description_user="m1", calories=100, protein_g=10, fat_g=5, carbs_g=8))

        # App account B (Apple) with its own history (overlapping date d1 + new d2).
        acct_b, _ = find_or_create_account_for_identity(db, provider="apple", provider_id="apple-1")
        u_b = account_member_users(db, acct_b.id)[0]
        day_b1 = UserDay(user_id=u_b.id, date=d1, total_calories=200, total_protein_g=20, total_fat_g=10, total_carbs_g=16)
        day_b2 = UserDay(user_id=u_b.id, date=d2, total_calories=50, total_protein_g=5, total_fat_g=2, total_carbs_g=4)
        db.add_all([day_b1, day_b2])
        db.flush()
        db.add(MealEntry(user_id=u_b.id, user_day_id=day_b1.id, description_user="m2", calories=200, protein_g=20, fat_g=10, carbs_g=16))
        db.add(MealEntry(user_id=u_b.id, user_day_id=day_b2.id, description_user="m3", calories=50, protein_g=5, fat_g=2, carbs_g=4))
        db.commit()

        acct_b_id = acct_b.id

        # Redeem: telegram account A merges INTO the app account B (survivor).
        result = link_telegram_account(db, source_account=acct_a, target_account=acct_b)
        assert result == "linked"

        # Account A is gone; B survives.
        assert db.query(Account).filter(Account.id == acct_a.id).first() is None
        survivor = db.query(Account).filter(Account.id == acct_b_id).first()
        assert survivor is not None

        # Exactly one member user remains, holding the unified diary.
        members = account_member_users(db, acct_b_id)
        assert len(members) == 1
        primary = members[0]
        assert primary.telegram_id == "111"        # inherited from telegram user
        assert primary.onboarding_completed is True
        assert primary.goal_type == "lose"

        # All 3 meals now belong to the survivor.
        meal_count = db.query(MealEntry).filter(MealEntry.user_id == primary.id).count()
        assert meal_count == 3

        # Same-date day totals merged (100 + 200), new date preserved.
        merged_d1 = db.query(UserDay).filter(UserDay.user_id == primary.id, UserDay.date == d1).all()
        assert len(merged_d1) == 1
        assert merged_d1[0].total_calories == 300
        merged_d2 = db.query(UserDay).filter(UserDay.user_id == primary.id, UserDay.date == d2).all()
        assert len(merged_d2) == 1 and merged_d2[0].total_calories == 50

        # Identities: both telegram + apple now point at the survivor.
        providers = {i.provider for i in db.query(Identity).filter(Identity.account_id == acct_b_id).all()}
        assert providers == {"apple", "telegram"}

        # Entitlement unified -> active.
        assert compute_account_access_status(db, survivor) == "active"

    def test_link_repoints_history_into_empty_app_account(self, db):
        """Production repro for the /auth/link/telegram/redeem IntegrityError.

        A brand-new app account (empty diary) links a Telegram account that
        already has several days of history. Because none of the source days
        share a date with the (empty) target, every day takes the *re-point*
        branch (``sd.user_id = target.id``) rather than the same-date *merge*
        branch the original test exercised. Previously that re-point shared a
        flush with the source DELETE, so the default ``User.days`` cascade reset
        ``user_days.user_id`` to NULL and violated its NOT NULL constraint.
        """
        # App account B (Apple sign-in) — fresh, empty diary.
        acct_b, _ = find_or_create_account_for_identity(db, provider="apple", provider_id="apple-2")
        acct_b_id = acct_b.id

        # Telegram account A with 5 distinct days of history (none shared w/ B).
        acct_a = Account()
        db.add(acct_a)
        db.flush()
        u_a = User(telegram_id="222", account_id=acct_a.id, onboarding_completed=True, goal_type="gain")
        db.add(u_a)
        db.add(Identity(account_id=acct_a.id, provider="telegram", provider_id="222"))
        db.flush()
        for i in range(1, 6):
            ud = UserDay(
                user_id=u_a.id, date=date(2026, 6, i),
                total_calories=100 + i, total_protein_g=10, total_fat_g=5, total_carbs_g=8,
            )
            db.add(ud)
            db.flush()
            db.add(MealEntry(
                user_id=u_a.id, user_day_id=ud.id, description_user=f"m{i}",
                calories=100 + i, protein_g=10, fat_g=5, carbs_g=8,
            ))
        db.commit()
        source_user_id = u_a.id

        # Force the source's diary relationship collections to be resident in
        # memory before the merge. That is the exact condition under which the
        # old single-flush ``db.delete(source)`` reset user_days.user_id to NULL
        # (SQLAlchemy treats the in-memory children as the deleted parent's and
        # disassociates them). Without this the bug doesn't reproduce on SQLite.
        _ = list(u_a.days)
        _ = list(u_a.meals)

        # Redeem: telegram account A merges INTO the empty app account B.
        result = link_telegram_account(db, source_account=acct_a, target_account=acct_b)
        assert result == "linked"

        # Source account+user gone; B survives with one unified container.
        assert db.query(Account).filter(Account.id == acct_a.id).first() is None
        members = account_member_users(db, acct_b_id)
        assert len(members) == 1
        primary = members[0]
        assert primary.telegram_id == "222"

        # All 5 days + 5 meals re-pointed onto the survivor, none orphaned.
        assert db.query(UserDay).filter(UserDay.user_id == primary.id).count() == 5
        assert db.query(MealEntry).filter(MealEntry.user_id == primary.id).count() == 5
        assert db.query(UserDay).filter(UserDay.user_id == source_user_id).count() == 0
        assert db.query(UserDay).count() == 5  # nothing lost / nullified

    def test_link_same_account_is_noop(self, db):
        acct, _ = find_or_create_account_for_identity(db, provider="apple", provider_id="apple-x")
        assert link_telegram_account(db, source_account=acct, target_account=acct) == "already_linked"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
