"""Add installs table (preview mode: one free AI log per install)

Additive: older clients never call /auth/install and never read it.

Revision ID: add_installs
Revises: add_weekly_recaps
Create Date: 2026-10-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_installs"
down_revision: Union[str, None] = "add_weekly_recaps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "installs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("install_id", sa.String(length=128), nullable=False),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("free_log_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ip", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_installs_id", "installs", ["id"])
    op.create_index("ix_installs_install_id", "installs", ["install_id"], unique=True)
    op.create_index("ix_installs_account_id", "installs", ["account_id"])
    op.create_index("ix_installs_ip", "installs", ["ip"])


def downgrade() -> None:
    op.drop_index("ix_installs_ip", table_name="installs")
    op.drop_index("ix_installs_account_id", table_name="installs")
    op.drop_index("ix_installs_install_id", table_name="installs")
    op.drop_index("ix_installs_id", table_name="installs")
    op.drop_table("installs")
