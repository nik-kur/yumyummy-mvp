"""Add usage guardrail fields and usage_records table

Revision ID: add_usage_guardrails
Revises: add_billing
Create Date: 2026-03-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_usage_guardrails"
down_revision: Union[str, None] = "add_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("usage_cost_current_period", sa.Float(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("usage_period_start", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "usage_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("web_search_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("intent", sa.String(), nullable=True),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_usage_records_id"), "usage_records", ["id"], unique=False)
    op.create_index(op.f("ix_usage_records_user_id"), "usage_records", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_usage_records_user_id"), table_name="usage_records")
    op.drop_index(op.f("ix_usage_records_id"), table_name="usage_records")
    op.drop_table("usage_records")
    op.drop_column("users", "usage_period_start")
    op.drop_column("users", "usage_cost_current_period")
