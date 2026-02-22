"""Add user timezone field

Revision ID: add_user_timezone
Revises: add_onboarding_fields
Create Date: 2026-02-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_user_timezone'
down_revision: Union[str, None] = 'add_onboarding_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('timezone', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'timezone')
