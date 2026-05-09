"""Tests for the Meta Conversions API client (server-side bridge).

Mirror of ``test_tiktok_events_client.py`` adapted for the Meta CAPI
payload shape (graph.facebook.com /events endpoint, ``data: [...]``
envelope, ``user_data`` instead of ``user``, single-string
``external_id`` instead of array, raw ``fbp``/``fbc``).
"""

from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest

from app.core import meta_capi_client


def _sha256(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


@pytest.fixture(autouse=True)
def _reset_module_cache():
    """Clear the posthog_persons cache between tests to avoid leakage."""
    from app.core import posthog_persons
    posthog_persons._cache.clear()
    yield
    posthog_persons._cache.clear()


def test_disabled_when_no_credentials():
    """Without pixel_id/access_token the client must do nothing."""
    with patch.object(meta_capi_client.settings, "meta_pixel_id", None), \
         patch.object(meta_capi_client.settings, "meta_access_token", None), \
         patch("threading.Thread") as mock_thread:
        meta_capi_client.send_complete_registration(
            user_id=1,
            telegram_id="123",
            posthog_distinct_id="ph_abc",
            acquisition_source="meta",
        )
        mock_thread.assert_not_called()


def test_disabled_when_only_pixel_id_set():
    with patch.object(meta_capi_client.settings, "meta_pixel_id", "123456"), \
         patch.object(meta_capi_client.settings, "meta_access_token", None), \
         patch("threading.Thread") as mock_thread:
        meta_capi_client.send_start_trial(
            user_id=1,
            telegram_id="123",
            posthog_distinct_id="ph_abc",
            trial_days=3,
        )
        mock_thread.assert_not_called()


def _capture_dispatched_body():
    """Return a (FakeThread class, container) pair where container[0]
    is the CAPI body the dispatcher would have POSTed to Meta."""
    container: list = []

    class FakeThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None, name=None):
            container.append(args[0])
            self.target = target

        def start(self):
            pass

    return FakeThread, container


def test_complete_registration_payload_shape():
    FakeThread, captured = _capture_dispatched_body()
    with patch.object(meta_capi_client.settings, "meta_pixel_id", "PIX_FB"), \
         patch.object(meta_capi_client.settings, "meta_access_token", "tok-xyz"), \
         patch.object(meta_capi_client.settings, "meta_capi_test_event_code", None), \
         patch(
             "app.core.meta_capi_client.fetch_pixel_ids",
             return_value={
                 "ttp": None,
                 "ttclid": None,
                 "fbp": "fb.1.1700.123",
                 "fbc": "fb.1.1700.click_xyz",
             },
         ), \
         patch("app.core.meta_capi_client.threading.Thread", FakeThread):
        meta_capi_client.send_complete_registration(
            user_id=42,
            telegram_id="999",
            posthog_distinct_id="ph_distinct",
            acquisition_source="meta_ad_v1",
        )

    assert len(captured) == 1
    body = captured[0]
    assert "test_event_code" not in body
    data = body["data"][0]
    assert data["event_name"] == "CompleteRegistration"
    assert data["event_id"] == "yy:registration:42"
    assert data["action_source"] == "website"
    assert data["event_source_url"] == "https://yumyummy.ai/"
    assert data["user_data"]["external_id"] == _sha256("ph_distinct")
    assert data["user_data"]["fbp"] == "fb.1.1700.123"
    assert data["user_data"]["fbc"] == "fb.1.1700.click_xyz"
    assert data["custom_data"]["content_name"] == "meta_ad_v1"
    assert data["custom_data"]["content_category"] == "subscription"


def test_start_trial_payload_shape():
    FakeThread, captured = _capture_dispatched_body()
    with patch.object(meta_capi_client.settings, "meta_pixel_id", "PIX_FB"), \
         patch.object(meta_capi_client.settings, "meta_access_token", "tok-xyz"), \
         patch(
             "app.core.meta_capi_client.fetch_pixel_ids",
             return_value={"ttp": None, "ttclid": None, "fbp": None, "fbc": None},
         ), \
         patch("app.core.meta_capi_client.threading.Thread", FakeThread):
        meta_capi_client.send_start_trial(
            user_id=7,
            telegram_id="555",
            posthog_distinct_id=None,
            trial_days=3,
        )

    body = captured[0]
    data = body["data"][0]
    assert data["event_name"] == "StartTrial"
    assert data["event_id"] == "yy:trial:7"
    # No posthog_distinct_id => external_id falls back to tg_<telegram_id>.
    assert data["user_data"]["external_id"] == _sha256("tg_555")
    # fbp/fbc are absent (not None/empty) so Meta ignores them.
    assert "fbp" not in data["user_data"]
    assert "fbc" not in data["user_data"]
    assert data["custom_data"]["value"] == 0
    assert data["custom_data"]["currency"] == "USD"
    assert data["custom_data"]["content_ids"] == ["trial_3d"]


def test_subscribe_first_vs_renewal_event_ids_differ():
    """Renewals must produce a different event_id than the first
    payment so Meta doesn't dedup them as the same conversion."""
    FakeThread, captured = _capture_dispatched_body()
    with patch.object(meta_capi_client.settings, "meta_pixel_id", "PIX_FB"), \
         patch.object(meta_capi_client.settings, "meta_access_token", "tok-xyz"), \
         patch(
             "app.core.meta_capi_client.fetch_pixel_ids",
             return_value={"ttp": None, "ttclid": None, "fbp": None, "fbc": None},
         ), \
         patch("app.core.meta_capi_client.threading.Thread", FakeThread):
        meta_capi_client.send_subscribe(
            user_id=11,
            telegram_id="111",
            posthog_distinct_id="ph_x",
            plan_id="monthly_v1",
            revenue_usd=9.99,
            currency="USD",
            is_first_payment=True,
        )
        meta_capi_client.send_subscribe(
            user_id=11,
            telegram_id="111",
            posthog_distinct_id="ph_x",
            plan_id="monthly_v1",
            revenue_usd=9.99,
            currency="USD",
            is_first_payment=False,
        )

    assert len(captured) == 2
    first_id = captured[0]["data"][0]["event_id"]
    renew_id = captured[1]["data"][0]["event_id"]
    assert first_id == "yy:subscribe:11:first"
    assert renew_id.startswith("yy:subscribe:11:renew_")
    assert first_id != renew_id

    first_custom = captured[0]["data"][0]["custom_data"]
    assert first_custom["value"] == 9.99
    assert first_custom["currency"] == "USD"
    assert first_custom["content_ids"] == ["monthly_v1"]
    # First-payment events carry predicted_ltv == revenue so Meta's
    # algo can bid for similar-LTV lookalikes.
    assert first_custom["predicted_ltv"] == 9.99


def test_test_event_code_is_forwarded():
    """When META_CAPI_TEST_EVENT_CODE is set, every payload must carry it."""
    FakeThread, captured = _capture_dispatched_body()
    with patch.object(meta_capi_client.settings, "meta_pixel_id", "PIX_FB"), \
         patch.object(meta_capi_client.settings, "meta_access_token", "tok-xyz"), \
         patch.object(meta_capi_client.settings, "meta_capi_test_event_code", "TEST456"), \
         patch(
             "app.core.meta_capi_client.fetch_pixel_ids",
             return_value={"ttp": None, "ttclid": None, "fbp": None, "fbc": None},
         ), \
         patch("app.core.meta_capi_client.threading.Thread", FakeThread):
        meta_capi_client.send_start_trial(
            user_id=1,
            telegram_id="1",
            posthog_distinct_id=None,
            trial_days=3,
        )

    assert captured[0]["test_event_code"] == "TEST456"


def test_external_id_prefers_posthog_distinct_id():
    """If both posthog_distinct_id and telegram_id are present, the
    PostHog id wins (so the conversion stitches to the same person
    profile that captured the LP pageview / Lead click)."""
    FakeThread, captured = _capture_dispatched_body()
    with patch.object(meta_capi_client.settings, "meta_pixel_id", "PIX_FB"), \
         patch.object(meta_capi_client.settings, "meta_access_token", "tok-xyz"), \
         patch(
             "app.core.meta_capi_client.fetch_pixel_ids",
             return_value={"ttp": None, "ttclid": None, "fbp": None, "fbc": None},
         ), \
         patch("app.core.meta_capi_client.threading.Thread", FakeThread):
        meta_capi_client.send_complete_registration(
            user_id=1,
            telegram_id="555",
            posthog_distinct_id="ph_distinct_abc",
            acquisition_source=None,
        )

    body = captured[0]
    assert body["data"][0]["user_data"]["external_id"] == _sha256("ph_distinct_abc")


def test_api_url_uses_configured_version_and_pixel():
    """The endpoint must always be graph.facebook.com/{version}/{pixel}/events."""
    with patch.object(meta_capi_client.settings, "meta_pixel_id", "826914203808503"), \
         patch.object(meta_capi_client.settings, "meta_api_version", "v21.0"):
        url = meta_capi_client._api_url()
        assert url == "https://graph.facebook.com/v21.0/826914203808503/events"
