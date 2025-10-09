"""add function_key and retention_extension_days to addon

Revision ID: 20251001_2
Revises: 20251001_1
Create Date: 2025-10-01

"""
from alembic import op
import sqlalchemy as sa
from migrations.postgres_helpers import safe_add_column, safe_drop_column


# revision identifiers, used by Alembic.
revision = '20251001_2'
down_revision = '20251001_1'
branch_labels = None
depends_on = None


def upgrade():
    """Add function_key and retention_extension_days to addon"""
    print("=== Adding function_key and retention_extension_days to addon ===")

    # Add columns safely
    safe_add_column('addon', sa.Column('function_key', sa.String(length=64), nullable=True))
    safe_add_column('addon', sa.Column('retention_extension_days', sa.Integer(), nullable=True))

    print("✅ Addon fields migration completed")


def downgrade():
    """Remove function_key and retention_extension_days from addon"""
    print("=== Removing function_key and retention_extension_days from addon ===")

    # Remove columns safely
    safe_drop_column('addon', 'retention_extension_days')
    safe_drop_column('addon', 'function_key')

    print("✅ Addon fields downgrade completed")