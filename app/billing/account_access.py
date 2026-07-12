"""
Account-level entitlement.

The existing :mod:`app.billing.access` helpers answer "does *this user row*
have access?" from a plain dict. Mobile needs "does *this account* have
access?", which is the union across every ``users`` row linked to the
account (Telegram Stars + Paddle + Gumroad + Apple-IAP-via-Adapty all live on
different members until a link merges them).

We reuse the battle-tested per-user logic by collapsing the account's members
into a single aggregated dict (best subscription end, best trial end, primary
member's usage) and feeding it to the existing functions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.user import User
from app.billing.access import (
    compute_access_status,
    has_access,
    get_usage_cap_usd,
    check_usage_cap,
    effective_period_cost,
    trial_days_remaining,
)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _max_dt(a: Optional[datetime], b: Optional[datetime]) -> Optional[datetime]:
    a_u, b_u = _as_utc(a), _as_utc(b)
    if a_u is None:
        return b
    if b_u is None:
        return a
    return a if a_u >= b_u else b


def _members(db: Session, account_id: int) -> List[User]:
    return (
        db.query(User)
        .filter(User.account_id == account_id)
        .order_by(User.id.asc())
        .all()
    )


def aggregate_account_billing(db: Session, account: Account) -> Dict[str, Any]:
    """Collapse all member users into one billing dict for the access helpers."""
    members = _members(db, account.id)

    agg: Dict[str, Any] = {
        "trial_started_at": None,
        "trial_ends_at": None,
        "subscription_started_at": None,
        "subscription_ends_at": None,
        "subscription_plan_id": None,
        "subscription_provider": None,
        "subscription_auto_renew": None,
        "usage_cost_current_period": 0.0,
        "usage_period_start": None,
    }
    if not members:
        return agg

    # Primary member owns the usage meter for cap checks.
    agg["usage_cost_current_period"] = float(members[0].usage_cost_current_period or 0.0)
    agg["usage_period_start"] = members[0].usage_period_start

    best_sub_member = None
    for m in members:
        agg["trial_ends_at"] = _max_dt(agg["trial_ends_at"], m.trial_ends_at)
        if agg["trial_ends_at"] is m.trial_ends_at:
            agg["trial_started_at"] = m.trial_started_at

        prev = agg["subscription_ends_at"]
        agg["subscription_ends_at"] = _max_dt(prev, m.subscription_ends_at)
        if agg["subscription_ends_at"] is m.subscription_ends_at and m.subscription_ends_at is not None:
            best_sub_member = m

    if best_sub_member is not None:
        agg["subscription_started_at"] = best_sub_member.subscription_started_at
        agg["subscription_plan_id"] = best_sub_member.subscription_plan_id
        agg["subscription_provider"] = best_sub_member.subscription_provider
        agg["subscription_auto_renew"] = best_sub_member.subscription_auto_renew

    return agg


def compute_account_access_status(db: Session, account: Account) -> str:
    return compute_access_status(aggregate_account_billing(db, account))


def account_has_access(db: Session, account: Account) -> bool:
    return has_access(aggregate_account_billing(db, account))


def account_billing_snapshot(db: Session, account: Account) -> Dict[str, Any]:
    agg = aggregate_account_billing(db, account)
    status = compute_access_status(agg)
    cap = get_usage_cap_usd(agg)
    return {
        "access_status": status,
        "trial_started_at": agg["trial_started_at"],
        "trial_ends_at": agg["trial_ends_at"],
        "trial_days_remaining": round(trial_days_remaining(agg), 2) if status == "trial" else None,
        "subscription_plan_id": agg["subscription_plan_id"],
        "subscription_ends_at": agg["subscription_ends_at"],
        "subscription_auto_renew": agg["subscription_auto_renew"],
        "subscription_provider": agg["subscription_provider"],
        "usage_cost_current_period": round(effective_period_cost(agg), 6),
        "usage_cap_usd": cap,
        "usage_exceeded": (not check_usage_cap(agg)) if cap is not None else False,
    }
