"""Tests for the TikTok Events API client (server-side bridge).

These tests verify the *contract* of the client without hitting the
real TikTok API:

  - When the client isn't configured (no pixel_code / no token), all
    public helpers are silent no-ops and never spawn a thread.
  - When configured, each helper builds an EAPI payload with the
    expected event name, event_id, hashed external_id, and ttp/ttclid
    pulled from the PostHog person profile.
  - The HTTP call runs in a daemon thread so the caller is never
    blocked by a slow TikTok response.
"""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from app.core import tiktok_events_client


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
    """Without pixel_code/access_token the client must do nothing."""
    with patch.object(tiktok_events_client.settings, "tiktok_pixel_code", None), \
         patch.object(tiktok_events_client.settings, "tiktok_access_token", None), \
         patch("threading.Thread") as mock_thread:
        tiktok_events_client.send_complete_registration(
            user_id=1,
            telegram_id="123",
            posthog_distinct_id="ph_abc",
            acquisition_source="tiktok",
        )
        mock_thread.assert_not_called()


def test_disabled_when_only_pixel_code_set():
    with patch.object(tiktok_events_client.settings, "tiktok_pixel_code", "PX123"), \
         patch.object(tiktok_events_client.settings, "tiktok_access_token", None), \
         patch("threading.Thread") as mock_thread:
        tiktok_events_client.send_start_trial(
            user_id=1,
            telegram_id="123",
            posthog_distinct_id="ph_abc",
            trial_days=3,
        )
        mock_thread.assert_not_called()


def _capture_dispatched_body():
    """Return a (Thread mock, container) pair where container[0] is
    the EAPI body the dispatcher *would* have POSTed to TikTok."""
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
    with patch.object(tiktok_events_client.settings, "tiktok_pixel_code", "PXTEST"), \
         patch.object(tiktok_events_client.settings, "tiktok_access_token", "tok-123"), \
         patch.object(tiktok_events_client.settings, "tiktok_test_event_code", None), \
         patch(
             "app.core.tiktok_events_client.fetch_pixel_ids",
             return_value={
                 "ttp": "ttp-abc",
                 "ttclid": "ttclid-xyz",
                 "fbp": None,
                 "fbc": None,
             },
         ), \
         patch("app.core.tiktok_events_client.threading.Thread", FakeThread):
        tiktok_events_client.send_complete_registration(
            user_id=42,
            telegram_id="999",
            posthog_distinct_id="ph_distinct",
            acquisition_source="tiktok_ad_v1",
        )

    assert len(captured) == 1
    body = captured[0]
    assert body["event_source"] == "web"
    assert body["event_source_id"] == "PXTEST"
    assert "test_event_code" not in body
    data = body["data"][0]
    assert data["event"] == "CompleteRegistration"
    assert data["event_id"] == "yy:registration:42"
    assert data["user"]["external_id"] == [_sha256("ph_distinct")]
    assert data["user"]["ttp"] == "ttp-abc"
    assert data["user"]["ttclid"] == "ttclid-xyz"
    assert data["properties"]["description"] == "tiktok_ad_v1"


def test_start_trial_payload_shape():
    FakeThread, captured = _capture_dispatched_body()
    with patch.object(tiktok_events_client.settings, "tiktok_pixel_code", "PXTEST"), \
         patch.object(tiktok_events_client.settings, "tiktok_access_token", "tok-123"), \
         patch(
             "app.core.tiktok_events_client.fetch_pixel_ids",
             return_value={"ttp": None, "ttclid": None, "fbp": None, "fbc": None},
         ), \
         patch("app.core.tiktok_events_client.threading.Thread", FakeThread):
        tiktok_events_client.send_start_trial(
            user_id=7,
            telegram_id="555",
            posthog_distinct_id=None,
            trial_days=3,
        )

    body = captured[0]
    data = body["data"][0]
    assert data["event"] == "StartTrial"
    assert data["event_id"] == "yy:trial:7"
    # No posthog_distinct_id => external_id falls back to tg_<telegram_id>.
    assert data["user"]["external_id"] == [_sha256("tg_555")]
    # ttp/ttclid are absent (not None) so TikTok ignores them.
    assert "ttp" not in data["user"]
    assert "ttclid" not in data["user"]
    assert data["properties"]["value"] == 0
    assert data["properties"]["currency"] == "USD"
    assert data["properties"]["content_id"] == "trial_3d"


def test_complete_payment_first_vs_renewal_event_ids_differ():
    """Renewals must produce a different event_id than the first
    payment so TikTok doesn't dedup them as the same conversion."""
    FakeThread, captured = _capture_dispatched_body()
    with patch.object(tiktok_events_client.settings, "tiktok_pixel_code", "PXTEST"), \
         patch.object(tiktok_events_client.settings, "tiktok_access_token", "tok-123"), \
         patch(
             "app.core.tiktok_events_client.fetch_pixel_ids",
             return_value={"ttp": None, "ttclid": None, "fbp": None, "fbc": None},
         ), \
         patch("app.core.tiktok_events_client.threading.Thread", FakeThread):
        tiktok_events_client.send_complete_payment(
            user_id=11,
            telegram_id="111",
            posthog_distinct_id="ph_x",
            plan_id="monthly_v1",
            revenue_usd=9.99,
            currency="USD",
            is_first_payment=True,
        )
        tiktok_events_client.send_complete_payment(
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
    assert first_id == "yy:payment:11:first"
    assert renew_id.startswith("yy:payment:11:renew_")
    assert first_id != renew_id

    first_props = captured[0]["data"][0]["properties"]
    assert first_props["value"] == 9.99
    assert first_props["currency"] == "USD"
    assert first_props["content_id"] == "monthly_v1"
    assert first_props["description"] == "first_subscription"
    assert captured[1]["data"][0]["properties"]["description"] == "renewal"


def test_test_event_code_is_forwarded():
    """When TIKTOK_TEST_EVENT_CODE is set, every payload must carry it."""
    FakeThread, captured = _capture_dispatched_body()
    with patch.object(tiktok_events_client.settings, "tiktok_pixel_code", "PXTEST"), \
         patch.object(tiktok_events_client.settings, "tiktok_access_token", "tok-123"), \
         patch.object(tiktok_events_client.settings, "tiktok_test_event_code", "TEST123"), \
         patch(
             "app.core.tiktok_events_client.fetch_pixel_ids",
             return_value={"ttp": None, "ttclid": None, "fbp": None, "fbc": None},
         ), \
         patch("app.core.tiktok_events_client.threading.Thread", FakeThread):
        tiktok_events_client.send_start_trial(
            user_id=1,
            telegram_id="1",
            posthog_distinct_id=None,
            trial_days=3,
        )

    assert captured[0]["test_event_code"] == "TEST123"


def test_external_id_prefers_posthog_distinct_id():
    """If both posthog_distinct_id and telegram_id are present, the
    PostHog id wins (so the conversion stitches to the same person
    profile that captured the LP pageview / Lead click)."""
    FakeThread, captured = _capture_dispatched_body()
    with patch.object(tiktok_events_client.settings, "tiktok_pixel_code", "PXTEST"), \
         patch.object(tiktok_events_client.settings, "tiktok_access_token", "tok-123"), \
         patch(
             "app.core.tiktok_events_client.fetch_pixel_ids",
             return_value={"ttp": None, "ttclid": None, "fbp": None, "fbc": None},
         ), \
         patch("app.core.tiktok_events_client.threading.Thread", FakeThread):
        tiktok_events_client.send_complete_registration(
            user_id=1,
            telegram_id="555",
            posthog_distinct_id="ph_distinct_abc",
            acquisition_source=None,
        )

    body = captured[0]
    assert body["data"][0]["user"]["external_id"] == [_sha256("ph_distinct_abc")]
