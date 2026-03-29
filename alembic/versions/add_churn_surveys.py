"""Add churn_surveys table

Revision ID: add_churn_surveys
Revises: add_paddle_billing
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_churn_surveys"
down_revision: Union[str, None] = "add_paddle_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "churn_surveys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("telegram_id", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("comment", sa.String(), nullable=True),
        sa.Column("subscription_provider", sa.String(), nullable=True),
        sa.Column("subscription_plan_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_churn_surveys_telegram_id", "churn_surveys", ["telegram_id"])


def downgrade() -> None:
    op.drop_index("ix_churn_surveys_telegram_id", table_name="churn_surveys")
    op.drop_table("churn_surveys")
