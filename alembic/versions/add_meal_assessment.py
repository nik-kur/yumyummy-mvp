"""Add per-meal assessment provenance

Stores HOW the agent obtained the numbers (label / barcode DB / official
site / USDA / estimate...) as a small JSON blob, so the meal card can say
"read off the label in your photo" instead of a bare accuracy badge.
Additive: 25(0) clients never read the column.

Revision ID: add_meal_assessment
Revises: add_meal_items_breakdown
Create Date: 2026-07-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_meal_assessment'
down_revision: Union[str, None] = 'add_meal_items_breakdown'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # JSON blob: {method, domain, portion_estimated, verified_items,
    # total_items}. Text (not JSONB) for dialect-agnosticism — read/written
    # whole, never queried by key.
    op.add_column('meal_entries', sa.Column('assessment_json', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('meal_entries', 'assessment_json')
