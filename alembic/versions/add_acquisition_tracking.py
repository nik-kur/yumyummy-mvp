"""Add acquisition tracking: users.acquisition_source + acquisition_events table

Revision ID: add_acquisition_tracking
Revises: add_launch_indexes
Create Date: 2026-05-08

Captures Telegram deep-link source parameters from
``t.me/<bot>?start=<source>``:

- ``users.acquisition_source`` — first-touch attribution (one column on the
  user row, easy to JOIN/filter in any downstream query).
- ``acquisition_events`` — append-only log of every deep-link click, so we
  can do multi-touch attribution and per-campaign cohort analysis.

Idempotent: uses IF NOT EXISTS for the column add and create_table_if_not_exists
semantics for the table.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "add_acquisition_tracking"
down_revision: Union[str, None] = "add_launch_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS acquisition_source VARCHAR"
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "acquisition_events" not in inspector.get_table_names():
        op.create_table(
            "acquisition_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("telegram_id", sa.String(), nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_acquisition_events_telegram_id",
            "acquisition_events",
            ["telegram_id"],
        )
        op.create_index(
            "ix_acquisition_events_source",
            "acquisition_events",
            ["source"],
        )
        op.create_index(
            "ix_acquisition_events_source_created_at",
            "acquisition_events",
            ["source", "created_at"],
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_acquisition_events_source_created_at")
    op.execute("DROP INDEX IF EXISTS ix_acquisition_events_source")
    op.execute("DROP INDEX IF EXISTS ix_acquisition_events_telegram_id")
    op.execute("DROP TABLE IF EXISTS acquisition_events")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS acquisition_source")
