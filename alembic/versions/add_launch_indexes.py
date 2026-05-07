"""Add launch indexes for hot query paths and pg_stat_statements

Revision ID: add_launch_indexes
Revises: add_lifecycle_fields
Create Date: 2026-05-07

Indexes added:
- user_days(user_id, date) composite — used by every meal log + day summary
  (existing ix_user_days_date covers only date, ix_user_days_id is redundant with PK)
- meal_entries(user_day_id) — used by /day/{user_id}/{day} and meal lookups
- meal_entries(user_id, eaten_at DESC) — used by get_latest_meal_id_for_today and export

Plus pg_stat_statements extension for slow-query diagnostics.

Uses IF NOT EXISTS so the migration is idempotent (safe to re-run).
"""
from typing import Sequence, Union

from alembic import op


revision: str = "add_launch_indexes"
down_revision: Union[str, None] = "add_lifecycle_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_days_user_id_date "
        "ON user_days (user_id, date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_meal_entries_user_day_id "
        "ON meal_entries (user_day_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_meal_entries_user_id_eaten_at "
        "ON meal_entries (user_id, eaten_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_meal_entries_user_id_eaten_at")
    op.execute("DROP INDEX IF EXISTS ix_meal_entries_user_day_id")
    op.execute("DROP INDEX IF EXISTS ix_user_days_user_id_date")
