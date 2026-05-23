"""Add landing_attribution table

Revision ID: add_landing_attribution
Revises: add_posthog_distinct_id
Create Date: 2026-05-23

Captures Meta / TikTok match keys (fbp, fbc, ttp, ttclid), client IP,
User-Agent, and landing URL when a visitor first hits yumyummy.ai. Keyed
by PostHog ``phid`` so the row can be looked up later by the same
identifier the bot sees in ``/start``.

Why a dedicated table vs reading from PostHog person profile:

  - Meta CAPI weighs IP / UA / fbp / fbc heavily for Event Match Quality
    (EMQ). PostHog stores ``$ip`` on the **event** row, not the person
    row, so the Persons API returns null and CAPI events ship without IP.
    The result is EMQ ~2-3/10 and zero campaign attribution.
  - PostHog ingestion lags 10-30s; for the fast LP→/start path, the
    CAPI call fires before person properties land. Our existing
    in-process retry (4s) only partially mitigates this.
  - Server-captured IP/UA are immune to ad-block / cookie loss because
    they come from the HTTP request itself.

Idempotent: ``create_table_if_not_exists`` semantics so re-running the
migration on an already-migrated DB is a no-op.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "add_landing_attribution"
down_revision: Union[str, None] = "add_posthog_distinct_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "landing_attribution" in inspector.get_table_names():
        return

    op.create_table(
        "landing_attribution",
        sa.Column("phid", sa.String(), primary_key=True),
        sa.Column("fbp", sa.String(), nullable=True),
        sa.Column("fbc", sa.String(), nullable=True),
        sa.Column("fbclid", sa.String(), nullable=True),
        sa.Column("ttp", sa.String(), nullable=True),
        sa.Column("ttclid", sa.String(), nullable=True),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("landing_url", sa.String(), nullable=True),
        sa.Column("utm_source", sa.String(), nullable=True),
        sa.Column("utm_medium", sa.String(), nullable=True),
        sa.Column("utm_campaign", sa.String(), nullable=True),
        sa.Column("utm_term", sa.String(), nullable=True),
        sa.Column("utm_content", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # utm_source / utm_campaign useful for "which campaign produced this
    # phid?" diagnostics without joining PostHog.
    op.create_index(
        "ix_landing_attribution_utm_campaign",
        "landing_attribution",
        ["utm_campaign"],
    )
    op.create_index(
        "ix_landing_attribution_created_at",
        "landing_attribution",
        ["created_at"],
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_landing_attribution_created_at")
    op.execute("DROP INDEX IF EXISTS ix_landing_attribution_utm_campaign")
    op.execute("DROP TABLE IF EXISTS landing_attribution")
