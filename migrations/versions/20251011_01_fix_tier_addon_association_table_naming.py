
"""Fix tier addon association table naming inconsistency

Revision ID: 20251011_01
Revises: 20251009_3
Create Date: 2025-10-11

This migration ensures the association table expected by the models
(`tier_allowed_addon`) exists in production. It is defensive and idempotent.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = '20251011_01'
down_revision = '20251009_3'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def upgrade():
    # Ensure required parent tables exist
    if not _table_exists('subscription_tier') or not _table_exists('addon'):
        return

    # Create tier_allowed_addon if missing
    if not _table_exists('tier_allowed_addon'):
        op.create_table(
            'tier_allowed_addon',
            sa.Column('tier_id', sa.Integer(), nullable=False),
            sa.Column('addon_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['tier_id'], ['subscription_tier.id']),
            sa.ForeignKeyConstraint(['addon_id'], ['addon.id']),
            sa.PrimaryKeyConstraint('tier_id', 'addon_id'),
        )


def downgrade():
    # Best-effort drop using existence check to avoid aborting the transaction
    try:
        bind = op.get_bind()
        # Use IF EXISTS to be extra safe on Postgres
        if _table_exists('tier_allowed_addon'):
            bind.execute(text("DROP TABLE IF EXISTS tier_allowed_addon CASCADE"))
    except Exception:
        # Do not re-raise; keep downgrade idempotent and non-fatal
        pass
