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


def test_week_returns_seven_ordered_days_with_meals():
    _, token = _make_account_token(provider_id="week@example.com", email="week@example.com")

    # Two meals on the first day, one on the third day of the window.
    client.post("/app/meals", headers=_auth(token), json={
        "date": "2026-03-02", "description_user": "Oats", "calories": 300,
        "protein_g": 12, "fat_g": 6, "carbs_g": 50,
    })
    client.post("/app/meals", headers=_auth(token), json={
        "date": "2026-03-02", "description_user": "Coffee", "calories": 20,
        "protein_g": 1, "fat_g": 0, "carbs_g": 3,
    })
    client.post("/app/meals", headers=_auth(token), json={
        "date": "2026-03-04", "description_user": "Salad", "calories": 400,
        "protein_g": 10, "fat_g": 30, "carbs_g": 20,
    })

    r = client.get("/app/week", headers=_auth(token), params={"start": "2026-03-02"})
    assert r.status_code == 200, r.text
    days = r.json()
    assert len(days) == 7
    assert [d["date"] for d in days] == [
        "2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05",
        "2026-03-06", "2026-03-07", "2026-03-08",
    ]
    assert days[0]["total_calories"] == 320
    assert len(days[0]["meals"]) == 2
    assert days[1]["total_calories"] == 0
    assert days[1]["meals"] == []
    assert days[2]["total_calories"] == 400
    assert len(days[2]["meals"]) == 1


def test_week_requires_auth_and_valid_date():
    _, token = _make_account_token(provider_id="week2@example.com", email="week2@example.com")
    assert client.get("/app/week", params={"start": "2026-03-02"}).status_code == 401
    assert client.get("/app/week", headers=_auth(token), params={"start": "not-a-date"}).status_code == 400


def test_history_returns_totals_and_meal_counts():
    _, token = _make_account_token(provider_id="hist@example.com", email="hist@example.com")

    client.post("/app/meals", headers=_auth(token), json={
        "date": "2026-03-02", "description_user": "A", "calories": 100,
    })
    client.post("/app/meals", headers=_auth(token), json={
        "date": "2026-03-02", "description_user": "B", "calories": 200,
    })
    client.post("/app/meals", headers=_auth(token), json={
        "date": "2026-03-05", "description_user": "C", "calories": 500,
    })

    r = client.get("/app/history", headers=_auth(token),
                   params={"start": "2026-03-01", "end": "2026-03-07"})
    assert r.status_code == 200, r.text
    rows = r.json()
    # Only days with a diary row come back, ordered by date.
    assert [row["date"] for row in rows] == ["2026-03-02", "2026-03-05"]
    assert rows[0]["total_calories"] == 300
    assert rows[0]["meal_count"] == 2
    assert rows[1]["total_calories"] == 500
    assert rows[1]["meal_count"] == 1

    # Validation: end before start, and an over-long range are rejected.
    assert client.get("/app/history", headers=_auth(token),
                      params={"start": "2026-03-07", "end": "2026-03-01"}).status_code == 400
    assert client.get("/app/history", headers=_auth(token),
                      params={"start": "2020-01-01", "end": "2026-03-01"}).status_code == 400


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


def test_update_meal_items_recompute_totals_and_day():
    _, token = _make_account_token(provider_id="edit@example.com", email="edit@example.com")
    today = _utcnow().date().isoformat()

    r = client.post("/app/meals", headers=_auth(token), json={
        "date": today, "description_user": "Greek salad", "calories": 400,
        "protein_g": 10, "fat_g": 30, "carbs_g": 20,
        "items": [
            {"name": "feta", "grams": 50, "calories_kcal": 130, "protein_g": 7, "fat_g": 11, "carbs_g": 2},
            {"name": "tomatoes", "grams": 120, "calories_kcal": 22, "protein_g": 1, "fat_g": 0, "carbs_g": 5},
            {"name": "olive oil", "grams": 20, "calories_kcal": 180, "protein_g": 0, "fat_g": 20, "carbs_g": 0},
        ],
    })
    assert r.status_code == 200, r.text
    meal_id = r.json()["id"]
    assert len(r.json()["items"]) == 3

    # Drop the tomatoes: totals must be recomputed from the remaining items.
    r = client.patch(f"/app/meals/{meal_id}", headers=_auth(token), json={
        "items": [
            {"name": "feta", "grams": 50, "calories_kcal": 130, "protein_g": 7, "fat_g": 11, "carbs_g": 2},
            {"name": "olive oil", "grams": 20, "calories_kcal": 180, "protein_g": 0, "fat_g": 20, "carbs_g": 0},
        ],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["calories"] == 310
    assert body["protein_g"] == 7
    assert body["fat_g"] == 31
    assert body["carbs_g"] == 2
    assert len(body["items"]) == 2

    # The day's aggregates follow the edit (400 -> 310).
    r = client.get("/app/today", headers=_auth(token))
    assert r.json()["total_calories"] == 310

    # Direct totals edit (no items): explicit fields win.
    r = client.patch(f"/app/meals/{meal_id}", headers=_auth(token), json={
        "calories": 500, "description_user": "Greek salad (large)",
    })
    assert r.status_code == 200
    assert r.json()["calories"] == 500
    assert r.json()["description_user"] == "Greek salad (large)"
    assert len(r.json()["items"]) == 2  # breakdown untouched
    r = client.get("/app/today", headers=_auth(token))
    assert r.json()["total_calories"] == 500

    # Foreign accounts can't edit someone else's meal.
    _, other = _make_account_token(provider_id="edit2@example.com", email="edit2@example.com")
    assert client.patch(f"/app/meals/{meal_id}", headers=_auth(other), json={"calories": 1}).status_code == 404


def test_saved_meal_edit_delete_and_log():
    _, token = _make_account_token(provider_id="sm2@example.com", email="sm2@example.com")
    r = client.post("/app/saved-meals", headers=_auth(token), json={
        "user_id": 0, "name": "Bowl", "total_calories": 450,
        "total_protein_g": 30, "total_fat_g": 10, "total_carbs_g": 60,
        "items": [
            {"name": "rice", "grams": 150, "calories_kcal": 200, "protein_g": 4, "fat_g": 1, "carbs_g": 45},
            {"name": "chicken", "grams": 120, "calories_kcal": 250, "protein_g": 26, "fat_g": 9, "carbs_g": 15},
        ],
    })
    assert r.status_code == 200, r.text
    saved_id = r.json()["id"]

    # The list response now carries the breakdown (additive field).
    r = client.get("/app/saved-meals", headers=_auth(token))
    assert len(r.json()["items"][0]["items"]) == 2

    # Rename + drop a component: totals recomputed from the remaining items.
    r = client.patch(f"/app/saved-meals/{saved_id}", headers=_auth(token), json={
        "name": "Chicken bowl",
        "items": [
            {"name": "chicken", "grams": 120, "calories_kcal": 250, "protein_g": 26, "fat_g": 9, "carbs_g": 15},
        ],
    })
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Chicken bowl"
    assert r.json()["total_calories"] == 250
    assert len(r.json()["items"]) == 1

    # Log it onto today: meal carries the breakdown, use_count increments.
    r = client.post(f"/app/saved-meals/{saved_id}/log", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["calories"] == 250
    assert len(r.json()["items"]) == 1
    r = client.get("/app/today", headers=_auth(token))
    assert r.json()["total_calories"] == 250
    r = client.get("/app/saved-meals", headers=_auth(token))
    assert r.json()["items"][0]["use_count"] == 1

    # Foreign account: 404 on all mutations; then owner deletes it.
    _, other = _make_account_token(provider_id="sm3@example.com", email="sm3@example.com")
    assert client.patch(f"/app/saved-meals/{saved_id}", headers=_auth(other), json={"name": "x"}).status_code == 404
    assert client.delete(f"/app/saved-meals/{saved_id}", headers=_auth(other)).status_code == 404
    assert client.post(f"/app/saved-meals/{saved_id}/log", headers=_auth(other)).status_code == 404

    r = client.delete(f"/app/saved-meals/{saved_id}", headers=_auth(token))
    assert r.status_code == 200
    r = client.get("/app/saved-meals", headers=_auth(token))
    assert r.json()["total"] == 0


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
    # confidence HIGH (source-verified) must store EXACT, not ESTIMATE.
    assert meals[0]["accuracy_level"] == "EXACT"

    # Detail endpoint returns the full breakdown with per-item sources.
    r = client.get(f"/app/meals/{meal_id}", headers=_auth(token))
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["calories"] == 372
    assert detail["accuracy_level"] == "EXACT"
    assert detail["items"][0]["name"] == "Сырники"
    assert detail["items"][0]["source_url"].startswith("https://")

    # Repeat = verbatim re-log; no new workflow call; today doubles.
    r = client.post(f"/app/meals/{meal_id}/repeat", headers=_auth(token))
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["id"] != meal_id
    assert rep["calories"] == 372
    assert rep["accuracy_level"] == "EXACT"  # accuracy copied verbatim
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


def test_agent_run_accuracy_from_confidence_and_source(monkeypatch):
    """accuracy_level maps from the workflow's confidence AND the presence of a
    source: HIGH or any source_url => EXACT (it was looked up); a source-less
    estimate (e.g. photo) => ESTIMATE.

    Reproduces the reported bug where an official-source product (lenta.com) the
    agent returned as confidence=ESTIMATE still showed the "Estimate" badge.
    """

    def _workflow(result):
        async def fake(**kwargs):
            return result
        return fake

    # Case 1: confidence ESTIMATE but a real source was found -> EXACT.
    _, t1 = _make_account_token(provider_id="acc1@example.com", email="acc1@example.com")
    monkeypatch.setattr(app_api_module, "run_yumyummy_workflow", _workflow({
        "intent": "product", "message_text": "ok", "confidence": "ESTIMATE",
        "totals": {"calories_kcal": 175, "protein_g": 30, "fat_g": 0, "carbs_g": 15},
        "items": [{"name": "Bio-Skyr", "grams": 500, "calories_kcal": 175, "protein_g": 30,
                   "fat_g": 0, "carbs_g": 15, "source_url": "https://lenta.com/skyr"}],
        "source_url": "https://lenta.com/skyr",
    }))
    assert client.post("/app/agent/run", headers=_auth(t1), json={"text": "скир"}).status_code == 200
    m1 = client.get("/app/meals/recent", headers=_auth(t1)).json()
    assert m1[0]["accuracy_level"] == "EXACT"

    # Case 2: photo estimate, no source anywhere -> ESTIMATE.
    _, t2 = _make_account_token(provider_id="acc2@example.com", email="acc2@example.com")
    monkeypatch.setattr(app_api_module, "run_yumyummy_workflow", _workflow({
        "intent": "photo_meal", "message_text": "ok", "confidence": "ESTIMATE",
        "totals": {"calories_kcal": 400, "protein_g": 20, "fat_g": 15, "carbs_g": 40},
        "items": [{"name": "Plate", "grams": 300, "calories_kcal": 400, "protein_g": 20,
                   "fat_g": 15, "carbs_g": 40, "source_url": None}],
        "source_url": None,
    }))
    assert client.post("/app/agent/run", headers=_auth(t2), json={"text": "(photo)"}).status_code == 200
    m2 = client.get("/app/meals/recent", headers=_auth(t2)).json()
    assert m2[0]["accuracy_level"] == "ESTIMATE"


def test_agent_run_stores_assessment_and_detail_returns_it(monkeypatch):
    """The additive `assessment` blob (HOW the numbers were obtained) survives
    the whole path: agent response -> persisted meal -> detail endpoint."""
    _, token = _make_account_token(provider_id="asm@example.com", email="asm@example.com")

    async def fake_workflow(**kwargs):
        return {
            "intent": "photo_meal",
            "message_text": "ok",
            "confidence": "HIGH",
            "totals": {"calories_kcal": 320, "protein_g": 20, "fat_g": 10, "carbs_g": 35},
            "items": [{"name": "Творог с ягодами", "grams": 200, "calories_kcal": 320,
                       "protein_g": 20, "fat_g": 10, "carbs_g": 35, "source_url": None}],
            "source_url": None,
            "assessment": {"method": "label", "domain": None,
                           "portion_estimated": False, "verified_items": 1, "total_items": 1},
        }

    monkeypatch.setattr(app_api_module, "run_yumyummy_workflow", fake_workflow)

    r = client.post("/app/agent/run", headers=_auth(token), json={"text": "(photo)"})
    assert r.status_code == 200, r.text
    # Additive field comes back on the agent response itself...
    assert r.json()["assessment"]["method"] == "label"

    # ...and on the persisted meal via list/detail.
    meals = client.get("/app/meals/recent", headers=_auth(token)).json()
    assert meals[0]["assessment"]["method"] == "label"
    assert meals[0]["assessment"]["verified_items"] == 1
    detail = client.get(f"/app/meals/{meals[0]['id']}", headers=_auth(token)).json()
    assert detail["assessment"]["method"] == "label"

    # Repeat copies provenance verbatim.
    rep = client.post(f"/app/meals/{meals[0]['id']}/repeat", headers=_auth(token)).json()
    assert rep["assessment"]["method"] == "label"

    # Old-shape results (no assessment key) still validate and store None.
    async def old_workflow(**kwargs):
        return {
            "intent": "log_meal", "message_text": "ok", "confidence": "ESTIMATE",
            "totals": {"calories_kcal": 100, "protein_g": 1, "fat_g": 1, "carbs_g": 20},
            "items": [], "source_url": None,
        }
    monkeypatch.setattr(app_api_module, "run_yumyummy_workflow", old_workflow)
    r = client.post("/app/agent/run", headers=_auth(token), json={"text": "яблоко"})
    assert r.status_code == 200, r.text
    assert r.json()["assessment"] is None


def test_photo_run_multi_merges_items_confidence_and_assessment(monkeypatch):
    """Multi-photo: per-photo results merge into one meal — items concat,
    totals sum, confidence is HIGH only when every photo is HIGH, assessment
    aggregates verified/total counters."""
    import asyncio

    from app.agent_v2.config import VARIANTS
    from app.agent_v2.pipelines import photo as photo_pipeline
    from app.agent_v2.schemas import Assessment, Item, Totals, V2Result

    def _sub(name, kcal, confidence, method, verified):
        r = V2Result(intent="photo_meal", variant="v2g")
        r.items = [Item(name=name, grams=100, calories_kcal=kcal)]
        r.totals = Totals(calories_kcal=kcal)
        r.confidence = confidence
        r.assessment = Assessment(
            method=method, portion_estimated=(method != "label"),
            verified_items=verified, total_items=1,
        )
        return r

    subs = [
        _sub("Овсянка", 300, "HIGH", "label", 1),
        _sub("Кофе с молоком", 60, "ESTIMATE", "estimate", 0),
    ]

    async def fake_run(image_bytes, spec, **kwargs):
        return subs.pop(0)

    monkeypatch.setattr(photo_pipeline, "run", fake_run)
    merged = asyncio.run(
        photo_pipeline.run_multi([b"img1", b"img2"], VARIANTS["v2g"])
    )
    assert len(merged.items) == 2
    assert merged.totals.calories_kcal == 360
    assert merged.confidence == "ESTIMATE"  # one photo was an estimate
    assert merged.assessment.method == "photo"
    assert merged.assessment.verified_items == 1
    assert merged.assessment.total_items == 2
    assert merged.assessment.portion_estimated is True

    # All photos labels -> the merged meal keeps the "label" method and HIGH.
    subs.extend([
        _sub("Йогурт", 120, "HIGH", "label", 1),
        _sub("Батончик", 200, "HIGH", "label", 1),
    ])
    merged = asyncio.run(
        photo_pipeline.run_multi([b"img1", b"img2"], VARIANTS["v2g"])
    )
    assert merged.confidence == "HIGH"
    assert merged.assessment.method == "label"


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
