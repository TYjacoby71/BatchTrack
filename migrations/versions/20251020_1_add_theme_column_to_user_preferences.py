
"""add theme column to user_preferences

Revision ID: 20251020_1
Revises: 20251017_2
Create Date: 2025-10-20 18:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20251020_1'
down_revision = '20251017_2'
branch_labels = None
depends_on = None

def table_exists(table_name):
    """Check if table exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    """Check if column exists in table"""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not table_exists(table_name):
        return False
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def upgrade():
    """Add theme column to user_preferences table"""
    print("=== Adding theme column to user_preferences ===")
    
    if table_exists('user_preferences'):
        if not column_exists('user_preferences', 'theme'):
            print("   Adding theme column...")
            try:
                op.add_column('user_preferences', sa.Column('theme', sa.String(length=20), nullable=True))
                print("   ✅ theme column added successfully")
            except Exception as e:
                print(f"   ⚠️  Could not add theme column: {e}")
        else:
            print("   ✅ theme column already exists")
    else:
        print("   ⚠️  user_preferences table not found")
    
    print("✅ Migration completed: theme column available")

def downgrade():
    """Remove theme column from user_preferences table"""
    print("=== Removing theme column from user_preferences ===")
    
    if table_exists('user_preferences') and column_exists('user_preferences', 'theme'):
        print("   Removing theme column...")
        try:
            op.drop_column('user_preferences', 'theme')
            print("   ✅ theme column removed successfully")
        except Exception as e:
            print(f"   ⚠️  Could not remove theme column: {e}")
    else:
        print("   ℹ️  theme column does not exist or table missing")
    
    print("✅ Downgrade completed")
