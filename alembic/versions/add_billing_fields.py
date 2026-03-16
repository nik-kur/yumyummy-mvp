"""Add billing fields to users and payment_events table

Revision ID: add_billing
Revises: add_saved_meals
Create Date: 2026-03-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'add_billing'
down_revision: Union[str, None] = 'add_saved_meals'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Billing columns on users
    op.add_column('users', sa.Column('trial_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('subscription_plan_id', sa.String(), nullable=True))
    op.add_column('users', sa.Column('subscription_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('subscription_ends_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('subscription_auto_renew', sa.Boolean(), nullable=True))
    op.add_column('users', sa.Column('subscription_telegram_charge_id', sa.String(), nullable=True))

    # Payment events audit log
    op.create_table(
        'payment_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('telegram_payment_charge_id', sa.String(), nullable=False),
        sa.Column('provider_payment_charge_id', sa.String(), nullable=True),
        sa.Column('plan_id', sa.String(), nullable=False),
        sa.Column('amount_xtr', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(), server_default='XTR', nullable=False),
        sa.Column('is_recurring', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_first_recurring', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('invoice_payload', sa.String(), nullable=True),
        sa.Column('raw_payload', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_payment_events_id'), 'payment_events', ['id'], unique=False)
    op.create_index(
        op.f('ix_payment_events_telegram_payment_charge_id'),
        'payment_events',
        ['telegram_payment_charge_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_payment_events_telegram_payment_charge_id'), table_name='payment_events')
    op.drop_index(op.f('ix_payment_events_id'), table_name='payment_events')
    op.drop_table('payment_events')

    op.drop_column('users', 'subscription_telegram_charge_id')
    op.drop_column('users', 'subscription_auto_renew')
    op.drop_column('users', 'subscription_ends_at')
    op.drop_column('users', 'subscription_started_at')
    op.drop_column('users', 'subscription_plan_id')
    op.drop_column('users', 'trial_ends_at')
    op.drop_column('users', 'trial_started_at')
