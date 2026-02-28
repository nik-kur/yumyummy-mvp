"""Add saved_meals and saved_meal_items tables

Revision ID: add_saved_meals
Revises: add_user_timezone
Create Date: 2026-02-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'add_saved_meals'
down_revision: Union[str, None] = 'add_user_timezone'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'saved_meals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('total_calories', sa.Float(), server_default='0'),
        sa.Column('total_protein_g', sa.Float(), server_default='0'),
        sa.Column('total_fat_g', sa.Float(), server_default='0'),
        sa.Column('total_carbs_g', sa.Float(), server_default='0'),
        sa.Column('use_count', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_saved_meals_id'), 'saved_meals', ['id'], unique=False)
    op.create_index(op.f('ix_saved_meals_user_id'), 'saved_meals', ['user_id'], unique=False)

    op.create_table(
        'saved_meal_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('saved_meal_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('grams', sa.Float(), nullable=True),
        sa.Column('calories_kcal', sa.Float(), server_default='0'),
        sa.Column('protein_g', sa.Float(), server_default='0'),
        sa.Column('fat_g', sa.Float(), server_default='0'),
        sa.Column('carbs_g', sa.Float(), server_default='0'),
        sa.Column('source_url', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['saved_meal_id'], ['saved_meals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_saved_meal_items_id'), 'saved_meal_items', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_saved_meal_items_id'), table_name='saved_meal_items')
    op.drop_table('saved_meal_items')
    op.drop_index(op.f('ix_saved_meals_user_id'), table_name='saved_meals')
    op.drop_index(op.f('ix_saved_meals_id'), table_name='saved_meals')
    op.drop_table('saved_meals')
