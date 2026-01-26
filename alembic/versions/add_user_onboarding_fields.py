"""add user onboarding fields

Revision ID: add_onboarding_001
Revises: 707e4ed2a4a7
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_onboarding_001'
down_revision: Union[str, Sequence[str], None] = '707e4ed2a4a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add onboarding and KBJU target fields to users table."""
    # Профиль пользователя (онбординг)
    op.add_column('users', sa.Column('goal_type', sa.String(), nullable=True))
    op.add_column('users', sa.Column('gender', sa.String(), nullable=True))
    op.add_column('users', sa.Column('age', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('height_cm', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('weight_kg', sa.Float(), nullable=True))
    op.add_column('users', sa.Column('activity_level', sa.String(), nullable=True))
    
    # Рассчитанные цели КБЖУ
    op.add_column('users', sa.Column('target_calories', sa.Float(), nullable=True))
    op.add_column('users', sa.Column('target_protein_g', sa.Float(), nullable=True))
    op.add_column('users', sa.Column('target_fat_g', sa.Float(), nullable=True))
    op.add_column('users', sa.Column('target_carbs_g', sa.Float(), nullable=True))
    
    # Флаг завершения онбординга
    op.add_column('users', sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Remove onboarding and KBJU target fields from users table."""
    op.drop_column('users', 'onboarding_completed')
    op.drop_column('users', 'target_carbs_g')
    op.drop_column('users', 'target_fat_g')
    op.drop_column('users', 'target_protein_g')
    op.drop_column('users', 'target_calories')
    op.drop_column('users', 'activity_level')
    op.drop_column('users', 'weight_kg')
    op.drop_column('users', 'height_cm')
    op.drop_column('users', 'age')
    op.drop_column('users', 'gender')
    op.drop_column('users', 'goal_type')
