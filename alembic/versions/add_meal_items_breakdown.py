"""Add per-meal ingredient breakdown + source url

Stores the AI workflow's ``items`` (per-ingredient name/grams/macros/source)
and the primary ``source_url`` directly on each meal entry so the app can show
"How we got this" with a real source link and an ingredient-level breakdown,
and so a meal can be re-logged verbatim ("Repeat") without a fresh AI search.

Revision ID: add_meal_items_breakdown
Revises: add_accounts_identities
Create Date: 2026-06-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_meal_items_breakdown'
down_revision: Union[str, None] = 'add_accounts_identities'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # JSON-encoded list of {name, grams, calories_kcal, protein_g, fat_g,
    # carbs_g, source_url}. Text (not JSONB) to keep the column dialect-agnostic
    # and because we only ever read/write the whole blob.
    op.add_column('meal_entries', sa.Column('items_json', sa.Text(), nullable=True))
    # Primary source the macros were checked against (top-level workflow source).
    op.add_column('meal_entries', sa.Column('source_url', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('meal_entries', 'source_url')
    op.drop_column('meal_entries', 'items_json')
