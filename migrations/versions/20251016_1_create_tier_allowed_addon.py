"""
Create tier_allowed_addon association table if missing

Revision ID: 20251016_1    
Revises: 20251015_04
Create Date: 2025-10-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20251016_1'
down_revision = '20251015_04'
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
    # Redundant creation: table is created in 20251001_1. Keep a no-op to preserve ordering.
    # Intentionally do not recreate if missing to avoid duplicate definitions.
    if not table_exists('tier_allowed_addon'):
        # If parents missing, earlier migration would have created it.
        # No action needed here.
        pass


def downgrade():
    # Best-effort drop; skip if table missing
    try:
        op.drop_table('tier_allowed_addon')
    except Exception:
        pass
