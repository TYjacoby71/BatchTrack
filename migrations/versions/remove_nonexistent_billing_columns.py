
"""remove nonexistent billing columns

Revision ID: f4e5d6c7b8a9
Revises: 0e15af770cb3
Create Date: 2025-08-06 00:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f4e5d6c7b8a9'
down_revision = '0e15af770cb3'
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def upgrade():
    """Remove columns that were referenced but don't exist"""
    print("=== Removing nonexistent billing columns ===")
    
    # These columns don't exist in the current schema but were being referenced
    nonexistent_columns = [
        'billing_cycle',
        'pricing_category', 
        'price_amount',
        'currency'
    ]
    
    for col_name in nonexistent_columns:
        if column_exists('subscription_tier', col_name):
            print(f"   Removing {col_name} from subscription_tier")
            try:
                op.drop_column('subscription_tier', col_name)
                print(f"   ✅ Removed {col_name}")
            except Exception as e:
                print(f"   ⚠️  Could not remove {col_name}: {e}")
        else:
            print(f"   ✅ Column {col_name} already doesn't exist")
    
    print("=== Migration completed ===")

def downgrade():
    """This migration only removes columns that shouldn't exist"""
    print("=== No downgrade needed - columns were incorrectly referenced ===")
    pass
