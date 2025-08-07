
"""add_fallback_price_column

Revision ID: add_fallback_price_column
Revises: 4246268c4e7c
Create Date: 2025-08-06 22:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'add_fallback_price_column'
down_revision = 'fix_missing_email_verification'
branch_labels = None
depends_on = None

def upgrade():
    """Add fallback_price column to subscription_tier table if it doesn't exist"""
    
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
    
    print("=== Adding fallback_price column to subscription_tier ===")
    
    # Add fallback_price column if it doesn't exist
    if not column_exists('subscription_tier', 'fallback_price'):
        print("   Adding fallback_price column...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.add_column(sa.Column('fallback_price', sa.String(32), nullable=True))
        print("✅ fallback_price column added successfully")
    else:
        print("   ⚠️  fallback_price column already exists, skipping")

def downgrade():
    """Remove fallback_price column from subscription_tier table"""
    
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
    
    print("=== Removing fallback_price column from subscription_tier ===")
    
    # Remove fallback_price column if it exists
    if column_exists('subscription_tier', 'fallback_price'):
        print("   Dropping fallback_price column...")
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.drop_column('fallback_price')
        print("✅ fallback_price column removed successfully")
    else:
        print("   ⚠️  fallback_price column doesn't exist, skipping")
