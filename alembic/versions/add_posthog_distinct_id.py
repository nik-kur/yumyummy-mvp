"""Add posthog_distinct_id to users

Revision ID: add_posthog_distinct_id
Revises: add_acquisition_tracking
Create Date: 2026-05-08

Stores the PostHog ``distinct_id`` for the same person as recorded on
the marketing site (yumyummy.ai). Captured from the Telegram deep-link
``?start=<distinct_id>`` parameter and used by the backend so every
backend-side PostHog event (``trial_started``, ``subscription_purchased``,
etc.) can be attributed to the same web visitor — closing the funnel
from traffic source → bot signup → paid subscription inside PostHog.

Idempotent: uses IF NOT EXISTS for the column add.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "add_posthog_distinct_id"
down_revision: Union[str, None] = "add_acquisition_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS posthog_distinct_id VARCHAR"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_users_posthog_distinct_id "
        "ON users (posthog_distinct_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_posthog_distinct_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS posthog_distinct_id")
