"""Add Gumroad billing fields to users and payment_events

Revision ID: add_gumroad_billing
Revises: add_usage_guardrails
Create Date: 2026-03-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_gumroad_billing"
down_revision: Union[str, None] = "add_usage_guardrails"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users table ---
    op.add_column("users", sa.Column("subscription_provider", sa.String(), nullable=True))
    op.add_column("users", sa.Column("subscription_gumroad_id", sa.String(), nullable=True))

    # --- payment_events table: new provider-neutral columns ---
    op.add_column("payment_events", sa.Column("provider", sa.String(), server_default="telegram", nullable=False))
    op.add_column("payment_events", sa.Column("provider_event_id", sa.String(), nullable=True))
    op.add_column("payment_events", sa.Column("gumroad_sale_id", sa.String(), nullable=True))
    op.add_column("payment_events", sa.Column("gumroad_subscription_id", sa.String(), nullable=True))
    op.add_column("payment_events", sa.Column("amount_cents", sa.Integer(), nullable=True))
    op.add_column("payment_events", sa.Column("event_type", sa.String(), server_default="purchase", nullable=False))

    # Make telegram_payment_charge_id nullable (Gumroad events won't have it)
    with op.batch_alter_table("payment_events") as batch_op:
        batch_op.alter_column("telegram_payment_charge_id", existing_type=sa.String(), nullable=True)
        batch_op.alter_column("amount_xtr", existing_type=sa.Integer(), nullable=True)

    # Indexes for Gumroad lookups
    op.create_index("ix_payment_events_provider_event_id", "payment_events", ["provider_event_id"])
    op.create_index("ix_payment_events_gumroad_sale_id", "payment_events", ["gumroad_sale_id"])
    op.create_index("ix_payment_events_gumroad_subscription_id", "payment_events", ["gumroad_subscription_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_events_gumroad_subscription_id", table_name="payment_events")
    op.drop_index("ix_payment_events_gumroad_sale_id", table_name="payment_events")
    op.drop_index("ix_payment_events_provider_event_id", table_name="payment_events")

    with op.batch_alter_table("payment_events") as batch_op:
        batch_op.alter_column("amount_xtr", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("telegram_payment_charge_id", existing_type=sa.String(), nullable=False)

    op.drop_column("payment_events", "event_type")
    op.drop_column("payment_events", "amount_cents")
    op.drop_column("payment_events", "gumroad_subscription_id")
    op.drop_column("payment_events", "gumroad_sale_id")
    op.drop_column("payment_events", "provider_event_id")
    op.drop_column("payment_events", "provider")

    op.drop_column("users", "subscription_gumroad_id")
    op.drop_column("users", "subscription_provider")
