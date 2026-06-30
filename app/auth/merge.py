"""
Merging accounts and their diary containers.

When a person links their Telegram history to the account they're signed into
on the phone, two previously-separate accounts (and their ``users`` rows) must
become one so the diary, saved meals and subscription are unified everywhere.

``merge_users`` is the heavy lifter: it re-points every child row (meals,
days, saved meals, payments, usage, churn surveys) from the source user onto
the target user, merges same-date day aggregates, folds the better
entitlement/profile into the target, then deletes the now-empty source user.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.account import Account, Identity
from app.models.user import User
from app.models.user_day import UserDay
from app.models.meal_entry import MealEntry
from app.models.saved_meal import SavedMeal
from app.models.payment_event import PaymentEvent
from app.models.usage_record import UsageRecord
from app.models.churn_survey import ChurnSurvey


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _later(a: Optional[datetime], b: Optional[datetime]) -> bool:
    """True if a is strictly later than b (None treated as -infinity)."""
    a_u, b_u = _as_utc(a), _as_utc(b)
    if a_u is None:
        return False
    if b_u is None:
        return True
    return a_u > b_u


def _combine_entitlement(target: User, source: User) -> None:
    # Prefer the subscription that lasts longer.
    if _later(source.subscription_ends_at, target.subscription_ends_at):
        target.subscription_plan_id = source.subscription_plan_id
        target.subscription_started_at = source.subscription_started_at
        target.subscription_ends_at = source.subscription_ends_at
        target.subscription_auto_renew = source.subscription_auto_renew
        target.subscription_provider = source.subscription_provider
        target.subscription_telegram_charge_id = source.subscription_telegram_charge_id
        target.subscription_gumroad_id = source.subscription_gumroad_id
        target.subscription_paddle_id = source.subscription_paddle_id

    # Keep the trial that ends later.
    if _later(source.trial_ends_at, target.trial_ends_at):
        target.trial_started_at = source.trial_started_at
        target.trial_ends_at = source.trial_ends_at


def _fill_missing_profile(target: User, source: User) -> None:
    profile_fields = (
        "goal_type", "gender", "age", "height_cm", "weight_kg", "activity_level",
        "target_calories", "target_protein_g", "target_fat_g", "target_carbs_g",
        "timezone", "acquisition_source", "posthog_distinct_id",
    )
    for field in profile_fields:
        if getattr(target, field, None) in (None, "") and getattr(source, field, None) not in (None, ""):
            setattr(target, field, getattr(source, field))

    if not target.onboarding_completed and source.onboarding_completed:
        target.onboarding_completed = True


def merge_users(db: Session, source: User, target: User) -> None:
    """Fold ``source`` user entirely into ``target`` user, then delete source."""
    if source.id == target.id:
        return

    # 1) Day aggregates: merge same-date days, re-point the rest.
    source_days = db.query(UserDay).filter(UserDay.user_id == source.id).all()
    for sd in source_days:
        td = (
            db.query(UserDay)
            .filter(UserDay.user_id == target.id, UserDay.date == sd.date)
            .first()
        )
        if td is not None:
            db.query(MealEntry).filter(MealEntry.user_day_id == sd.id).update(
                {MealEntry.user_day_id: td.id, MealEntry.user_id: target.id},
                synchronize_session=False,
            )
            td.total_calories = (td.total_calories or 0) + (sd.total_calories or 0)
            td.total_protein_g = (td.total_protein_g or 0) + (sd.total_protein_g or 0)
            td.total_fat_g = (td.total_fat_g or 0) + (sd.total_fat_g or 0)
            td.total_carbs_g = (td.total_carbs_g or 0) + (sd.total_carbs_g or 0)
            db.delete(sd)
        else:
            sd.user_id = target.id

    # 2) Re-point any remaining child rows that key on user_id.
    for model in (MealEntry, SavedMeal, PaymentEvent, UsageRecord, ChurnSurvey):
        db.query(model).filter(model.user_id == source.id).update(
            {model.user_id: target.id}, synchronize_session=False
        )

    # 3) Fold entitlement + profile into the survivor.
    _combine_entitlement(target, source)
    _fill_missing_profile(target, source)

    # If the target has no Telegram id yet, it should inherit the source's so
    # the bot keeps resolving this person to the (now unified) diary. We do
    # this *after* deleting the source to avoid a transient UNIQUE collision on
    # users.telegram_id (both rows briefly holding the same id).
    inherit_telegram_id = source.telegram_id if (not target.telegram_id and source.telegram_id) else None
    source_id = source.id

    # 4) Persist the re-points *before* the source row goes away.
    #
    # Why the explicit flush + Core DELETE instead of ``db.delete(source)``:
    # ``User.days`` / ``User.meals`` / ``User.saved_meals`` ... are plain
    # one-to-many relationships with SQLAlchemy's default cascade (no
    # delete-orphan, no passive_deletes). If the source DELETE shared a single
    # flush with the "sd.user_id = target.id" re-points above, the unit of work
    # would treat those (in-memory) children as still belonging to the
    # soon-to-be-deleted source and reset ``user_days.user_id`` to NULL to
    # disassociate them — violating its NOT NULL constraint. That is the
    # IntegrityError we hit in production on /auth/link/telegram/redeem.
    # Flushing here commits the re-points as plain UPDATEs while the source
    # still exists; the subsequent Core DELETE then removes an already-childless
    # row without ever running the ORM relationship cascade.
    db.flush()
    db.query(User).filter(User.id == source_id).delete(synchronize_session=False)
    db.flush()

    if inherit_telegram_id is not None:
        target.telegram_id = inherit_telegram_id
        db.flush()


def merge_account_into(db: Session, *, source_account: Account, target_account: Account) -> None:
    """Move ``source_account``'s identities + users onto ``target_account``."""
    if source_account.id == target_account.id:
        return

    target_primary = (
        db.query(User)
        .filter(User.account_id == target_account.id)
        .order_by(User.id.asc())
        .first()
    )
    if target_primary is None:
        target_primary = User(account_id=target_account.id)
        db.add(target_primary)
        db.flush()

    # Merge every source member user into the target's primary container.
    source_users = (
        db.query(User)
        .filter(User.account_id == source_account.id)
        .order_by(User.id.asc())
        .all()
    )
    for su in source_users:
        merge_users(db, su, target_primary)

    # Move identities (skip any provider already present on the target).
    # IMPORTANT: reassign via the relationship (``ident.account = ...``), not the
    # raw FK column. ``Account.identities`` is delete-orphan, so if the source
    # account's cached collection still referenced the identity, deleting the
    # source account would orphan-delete it. Assigning the relationship updates
    # both back-populated collections and avoids that.
    target_providers = {
        i.provider for i in db.query(Identity).filter(Identity.account_id == target_account.id).all()
    }
    for ident in db.query(Identity).filter(Identity.account_id == source_account.id).all():
        if ident.provider in target_providers and ident.provider != "telegram":
            # Keep the target's own primary identity for that provider; drop dup.
            db.delete(ident)
        else:
            ident.account = target_account

    db.flush()
    db.delete(source_account)
    db.flush()


def link_telegram_account(db: Session, *, source_account: Account, target_account: Account) -> str:
    """Public entry point used by the link-redeem endpoint.

    Returns 'already_linked' if they're the same account, else 'linked'.
    """
    if source_account.id == target_account.id:
        return "already_linked"
    merge_account_into(db, source_account=source_account, target_account=target_account)
    db.commit()
    return "linked"
