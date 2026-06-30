"""
HTTP-level tests for the mobile API (auth + account-scoped endpoints +
Adapty webhook + upload presign).

A minimal FastAPI app is assembled from the new routers (avoiding main.py's
startup side effects) and backed by a temp-file SQLite DB so that the request
session and the agent-run persist session (a separate ``SessionLocal``) share
data — mirroring production where both hit the same Postgres.
"""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.core.config import settings
from app.core import jwt_auth
from app.deps import get_db
from app.models.user import User
from app.models.account import Account, Identity
from app.models.meal_entry import MealEntry
from app.auth import providers as auth_providers
from app.auth.service import find_or_create_account_for_identity, account_member_users
from app.auth import codes as auth_codes

from app.api.auth import router as auth_router
from app.api.app_api import router as app_api_router
from app.api.uploads import router as uploads_router
from app.api.adapty_webhook import router as adapty_webhook_router
import app.api.app_api as app_api_module


# --- temp-file DB shared across sessions/connections ---------------------
_db_fd, _db_path = tempfile.mkstemp(suffix=".sqlite")
os.close(_db_fd)
engine = create_engine(
    f"sqlite:///{_db_path}", connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


test_app = FastAPI()
test_app.include_router(auth_router)
test_app.include_router(app_api_router)
test_app.include_router(uploads_router)
test_app.include_router(adapty_webhook_router)
test_app.dependency_overrides[get_db] = _override_get_db

client = TestClient(test_app)


def _utcnow():
    return datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    Base.metadata.create_all(engine)
    # Test configuration.
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-test-secret-test-secret-32", raising=False)
    monkeypatch.setattr(settings, "auth_email_debug_return_code", True, raising=False)
    monkeypatch.setattr(settings, "adapty_webhook_secret", "whsec_test", raising=False)
    monkeypatch.setattr(settings, "storage_enabled", False, raising=False)
    monkeypatch.setattr(settings, "billing_paywall_enabled", True, raising=False)
    # The /app/agent/run persist path opens its own SessionLocal.
    monkeypatch.setattr(app_api_module, "SessionLocal", TestingSessionLocal, raising=False)
    yield
    Base.metadata.drop_all(engine)


def _make_account_token(provider="email", provider_id="user@example.com", email="user@example.com"):
    db = TestingSessionLocal()
    try:
        account, _ = find_or_create_account_for_identity(
            db, provider=provider, provider_id=provider_id, email=email
        )
        account_id = account.id
    finally:
        db.close()
    return account_id, jwt_auth.create_access_token(account_id, secret=settings.jwt_secret)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ===== Auth endpoints =====

def test_email_login_flow_returns_token_and_me():
    r = client.post("/auth/email/request", json={"email": "Foo@Example.com"})
    assert r.status_code == 200
    code = r.json()["debug_code"]
    assert code

    r = client.post("/auth/email/verify", json={"email": "foo@example.com", "code": code})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True
    token = body["access_token"]

    r = client.get("/app/me", headers=_auth(token))
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["account_id"] == body["account_id"]
    assert me["onboarding_completed"] is False
    assert me["billing"]["access_status"] == "new"
    assert "email" in me["linked_providers"]


def test_email_verify_wrong_code_rejected():
    client.post("/auth/email/request", json={"email": "a@b.com"})
    r = client.post("/auth/email/verify", json={"email": "a@b.com", "code": "000000"})
    assert r.status_code == 401


def test_apple_signin_is_idempotent(monkeypatch):
    monkeypatch.setattr(
        auth_providers,
        "verify_apple_identity_token",
        lambda tok: auth_providers.ProviderIdentity("apple", "apple-sub-42", "apple@example.com"),
    )
    r1 = client.post("/auth/apple", json={"identity_token": "x"})
    assert r1.status_code == 200, r1.text
    assert r1.json()["created"] is True
    r2 = client.post("/auth/apple", json={"identity_token": "x"})
    assert r2.status_code == 200
    assert r2.json()["created"] is False
    assert r1.json()["account_id"] == r2.json()["account_id"]


def test_me_requires_auth():
    assert client.get("/app/me").status_code == 401
    assert client.get("/app/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


# ===== Profile / trial / billing =====

def test_update_profile_and_start_trial():
    _, token = _make_account_token()

    r = client.patch("/app/me", headers=_auth(token), json={"goal_type": "lose", "onboarding_completed": True, "timezone": "Europe/Berlin"})
    assert r.status_code == 200, r.text
    assert r.json()["goal_type"] == "lose"
    assert r.json()["onboarding_completed"] is True

    r = client.post("/app/billing/trial/start", headers=_auth(token), json={"trial_days": 7})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trial_days"] == 7
    assert body["access_status"] == "trial"

    # idempotent second call
    r = client.post("/app/billing/trial/start", headers=_auth(token), json={"trial_days": 7})
    assert r.json()["already_started"] is True

    r = client.get("/app/billing/status", headers=_auth(token))
    assert r.json()["access_status"] == "trial"


def test_invalid_trial_days_falls_back_to_default():
    _, token = _make_account_token(provider_id="trial@example.com", email="trial@example.com")
    r = client.post("/app/billing/trial/start", headers=_auth(token), json={"trial_days": 99})
    assert r.json()["trial_days"] == 3


# ===== Meals / diary =====

def test_meal_crud_and_today():
    _, token = _make_account_token(provider_id="meals@example.com", email="meals@example.com")
    today = _utcnow().date().isoformat()

    r = client.post("/app/meals", headers=_auth(token), json={
        "date": today, "description_user": "Oatmeal", "calories": 300,
        "protein_g": 12, "fat_g": 6, "carbs_g": 50,
    })
    assert r.status_code == 200, r.text
    meal_id = r.json()["id"]

    r = client.get("/app/today", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["total_calories"] == 300
    assert len(r.json()["meals"]) == 1

    r = client.get("/app/meals/recent", headers=_auth(token))
    assert len(r.json()) == 1

    r = client.delete(f"/app/meals/{meal_id}", headers=_auth(token))
    assert r.status_code == 200

    r = client.get("/app/today", headers=_auth(token))
    assert r.json()["total_calories"] == 0


def test_saved_meals():
    _, token = _make_account_token(provider_id="sm@example.com", email="sm@example.com")
    r = client.post("/app/saved-meals", headers=_auth(token), json={
        "user_id": 0, "name": "My Bowl", "total_calories": 450,
        "items": [{"name": "rice", "calories_kcal": 200}],
    })
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "My Bowl"
    r = client.get("/app/saved-meals", headers=_auth(token))
    assert r.json()["total"] == 1


# ===== Agent run (logging via AI) =====

def test_agent_run_persists_meal(monkeypatch):
    account_id, token = _make_account_token(provider_id="agent@example.com", email="agent@example.com")

    async def fake_workflow(**kwargs):
        return {
            "intent": "log_meal",
            "message_text": "Logged banana",
            "confidence": "HIGH",
            "totals": {"calories_kcal": 250, "protein_g": 3, "fat_g": 1, "carbs_g": 60},
            "items": [{"name": "banana", "grams": 240, "calories_kcal": 250, "protein_g": 3, "fat_g": 1, "carbs_g": 60}],
            "source_url": None,
            "_usage": {"cost": {"estimated_total_cost_usd": 0.01}, "input_tokens": 10, "output_tokens": 5},
        }

    monkeypatch.setattr(app_api_module, "run_yumyummy_workflow", fake_workflow)

    r = client.post("/app/agent/run", headers=_auth(token), json={"text": "1 banana"})
    assert r.status_code == 200, r.text
    assert r.json()["intent"] == "log_meal"

    # The meal should now be persisted under the account's primary user.
    db = TestingSessionLocal()
    try:
        members = account_member_users(db, account_id)
        ids = [u.id for u in members]
        meals = db.query(MealEntry).filter(MealEntry.user_id.in_(ids)).all()
        assert len(meals) == 1
        assert meals[0].calories == 250
    finally:
        db.close()


def test_agent_run_stores_breakdown_then_detail_and_repeat(monkeypatch):
    """The AI run stores the ingredient breakdown + source; the detail endpoint
    returns it; and Repeat re-logs the meal verbatim (no workflow call)."""
    _, token = _make_account_token(provider_id="bd@example.com", email="bd@example.com")

    calls = {"n": 0}

    async def fake_workflow(**kwargs):
        calls["n"] += 1
        return {
            "intent": "product",
            "message_text": "Logged",
            "confidence": "HIGH",
            "totals": {"calories_kcal": 372, "protein_g": 44, "fat_g": 14, "carbs_g": 18},
            "items": [
                {"name": "Сырники", "grams": 140, "calories_kcal": 250, "protein_g": 30,
                 "fat_g": 9, "carbs_g": 12, "source_url": "https://azbukalife.example/syrniki"},
                {"name": "Батончик", "grams": 60, "calories_kcal": 122, "protein_g": 14,
                 "fat_g": 5, "carbs_g": 6, "source_url": "https://exponenta.example/mango"},
            ],
            "source_url": "https://azbukalife.example/syrniki",
        }

    monkeypatch.setattr(app_api_module, "run_yumyummy_workflow", fake_workflow)

    r = client.post("/app/agent/run", headers=_auth(token), json={"text": "сырники и батончик"})
    assert r.status_code == 200, r.text

    # Exactly one meal persisted (the duplicate bug was the client also POSTing
    # /app/meals; the backend itself logs once).
    r = client.get("/app/meals/recent", headers=_auth(token))
    meals = r.json()
    assert len(meals) == 1
    meal_id = meals[0]["id"]
    assert meals[0]["source_url"] == "https://azbukalife.example/syrniki"
    assert len(meals[0]["items"]) == 2

    # Detail endpoint returns the full breakdown with per-item sources.
    r = client.get(f"/app/meals/{meal_id}", headers=_auth(token))
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["calories"] == 372
    assert detail["items"][0]["name"] == "Сырники"
    assert detail["items"][0]["source_url"].startswith("https://")

    # Repeat = verbatim re-log; no new workflow call; today doubles.
    r = client.post(f"/app/meals/{meal_id}/repeat", headers=_auth(token))
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["id"] != meal_id
    assert rep["calories"] == 372
    assert len(rep["items"]) == 2  # breakdown copied verbatim
    assert calls["n"] == 1  # workflow ran once (the original log), not for Repeat

    r = client.get("/app/today", headers=_auth(token))
    body = r.json()
    assert body["total_calories"] == 744
    assert len(body["meals"]) == 2

    # Ownership: a different account can neither read nor repeat the meal.
    _, other = _make_account_token(provider_id="other@example.com", email="other@example.com")
    assert client.get(f"/app/meals/{meal_id}", headers=_auth(other)).status_code == 404
    assert client.post(f"/app/meals/{meal_id}/repeat", headers=_auth(other)).status_code == 404


# ===== Telegram linking =====

def test_telegram_link_redeem_merges(monkeypatch):
    # App account (Apple) currently signed in.
    monkeypatch.setattr(
        auth_providers,
        "verify_apple_identity_token",
        lambda tok: auth_providers.ProviderIdentity("apple", "apple-link", "link@example.com"),
    )
    r = client.post("/auth/apple", json={"identity_token": "x"})
    app_token = r.json()["access_token"]

    # A separate Telegram account with a code, created server-side.
    db = TestingSessionLocal()
    try:
        tg_account = Account()
        db.add(tg_account)
        db.flush()
        db.add(User(telegram_id="700700", account_id=tg_account.id, onboarding_completed=True))
        db.add(Identity(account_id=tg_account.id, provider="telegram", provider_id="700700"))
        db.commit()
        code, _ = auth_codes.create_telegram_link_code(db, account_id=tg_account.id, telegram_id="700700")
    finally:
        db.close()

    r = client.post("/auth/link/telegram/redeem", headers=_auth(app_token), json={"code": code})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "linked"

    # The app account now carries the telegram id + both providers.
    r = client.get("/app/me", headers=_auth(app_token))
    me = r.json()
    assert me["telegram_id"] == "700700"
    assert set(me["linked_providers"]) == {"apple", "telegram"}


def test_telegram_link_bad_code_rejected():
    _, token = _make_account_token(provider_id="badlink@example.com", email="badlink@example.com")
    r = client.post("/auth/link/telegram/redeem", headers=_auth(token), json={"code": "NOPECODE"})
    assert r.status_code == 400


# ===== Adapty webhook =====

def test_adapty_webhook_activates_then_status_active():
    account_id, token = _make_account_token(provider_id="adapty@example.com", email="adapty@example.com")
    expires = (_utcnow() + timedelta(days=30)).isoformat()

    r = client.post(
        "/webhooks/adapty",
        headers={"Authorization": "whsec_test"},
        json={
            "event_type": "subscription_started",
            "customer_user_id": str(account_id),
            "event_properties": {"vendor_product_id": "mo_monthly", "subscription_expires_at": expires, "transaction_id": "txn_1"},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"

    r = client.get("/app/billing/status", headers=_auth(token))
    assert r.json()["access_status"] == "active"


def test_adapty_webhook_rejects_bad_secret():
    r = client.post("/webhooks/adapty", headers={"Authorization": "wrong"}, json={"event_type": "x"})
    assert r.status_code == 401


# ===== Upload presign =====

def test_presign_returns_503_when_storage_disabled():
    _, token = _make_account_token(provider_id="up@example.com", email="up@example.com")
    r = client.post("/app/uploads/meal-photo/presign", headers=_auth(token), json={"content_type": "image/jpeg"})
    assert r.status_code == 503


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
