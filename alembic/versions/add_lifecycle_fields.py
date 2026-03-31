"""Add lifecycle tracking fields to users

Revision ID: add_lifecycle_fields
Revises: add_notification_events
Create Date: 2026-03-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "add_lifecycle_fields"
down_revision: Union[str, None] = "add_notification_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("features_used", sa.String(), nullable=True))
    op.add_column("users", sa.Column("meals_count_trial", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("users", "meals_count_trial")
    op.drop_column("users", "features_used")
