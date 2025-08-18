
"""fix all missing tier columns

Revision ID: fix_all_missing_tier_columns
Revises: fix_missing_max_users_column
Create Date: 2025-08-18 20:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'fix_all_missing_tier_columns'
down_revision = 'fix_missing_max_users_column'
branch_labels = None
depends_on = None


def upgrade():
    """Add all missing tier limit columns that should have been added"""
    
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    def column_exists(table_name, column_name):
        if table_name not in inspector.get_table_names():
            return False
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    
    print("=== Adding ALL missing subscription tier columns ===")
    
    # All the tier limit columns that should exist based on the model
    tier_limit_columns = [
        ('max_recipes', 'Maximum recipes allowed'),
        ('max_batches', 'Maximum batches allowed'),
        ('max_products', 'Maximum products allowed'),
        ('max_batchbot_requests', 'Maximum AI requests allowed'),
        ('max_monthly_batches', 'Maximum monthly batches allowed')
    ]
    
    for col_name, description in tier_limit_columns:
        if not column_exists('subscription_tier', col_name):
            print(f"   Adding missing {col_name} column...")
            op.add_column('subscription_tier', sa.Column(col_name, sa.Integer, nullable=True))
            print(f"   ✅ {col_name} column added successfully")
        else:
            print(f"   ⚠️  {col_name} column already exists")
    
    print("✅ All missing tier columns migration completed")


def downgrade():
    """Remove the tier limit columns"""
    tier_limit_columns = [
        'max_recipes', 'max_batches', 'max_products', 
        'max_batchbot_requests', 'max_monthly_batches'
    ]
    
    for col_name in tier_limit_columns:
        try:
            op.drop_column('subscription_tier', col_name)
        except Exception:
            pass
