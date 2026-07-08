"""Add weekly_recaps table (Week in Recap cache)

Caches the LLM-generated weekly summary per (user, week_start) so the
"Week in Recap" screen / push never regenerates it twice. Numeric stats are
recomputed live; this table only persists the friendly summary (+ a stats
snapshot for the record). Additive: 25(0) clients never read it.

Revision ID: add_weekly_recaps
Revises: add_meal_assessment
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_weekly_recaps"
down_revision: Union[str, None] = "add_meal_assessment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "weekly_recaps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("week_start", sa.Date(), nullable=False, index=True),
        sa.Column("stats_json", sa.Text(), nullable=True),
        sa.Column("llm_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "week_start", name="uq_weekly_recap_user_week"),
    )


def downgrade() -> None:
    op.drop_table("weekly_recaps")
