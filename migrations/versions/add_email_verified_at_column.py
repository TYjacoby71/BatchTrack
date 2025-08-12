"""add email_verified_at column

Revision ID: add_email_verified_at_column
Revises: add_is_verified_to_user
Create Date: 2025-08-12 02:17:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_email_verified_at_column'
down_revision = 'add_is_verified_to_user'
branch_labels = None
depends_on = None

def upgrade():
    """Add email_verified_at column - no-op as column already exists"""
    print("=== Adding email_verified_at column (no-op) ===")
    print("   Column already exists in current schema")
    print("✅ Migration completed")

def downgrade():
    """Remove email_verified_at column - no-op"""
    print("=== Removing email_verified_at column (no-op) ===") 
    print("   No changes to revert")
    print("✅ Downgrade completed")
