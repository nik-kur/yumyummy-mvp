"""
Preview mode (V3 screen 21): anonymous account per install, one free AI meal
log per install (kept across reinstalls and the merge), merge on sign-in.

Reuses the app/DB harness of ``test_app_api`` (temp SQLite shared with the
agent-run persist session).
"""

from app.core.config import settings
from app.models.account import Account
from app.models.install import Install
from app.models.meal_entry import MealEntry
from app.auth.service import account_member_users

from tests.test_app_api import (  # noqa: F401 — autouse fixture + shared client
    TestingSessionLocal,
    _auth,
    app_api_module,
    auth_providers,
    client,
    setup_db,
)



def _meal_workflow(intent="log_meal"):
    async def fake_workflow(**kwargs):
        return {
            "intent": intent,
            "message_text": "Logged salad",
            "confidence": "HIGH",
            "totals": {"calories_kcal": 174, "protein_g": 7, "fat_g": 14, "carbs_g": 7},
            "items": [{"name": "salad", "grams": 150, "calories_kcal": 174, "protein_g": 7, "fat_g": 14, "carbs_g": 7}],
            "source_url": None,
        }

    return fake_workflow


def _start(install_id=None):
    r = client.post("/auth/install", json={"install_id": install_id} if install_id else {})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["install_id"] and len(body["install_id"]) >= 16
    return body


def test_install_gives_anonymous_preview_account_and_reuses_it():
    first = _start()
    assert first["created"] is True
    again = _start(first["install_id"])
    assert again["install_id"] == first["install_id"]
    assert again["created"] is False
    assert again["account_id"] == first["account_id"]

    me = client.get("/app/me", headers=_auth(first["access_token"])).json()
    assert me["is_preview"] is True
    assert me["preview_free_log_available"] is True
    assert me["linked_providers"] == []


def test_real_account_is_not_preview(monkeypatch):
    monkeypatch.setattr(
        auth_providers,
        "verify_apple_identity_token",
        lambda tok: auth_providers.ProviderIdentity("apple", "apple-real", "real@example.com"),
    )
    token = client.post("/auth/apple", json={"identity_token": "x"}).json()["access_token"]
    me = client.get("/app/me", headers=_auth(token)).json()
    assert me["is_preview"] is False


def test_one_free_meal_log_then_paywall(monkeypatch):
    token = _start()["access_token"]
    monkeypatch.setattr(app_api_module, "run_yumyummy_workflow", _meal_workflow())

    r1 = client.post("/app/agent/run", headers=_auth(token), json={"text": "salad"})
    assert r1.json()["intent"] == "log_meal"
    me = client.get("/app/me", headers=_auth(token)).json()
    assert me["preview_free_log_available"] is False

    r2 = client.post("/app/agent/run", headers=_auth(token), json={"text": "another salad"})
    assert r2.json()["intent"] == "paywall"

    db = TestingSessionLocal()
    try:
        meals = db.query(MealEntry).all()
        assert len(meals) == 1
    finally:
        db.close()


def test_non_meal_answer_does_not_spend_the_free_log(monkeypatch):
    token = _start()["access_token"]
    monkeypatch.setattr(app_api_module, "run_yumyummy_workflow", _meal_workflow(intent="help"))
    client.post("/app/agent/run", headers=_auth(token), json={"text": "hi"})
    me = client.get("/app/me", headers=_auth(token)).json()
    assert me["preview_free_log_available"] is True


def test_advisor_and_other_forced_intents_are_not_free_in_preview(monkeypatch):
    token = _start()["access_token"]
    monkeypatch.setattr(app_api_module, "run_yumyummy_workflow", _meal_workflow())
    for forced in ("advice", "food_advice", "Advice", "help"):
        r = client.post("/app/agent/run", headers=_auth(token), json={"text": "what next?", "force_intent": forced})
        assert r.json()["intent"] == "paywall", forced


def test_free_log_cannot_be_claimed_twice():
    from app.auth import preview as preview_module

    account_id = _start()["account_id"]
    db = TestingSessionLocal()
    try:
        account = db.get(Account, account_id)
        assert preview_module.claim_free_log(db, account) is True
        # A second request in flight before the first finished.
        assert preview_module.claim_free_log(db, account) is False
    finally:
        db.close()


def test_non_meal_answers_count_towards_the_ai_call_cap(monkeypatch):
    monkeypatch.setattr(settings, "preview_ai_calls_per_install", 3, raising=False)
    token = _start()["access_token"]
    monkeypatch.setattr(app_api_module, "run_yumyummy_workflow", _meal_workflow(intent="help"))
    for _ in range(3):
        assert client.post("/app/agent/run", headers=_auth(token), json={"text": "hi"}).json()["intent"] == "help"
    r = client.post("/app/agent/run", headers=_auth(token), json={"text": "hi again"})
    assert r.json()["intent"] == "paywall"
    me = client.get("/app/me", headers=_auth(token)).json()
    assert me["preview_free_log_available"] is False


def test_merge_survives_a_cached_weekly_recap(monkeypatch):
    from datetime import date

    from app.models.weekly_recap import WeeklyRecap

    preview_session = _start()
    db = TestingSessionLocal()
    try:
        user = account_member_users(db, preview_session["account_id"])[0]
        db.add(WeeklyRecap(user_id=user.id, week_start=date(2026, 10, 12), llm_summary="x"))
        db.commit()
    finally:
        db.close()
    monkeypatch.setattr(
        auth_providers,
        "verify_apple_identity_token",
        lambda tok: auth_providers.ProviderIdentity("apple", "apple-recap", "recap@example.com"),
    )
    r = client.post("/auth/apple", headers=_auth(preview_session["access_token"]), json={"identity_token": "x"})
    assert r.status_code == 200
    db = TestingSessionLocal()
    try:
        assert db.get(Account, preview_session["account_id"]) is None
    finally:
        db.close()


def test_preview_cannot_sync_billing_or_save_meals():
    token = _start()["access_token"]
    assert client.post("/app/billing/sync", headers=_auth(token), json={"adapty_profile_id": "x"}).status_code == 402
    r = client.post("/app/saved-meals", headers=_auth(token), json={"name": "x", "items": []})
    assert r.status_code == 402


def test_preview_cannot_use_paid_or_manual_endpoints(monkeypatch):
    token = _start()["access_token"]
    assert client.post("/app/billing/trial/start", headers=_auth(token), json={}).status_code == 402
    r = client.post(
        "/app/meals",
        headers=_auth(token),
        json={"description_user": "x", "calories": 1, "protein_g": 0, "fat_g": 0, "carbs_g": 0},
    )
    assert r.status_code == 402


def test_unknown_install_id_gets_a_fresh_server_issued_one():
    r = _start("made-up-by-the-client-0000")
    assert r["install_id"] != "made-up-by-the-client-0000"


def test_reinstall_keeps_the_free_log_spent(monkeypatch):
    first = _start()
    token = first["access_token"]
    monkeypatch.setattr(app_api_module, "run_yumyummy_workflow", _meal_workflow())
    client.post("/app/agent/run", headers=_auth(token), json={"text": "salad"})

    # Reinstall: same Keychain install id → same account, still spent.
    again = _start(first["install_id"])
    me = client.get("/app/me", headers=_auth(again["access_token"])).json()
    assert me["preview_free_log_available"] is False


def test_sign_in_merges_preview_account(monkeypatch):
    preview = _start()
    token = preview["access_token"]
    client.patch("/app/me", headers=_auth(token), json={"goal_type": "lose", "target_calories": 1450})
    monkeypatch.setattr(app_api_module, "run_yumyummy_workflow", _meal_workflow())
    client.post("/app/agent/run", headers=_auth(token), json={"text": "salad"})

    monkeypatch.setattr(
        auth_providers,
        "verify_apple_identity_token",
        lambda tok: auth_providers.ProviderIdentity("apple", "apple-buyer", "buyer@example.com"),
    )
    r = client.post("/auth/apple", headers=_auth(token), json={"identity_token": "x"})
    assert r.status_code == 200, r.text
    real = r.json()
    assert real["created"] is True
    assert real["account_id"] != preview["account_id"]

    me = client.get("/app/me", headers=_auth(real["access_token"])).json()
    assert me["is_preview"] is False
    assert me["goal_type"] == "lose"
    assert me["target_calories"] == 1450

    db = TestingSessionLocal()
    try:
        assert db.get(Account, preview["account_id"]) is None
        members = account_member_users(db, real["account_id"])
        assert db.query(MealEntry).filter(MealEntry.user_id.in_([u.id for u in members])).count() == 1
        install = db.query(Install).filter(Install.install_id == preview["install_id"]).one()
        assert install.account_id == real["account_id"]
        assert install.free_log_used_at is not None
    finally:
        db.close()

    # Signed out later, same install: a fresh preview account, no second free log.
    later = _start(preview["install_id"])
    assert later["account_id"] not in (preview["account_id"], real["account_id"])
    me = client.get("/app/me", headers=_auth(later["access_token"])).json()
    assert me["is_preview"] is True
    assert me["preview_free_log_available"] is False


def test_real_account_token_on_sign_in_is_never_merged(monkeypatch):
    monkeypatch.setattr(
        auth_providers,
        "verify_apple_identity_token",
        lambda tok: auth_providers.ProviderIdentity("apple", "apple-a", "a@example.com"),
    )
    a = client.post("/auth/apple", json={"identity_token": "x"}).json()
    monkeypatch.setattr(
        auth_providers,
        "verify_apple_identity_token",
        lambda tok: auth_providers.ProviderIdentity("apple", "apple-b", "b@example.com"),
    )
    b = client.post("/auth/apple", headers=_auth(a["access_token"]), json={"identity_token": "x"}).json()
    db = TestingSessionLocal()
    try:
        assert db.get(Account, a["account_id"]) is not None
        assert db.get(Account, b["account_id"]) is not None
    finally:
        db.close()


def test_per_ip_install_cap(monkeypatch):
    monkeypatch.setattr(settings, "preview_installs_per_ip_day", 2, raising=False)
    a = _start()
    _start()
    r = client.post("/auth/install", json={})
    assert r.status_code == 503
    # A known install still gets back in.
    assert client.post("/auth/install", json={"install_id": a["install_id"]}).status_code == 200


def test_preview_off(monkeypatch):
    monkeypatch.setattr(settings, "preview_mode_enabled", False, raising=False)
    assert client.post("/auth/install", json={}).status_code == 503
