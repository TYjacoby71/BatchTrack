
"""Add offline billing support

Revision ID: add_offline_billing_support
Revises: drop_deprecated_billing_columns
Create Date: 2025-08-06 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_offline_billing_support'
down_revision = 'drop_deprecated_billing_columns'
branch_labels = None
depends_on = None

def upgrade():
    """Mock migration - no changes needed"""
    print("=== Mock migration: add_offline_billing_support ===")
    print("   No changes to apply - this is a mock revision for production sync")
    print("✅ Mock migration completed")

def downgrade():
    """Mock migration - no changes to revert"""
    print("=== Mock migration downgrade: add_offline_billing_support ===")
    print("   No changes to revert - this is a mock revision for production sync")
    print("✅ Downgrade completed successfully")
