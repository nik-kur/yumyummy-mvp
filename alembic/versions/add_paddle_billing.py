"""Add Paddle billing fields to users and payment_events

Revision ID: add_paddle_billing
Revises: add_gumroad_billing
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_paddle_billing"
down_revision: Union[str, None] = "add_gumroad_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("subscription_paddle_id", sa.String(), nullable=True))

    op.add_column("payment_events", sa.Column("paddle_transaction_id", sa.String(), nullable=True))
    op.add_column("payment_events", sa.Column("paddle_subscription_id", sa.String(), nullable=True))

    op.create_index("ix_payment_events_paddle_transaction_id", "payment_events", ["paddle_transaction_id"])
    op.create_index("ix_payment_events_paddle_subscription_id", "payment_events", ["paddle_subscription_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_events_paddle_subscription_id", table_name="payment_events")
    op.drop_index("ix_payment_events_paddle_transaction_id", table_name="payment_events")

    op.drop_column("payment_events", "paddle_subscription_id")
    op.drop_column("payment_events", "paddle_transaction_id")

    op.drop_column("users", "subscription_paddle_id")
