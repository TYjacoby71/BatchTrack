
"""add is_verified field to user table

Revision ID: add_is_verified_to_user
Revises: 39e309ff02d1
Create Date: 2025-08-12 00:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'add_is_verified_to_user'
down_revision = '39e309ff02d1'
branch_labels = None
depends_on = None

def upgrade():
    """Add is_verified field to user table"""
    
    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)

    def column_exists(table_name, column_name):
        """Check if a column exists in a table"""
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception:
            return False

    print("=== Adding is_verified field to user table ===")

    # Add is_verified column if it doesn't exist
    if not column_exists('user', 'is_verified'):
        print("   Adding is_verified column...")
        with op.batch_alter_table('user', schema=None) as batch_op:
            batch_op.add_column(sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='0'))
        print("✅ is_verified column added successfully")
    else:
        print("   ⚠️  is_verified column already exists, skipping")

    print("=== Migration completed ===")

def downgrade():
    """Remove is_verified field from user table"""
    print("=== Removing is_verified field from user table ===")

    with op.batch_alter_table('user', schema=None) as batch_op:
        try:
            batch_op.drop_column('is_verified')
            print("✅ is_verified column removed successfully")
        except Exception as e:
            print(f"   ⚠️  Could not remove is_verified column: {e}")

    print("✅ Downgrade completed")
