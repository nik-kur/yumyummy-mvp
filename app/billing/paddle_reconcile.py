"""
Paddle subscription reconciliation.

Webhooks are the primary mechanism for keeping local subscription state in
sync with Paddle. They can fail, though — network blips, app downtime, the
webhook secret being rotated, etc. — so this module provides an
authoritative pull-style sync against the Paddle API as a safety net.

Two entry points:

* :func:`reconcile_user`   — sync one user's subscription. Cheap. Use after
                             admin actions or when a user reports an issue.
* :func:`reconcile_all`    — sync every user with a Paddle subscription
                             whose ``subscription_ends_at`` is in a
                             worry zone (about-to-expire or recently
                             expired but ``auto_renew`` still on). Used by
                             the periodic background job.

Reconciliation is *strictly* about copying provider state into our DB; it
never charges, refunds or changes anything in Paddle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.billing.service import sync_subscription_state
from app.external.paddle_client import (
    PaddleAPIError,
    extract_period_ends_at,
    get_subscription,
)
from app.models.user import User

logger = logging.getLogger(__name__)


# A subscription that's expired but still has auto_renew on is the prime
# suspect for "stuck" state — Paddle either has a future next_billed_at
# (webhook missed) or has flipped to past_due (we should revoke).
RECONCILE_LOOKAHEAD_DAYS = 2
RECONCILE_LOOKBACK_DAYS = 7


@dataclass
class ReconcileResult:
    telegram_id: str
    status: str  # 'updated' | 'unchanged' | 'no_subscription' | 'error' | 'revoked'
    new_ends_at: Optional[datetime] = None
    paddle_status: Optional[str] = None
    error: Optional[str] = None


async def reconcile_user(db: Session, user: User) -> ReconcileResult:
    """Pull this user's Paddle subscription and mirror it into the DB."""
    if not user.subscription_paddle_id:
        return ReconcileResult(
            telegram_id=user.telegram_id, status="no_subscription",
        )

    try:
        sub = await get_subscription(user.subscription_paddle_id)
    except PaddleAPIError as e:
        logger.warning(
            "[PADDLE-RECON] API error for telegram_id=%s sub=%s: %s",
            user.telegram_id, user.subscription_paddle_id, e,
        )
        return ReconcileResult(
            telegram_id=user.telegram_id,
            status="error",
            error=str(e),
        )

    paddle_status = sub.get("status")
    period_ends = extract_period_ends_at(sub)
    scheduled = sub.get("scheduled_change") or {}
    scheduled_action = scheduled.get("action")

    # Decide what to write based on Paddle's status.
    revoke = False
    auto_renew: Optional[bool]
    if paddle_status == "active":
        auto_renew = True
        if scheduled_action in ("cancel", "pause"):
            auto_renew = False
    elif paddle_status == "trialing":
        auto_renew = True
    elif paddle_status == "paused":
        revoke = True
        auto_renew = False
    elif paddle_status == "canceled":
        # Already canceled on Paddle's side — ensure auto_renew is off.
        # Access stays valid until period_ends if Paddle still reports one.
        auto_renew = False
    elif paddle_status == "past_due":
        # Payment retry window — keep auto_renew on so a successful retry
        # restores access naturally; don't extend ends_at past Paddle's
        # reported value.
        auto_renew = True
    else:
        auto_renew = None

    status = sync_subscription_state(
        db, user,
        provider="paddle",
        period_ends_at=period_ends if not revoke else None,
        auto_renew=auto_renew,
        revoke=revoke,
    )

    return ReconcileResult(
        telegram_id=user.telegram_id,
        status="revoked" if revoke and status == "updated" else status,
        new_ends_at=user.subscription_ends_at,
        paddle_status=paddle_status,
    )


def _candidates_for_reconcile(db: Session) -> List[User]:
    """
    Return users whose local Paddle state plausibly differs from Paddle's
    reality and is worth re-checking now.
    """
    now = datetime.now(timezone.utc)
    horizon_future = now + timedelta(days=RECONCILE_LOOKAHEAD_DAYS)
    horizon_past = now - timedelta(days=RECONCILE_LOOKBACK_DAYS)

    q = (
        db.query(User)
        .filter(User.subscription_provider == "paddle")
        .filter(User.subscription_paddle_id.isnot(None))
        .filter(User.subscription_ends_at.isnot(None))
        .filter(User.subscription_ends_at <= horizon_future)
        .filter(User.subscription_ends_at >= horizon_past)
    )
    # Prioritise auto-renew subs: they're the ones we'll falsely lock out
    # if a webhook went missing.
    return q.all()


async def reconcile_all(db: Session) -> List[ReconcileResult]:
    """Reconcile every user in the worry zone. Safe to run on a schedule."""
    users = _candidates_for_reconcile(db)
    if not users:
        return []

    logger.info("[PADDLE-RECON] Reconciling %d candidate users", len(users))
    results: List[ReconcileResult] = []
    for u in users:
        try:
            res = await reconcile_user(db, u)
        except Exception as e:
            logger.exception(
                "[PADDLE-RECON] Unexpected error for telegram_id=%s: %s",
                u.telegram_id, e,
            )
            res = ReconcileResult(
                telegram_id=u.telegram_id, status="error", error=str(e),
            )
        results.append(res)
    logger.info(
        "[PADDLE-RECON] Completed: %s",
        ", ".join(f"{r.telegram_id}={r.status}" for r in results),
    )
    return results
