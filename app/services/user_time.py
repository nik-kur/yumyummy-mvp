from datetime import date, datetime
from typing import Any, Union

import pytz


_DEFAULT_TZ = "Europe/Moscow"


def _extract_tz_name(user) -> str:
    if isinstance(user, dict):
        return (user or {}).get("timezone") or _DEFAULT_TZ
    return getattr(user, "timezone", None) or _DEFAULT_TZ


def user_tz(user) -> Any:
    """Return a pytz timezone for *user* (dict or ORM model)."""
    try:
        return pytz.timezone(_extract_tz_name(user))
    except pytz.exceptions.UnknownTimeZoneError:
        return pytz.timezone(_DEFAULT_TZ)


def today_for_user(user) -> date:
    """Current calendar date in the user's saved timezone."""
    return datetime.now(user_tz(user)).date()


def now_for_user(user) -> datetime:
    """Current wall-clock datetime in the user's saved timezone."""
    return datetime.now(user_tz(user))
