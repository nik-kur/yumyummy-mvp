"""Add notification_events table and first_meal_after_onboarding_at to users

Revision ID: add_notification_events
Revises: add_churn_surveys
Create Date: 2026-03-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_notification_events"
down_revision: Union[str, None] = "add_churn_surveys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.String(), nullable=False, index=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("extra_data", sa.String(), nullable=True),
    )

    op.add_column(
        "users",
        sa.Column("first_meal_after_onboarding_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "first_meal_after_onboarding_at")
    op.drop_table("notification_events")
