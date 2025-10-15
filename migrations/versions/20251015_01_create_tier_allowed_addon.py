"""
Create tier_allowed_addon association table if missing

Revision ID: 20251015_01_create_tier_allowed_addon
Revises: 20251009_2
Create Date: 2025-10-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20251015_01_create_tier_allowed_addon'
down_revision = '20251009_2'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def upgrade():
    # Create association table for allowed add-ons on a tier
    if not table_exists('tier_allowed_addon'):
        # Only create if parent tables exist
        if table_exists('subscription_tier') and table_exists('addon'):
            op.create_table(
                'tier_allowed_addon',
                sa.Column('tier_id', sa.Integer(), nullable=False),
                sa.Column('addon_id', sa.Integer(), nullable=False),
                sa.ForeignKeyConstraint(['tier_id'], ['subscription_tier.id']),
                sa.ForeignKeyConstraint(['addon_id'], ['addon.id']),
                sa.PrimaryKeyConstraint('tier_id', 'addon_id'),
            )


def downgrade():
    # Best-effort drop; skip if table missing
    try:
        op.drop_table('tier_allowed_addon')
    except Exception:
        pass
