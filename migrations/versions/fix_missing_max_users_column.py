
"""fix missing max_users column

Revision ID: fix_missing_max_users_column  
Revises: 758a11548815
Create Date: 2025-08-18 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'fix_missing_max_users_column'
down_revision = '758a11548815'
branch_labels = None
depends_on = None


def upgrade():
    """Add missing max_users column if it doesn't exist"""
    
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    def column_exists(table_name, column_name):
        if table_name not in inspector.get_table_names():
            return False
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    
    print("=== Fixing missing max_users column ===")
    
    if not column_exists('subscription_tier', 'max_users'):
        print("   Adding missing max_users column...")
        op.add_column('subscription_tier', sa.Column('max_users', sa.Integer, nullable=True))
        print("   ✅ max_users column added successfully")
    else:
        print("   ⚠️  max_users column already exists")
    
    print("✅ Fix migration completed")


def downgrade():
    """Remove max_users column"""
    try:
        op.drop_column('subscription_tier', 'max_users')
    except Exception:
        pass
